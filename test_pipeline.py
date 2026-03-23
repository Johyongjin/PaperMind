"""3개 PDF 파이프라인 테스트 스크립트"""
from modules.pdf_processor import collect_pdfs, deduplicate, process_pdf
from modules.ai_analyzer import analyze_pdf
from modules.sheets_manager import SheetsManager
from modules.logger import log_failure

def run_test(n=3):
    print("=" * 60)
    print(f"PaperMind 파이프라인 테스트 ({n}개 PDF)")
    print("=" * 60)

    # 1. PDF 수집 및 중복 제거
    all_pdfs = collect_pdfs("Articles")
    unique_pdfs, skipped = deduplicate(all_pdfs)
    print(f"\nPDF 수집: {len(all_pdfs)}개 → 중복 {len(skipped)}개 제거 → {len(unique_pdfs)}개")

    # 2. 스캔 PDF 제외하고 일반 PDF만 선택
    candidates = []
    for path in unique_pdfs:
        if len(candidates) >= n * 3:  # 여유있게 수집
            break
        result = process_pdf(path)
        if not result.get("is_scan") and "error" not in result and result.get("chunks"):
            candidates.append((path, result))
        if len(candidates) >= n:
            break

    print(f"테스트 대상: {len(candidates)}개\n")

    # 3. Sheets 연결
    sheets = SheetsManager()
    print("Google Sheets 연결 완료\n")

    # 4. 파이프라인 실행
    for i, (path, pdf_result) in enumerate(candidates, 1):
        print(f"[{i}/{n}] {path.name}")
        print(f"  페이지: {pdf_result['page_count']}p / 청크: {len(pdf_result['chunks'])}개")

        # AI 분석
        print("  Claude 분석 중...", end=" ", flush=True)
        analysis = analyze_pdf(pdf_result)

        if "error" in analysis:
            print(f"실패 - {analysis['error']}")
            log_failure(path.name, analysis["error"])
            continue

        doc_type = analysis.get("type", "?")
        title = analysis.get("title", "제목 없음")
        print(f"완료 ({doc_type})")
        print(f"  제목: {title[:60]}")

        # 시트 저장
        print("  시트 저장 중...", end=" ", flush=True)
        try:
            status = sheets.save_result(analysis)
            print(f"{status}")
        except RuntimeError as e:
            print(f"실패 - {e}")
            log_failure(path.name, str(e))
            continue

        # 추출 결과 미리보기
        if doc_type == "paper":
            print(f"  저자: {analysis.get('authors', '')[:50]}")
            print(f"  연도: {analysis.get('year', '')}")
            print(f"  저널: {analysis.get('journal', '')[:50]}")
            print(f"  키워드: {analysis.get('keywords', '')[:60]}")
        else:
            print(f"  발행기관: {analysis.get('institution', '')[:50]}")
            print(f"  연도: {analysis.get('year', '')}")
            print(f"  키워드: {analysis.get('keywords', '')[:60]}")
        print()

    print("=" * 60)
    print("테스트 완료. 스프레드시트에서 결과를 확인하세요.")
    print("=" * 60)


if __name__ == "__main__":
    run_test(n=3)
