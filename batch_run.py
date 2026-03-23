"""전체 PDF 배치 처리 스크립트"""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from modules.pdf_processor import collect_pdfs, deduplicate, process_pdf, get_first_page_text
from modules.ai_analyzer import analyze_pdf
from modules.sheets_manager import SheetsManager
from modules.logger import log_failure

PROGRESS_LOG = Path("batch_progress.log")
PROCESSED_HASHES_FILE = Path("processed_hashes.json")


def load_processed_hashes() -> set:
    if PROCESSED_HASHES_FILE.exists():
        try:
            return set(json.loads(PROCESSED_HASHES_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_processed_hash(file_hash: str, processed_hashes: set):
    processed_hashes.add(file_hash)
    PROCESSED_HASHES_FILE.write_text(
        json.dumps(list(processed_hashes), ensure_ascii=False),
        encoding="utf-8"
    )


def quick_hash(path: Path) -> str:
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def title_in_text(titles: set, text: str) -> bool:
    """소문자 변환된 텍스트에 15자 이상 제목이 포함되는지 확인한다."""
    text_lower = text.lower()
    return any(len(t) >= 15 and t.lower() in text_lower for t in titles)


def log(msg: str, end="\n"):
    try:
        print(msg, end=end, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", errors="replace").decode("ascii", errors="replace"), end=end, flush=True)
    with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
        f.write(msg + end)


def run_batch():
    PROGRESS_LOG.write_text("", encoding="utf-8")

    start_time = datetime.now()
    log("=" * 65)
    log("  PaperMind 전체 배치 처리 시작")
    log(f"  시작 시각: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 65)

    # 1. PDF 수집 및 해시 중복 제거
    log("\n[준비] PDF 수집 중...")
    all_pdfs = collect_pdfs("Articles")
    unique_pdfs, hash_dupes = deduplicate(all_pdfs)
    log(f"  발견: {len(all_pdfs)}개 / 해시 중복: {len(hash_dupes)}개 / 처리 대상: {len(unique_pdfs)}개")

    # 2. Google Sheets 연결 및 기존 제목 로드
    log("\n[준비] Google Sheets 연결 중...")
    sheets = SheetsManager()
    existing_paper_titles  = sheets.get_existing_titles("paper")
    existing_report_titles = sheets.get_existing_titles("report")
    all_existing_titles    = existing_paper_titles | existing_report_titles
    log(f"  기존 저장 - 논문: {len(existing_paper_titles)}개 / 보고서: {len(existing_report_titles)}개")

    # 3. 로컬 해시 캐시 로드
    processed_hashes = load_processed_hashes()
    log(f"  로컬 캐시  - 처리 완료: {len(processed_hashes)}개")

    # 4. 배치 처리
    total          = len(unique_pdfs)
    success_paper  = 0
    success_report = 0
    skipped_scan   = 0
    skipped_title  = 0
    skipped_hash   = len(hash_dupes)
    skipped_cache  = 0
    failed         = 0

    log(f"\n[처리] 총 {total}개 시작\n")

    for idx, path in enumerate(unique_pdfs, 1):
        prefix = f"[{idx:3d}/{total}] {path.name[:50]:50s}"

        # ── 사전 필터 1: 로컬 해시 캐시 ──────────────────────────────────
        fhash = quick_hash(path)
        if fhash in processed_hashes:
            log(f"{prefix} → 캐시 건너뜀")
            skipped_cache += 1
            continue

        # ── 사전 필터 2: 첫 페이지 제목 매칭 ────────────────────────────
        if all_existing_titles:
            first_text = get_first_page_text(path)
            if title_in_text(all_existing_titles, first_text):
                log(f"{prefix} → 기존 저장 건너뜀 (제목 매칭)")
                skipped_title += 1
                save_processed_hash(fhash, processed_hashes)
                continue

        # ── PDF 파싱 ──────────────────────────────────────────────────────
        pdf_result = process_pdf(path)

        if pdf_result.get("is_scan"):
            log(f"{prefix} → 스캔PDF 건너뜀")
            log_failure(path.name, "스캔 PDF - 텍스트 추출 불가")
            skipped_scan += 1
            continue

        if "error" in pdf_result:
            log(f"{prefix} → 파싱 오류")
            log_failure(path.name, pdf_result["error"])
            failed += 1
            continue

        pages = pdf_result['page_count']
        log(f"{prefix} ({pages}p) 분석중...", end=" ")

        # ── Claude 분석 ──────────────────────────────────────────────────
        analysis = analyze_pdf(pdf_result)

        if "error" in analysis:
            log("분석 실패")
            log_failure(path.name, analysis["error"])
            failed += 1
            continue

        doc_type = analysis.get("type")
        title    = analysis.get("title", "").strip()

        # ── 제목 중복 확인 (안전망) ──────────────────────────────────────
        if doc_type == "paper" and title in existing_paper_titles:
            log("제목 중복 건너뜀")
            skipped_title += 1
            save_processed_hash(fhash, processed_hashes)
            continue
        if doc_type == "report" and title in existing_report_titles:
            log("제목 중복 건너뜀")
            skipped_title += 1
            save_processed_hash(fhash, processed_hashes)
            continue

        # ── 시트 저장 ────────────────────────────────────────────────────
        try:
            status = sheets.save_result(analysis)
            if status == "saved":
                if doc_type == "paper":
                    existing_paper_titles.add(title)
                    success_paper += 1
                else:
                    existing_report_titles.add(title)
                    success_report += 1
                all_existing_titles.add(title)
                save_processed_hash(fhash, processed_hashes)
                log(f"저장완료 ({doc_type})")
            elif status == "duplicate":
                log("제목 중복 건너뜀")
                skipped_title += 1
                save_processed_hash(fhash, processed_hashes)
            else:
                log("저장 오류")
                log_failure(path.name, "save_result 반환값 error")
                failed += 1
        except RuntimeError as e:
            log("저장 실패")
            log_failure(path.name, str(e))
            failed += 1

    # 5. 최종 요약
    end_time  = datetime.now()
    duration  = end_time - start_time
    total_min = int(duration.total_seconds() // 60)
    total_sec = int(duration.total_seconds() % 60)

    log("\n" + "=" * 65)
    log("  배치 처리 완료")
    log(f"  종료 시각: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"  소요 시간: {total_min}분 {total_sec}초")
    log("=" * 65)
    log(f"  저장 완료  : 논문 {success_paper}개 / 보고서 {success_report}개 (합계 {success_paper + success_report}개)")
    log(f"  건너뜀     : 해시중복 {skipped_hash}개 / 제목중복 {skipped_title}개 / 스캔PDF {skipped_scan}개 / 캐시 {skipped_cache}개")
    log(f"  실패       : {failed}개")
    log("=" * 65)
    if failed > 0:
        log("  실패 목록 -> failed_files.log / failed_files.csv 참고")


if __name__ == "__main__":
    run_batch()
