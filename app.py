import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from config import GOOGLE_SERVICE_ACCOUNT_PATH, GOOGLE_SHEETS_URL
from modules.ai_analyzer import analyze_pdf
from modules.logger import log_failure
from modules.pdf_processor import (
    collect_pdfs,
    compute_hash,
    deduplicate,
    get_first_page_text,
    process_pdf,
)
from modules.sheets_manager import SheetsManager

# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

PROCESSED_HASHES_FILE = Path("processed_hashes.json")


def _save_uploaded_to_tmp(uploaded_file) -> Path:
    suffix = Path(uploaded_file.name).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(uploaded_file.read())
        return Path(tmp.name)


def _display_paper_result(analysis: dict):
    col1, col2 = st.columns([2, 1])
    with col1:
        st.write(f"**제목**: {analysis.get('title', '')}")
        st.write(f"**저자**: {analysis.get('authors', '')}")
        st.write(f"**저널**: {analysis.get('journal', '')}")
        st.write(f"**연도**: {analysis.get('year', '')}  |  **키워드**: {analysis.get('keywords', '')}")
    with col2:
        st.caption("APA 인용")
        st.write(analysis.get("apa_citation", ""))
    with st.expander("상세 내용 보기"):
        st.write("**연구목적**")
        st.write(analysis.get("research_purpose", ""))
        st.write("**연구방법**")
        st.write(analysis.get("research_method", ""))
        st.write("**연구결과**")
        st.write(analysis.get("research_result", ""))


def _display_report_result(analysis: dict):
    col1, col2 = st.columns([2, 1])
    with col1:
        st.write(f"**제목**: {analysis.get('title', '')}")
        st.write(f"**발행기관**: {analysis.get('institution', '')}")
        st.write(f"**연도**: {analysis.get('year', '')}  |  **키워드**: {analysis.get('keywords', '')}")
    with col2:
        st.caption("인용")
        st.write(analysis.get("citation", ""))
    with st.expander("상세 내용 보기"):
        st.write("**배경**")
        st.write(analysis.get("background", ""))
        st.write("**주요내용**")
        st.write(analysis.get("main_content", ""))
        st.write("**시사점**")
        st.write(analysis.get("implications", ""))


def _load_processed_hashes() -> set:
    if PROCESSED_HASHES_FILE.exists():
        try:
            return set(json.loads(PROCESSED_HASHES_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def _save_processed_hash(file_hash: str, processed_hashes: set):
    processed_hashes.add(file_hash)
    PROCESSED_HASHES_FILE.write_text(
        json.dumps(list(processed_hashes), ensure_ascii=False),
        encoding="utf-8",
    )


def _title_in_text(titles: set, text: str) -> bool:
    text_lower = text.lower()
    return any(len(t) >= 15 and t.lower() in text_lower for t in titles)


def _process_and_save(upf, force_type: str, sheets: SheetsManager):
    """업로드 파일 1개를 처리하고 저장한다. (논문/보고서 공통)
    반환: "saved" | "duplicate" | "scan" | "error"
    """
    tmp_path = _save_uploaded_to_tmp(upf)
    try:
        pdf_result = process_pdf(tmp_path)
        pdf_result["file_name"] = upf.name

        if pdf_result.get("is_scan"):
            log_failure(upf.name, "스캔 PDF - 텍스트 추출 불가")
            return "scan", None

        if "error" in pdf_result:
            log_failure(upf.name, pdf_result["error"])
            return "error", pdf_result["error"]

        analysis = analyze_pdf(pdf_result, force_type=force_type)

        if "error" in analysis:
            log_failure(upf.name, analysis["error"])
            return "error", analysis

        save_status = sheets.save_result(analysis)
        return save_status, analysis

    except Exception as e:
        log_failure(upf.name, str(e))
        return "error", str(e)
    finally:
        tmp_path.unlink(missing_ok=True)


# ── 페이지 설정 ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="PaperMind", layout="wide", page_icon="📚")
st.title("📚 PaperMind")
st.caption("PDF 논문·보고서를 AI로 분석하여 Google Sheets에 정리합니다.")

# ── 사이드바 ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("설정")
    sheets_url = st.text_input(
        "Google Sheets URL",
        value=GOOGLE_SHEETS_URL or "",
        placeholder="https://docs.google.com/spreadsheets/d/...",
    )
    if sheets_url:
        st.success("URL 입력됨")
    else:
        st.warning("Sheets URL을 입력하세요")

    st.divider()
    st.caption(f"서비스 계정: `{GOOGLE_SERVICE_ACCOUNT_PATH}`")


# ── 탭 ───────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs(
    ["📄 논문 추가", "📊 보고서 추가", "📋 전체 목록", "⚙️ 배치 처리"]
)


# ══════════════════════════════════════════════════════════════════════════════
# 탭 1: 논문 추가
# ══════════════════════════════════════════════════════════════════════════════

with tab1:
    st.subheader("논문 추가")
    st.caption("업로드한 PDF를 학술 논문으로 분석하여 Sheets에 저장합니다.")

    paper_files = st.file_uploader(
        "PDF 파일 선택",
        type="pdf",
        accept_multiple_files=True,
        key="paper_uploader",
    )

    if paper_files:
        st.info(f"{len(paper_files)}개 파일 선택됨")

    if st.button(
        "분석 및 저장",
        key="paper_run",
        disabled=not (paper_files and sheets_url),
    ):
        try:
            sheets = SheetsManager(sheets_url)
        except Exception as e:
            st.error(f"Sheets 연결 실패: {e}")
            st.stop()

        success, failed, duplicate, scan = 0, 0, 0, 0

        for upf in paper_files:
            with st.status(f"처리 중: {upf.name}", expanded=True) as status:
                st.write("PDF 텍스트 추출 중...")
                result_code, result_data = _process_and_save(upf, "paper", sheets)

                if result_code == "saved":
                    status.update(label=f"저장 완료: {upf.name}", state="complete")
                    success += 1
                    _display_paper_result(result_data)
                elif result_code == "duplicate":
                    status.update(label=f"중복 — 건너뜀: {upf.name}", state="complete")
                    duplicate += 1
                elif result_code == "scan":
                    status.update(label=f"스캔 PDF — 건너뜀: {upf.name}", state="error")
                    scan += 1
                else:
                    status.update(label=f"실패: {upf.name}", state="error")
                    if isinstance(result_data, dict) and "error" in result_data:
                        st.error(result_data["error"])
                    elif result_data:
                        st.error(str(result_data))
                    failed += 1

        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("저장 완료", success)
        c2.metric("중복 건너뜀", duplicate)
        c3.metric("스캔 PDF", scan)
        c4.metric("실패", failed)


# ══════════════════════════════════════════════════════════════════════════════
# 탭 2: 보고서 추가
# ══════════════════════════════════════════════════════════════════════════════

with tab2:
    st.subheader("보고서 추가")
    st.caption("업로드한 PDF를 보고서로 분석하여 Sheets에 저장합니다.")

    report_files = st.file_uploader(
        "PDF 파일 선택",
        type="pdf",
        accept_multiple_files=True,
        key="report_uploader",
    )

    if report_files:
        st.info(f"{len(report_files)}개 파일 선택됨")

    if st.button(
        "분석 및 저장",
        key="report_run",
        disabled=not (report_files and sheets_url),
    ):
        try:
            sheets = SheetsManager(sheets_url)
        except Exception as e:
            st.error(f"Sheets 연결 실패: {e}")
            st.stop()

        success, failed, duplicate, scan = 0, 0, 0, 0

        for upf in report_files:
            with st.status(f"처리 중: {upf.name}", expanded=True) as status:
                st.write("PDF 텍스트 추출 중...")
                result_code, result_data = _process_and_save(upf, "report", sheets)

                if result_code == "saved":
                    status.update(label=f"저장 완료: {upf.name}", state="complete")
                    success += 1
                    _display_report_result(result_data)
                elif result_code == "duplicate":
                    status.update(label=f"중복 — 건너뜀: {upf.name}", state="complete")
                    duplicate += 1
                elif result_code == "scan":
                    status.update(label=f"스캔 PDF — 건너뜀: {upf.name}", state="error")
                    scan += 1
                else:
                    status.update(label=f"실패: {upf.name}", state="error")
                    if isinstance(result_data, dict) and "error" in result_data:
                        st.error(result_data["error"])
                    elif result_data:
                        st.error(str(result_data))
                    failed += 1

        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("저장 완료", success)
        c2.metric("중복 건너뜀", duplicate)
        c3.metric("스캔 PDF", scan)
        c4.metric("실패", failed)


# ══════════════════════════════════════════════════════════════════════════════
# 탭 3: 전체 목록
# ══════════════════════════════════════════════════════════════════════════════

with tab3:
    st.subheader("전체 목록")

    if not sheets_url:
        st.warning("사이드바에서 Sheets URL을 입력하세요.")
    else:
        if st.button("데이터 불러오기", key="list_load"):
            try:
                sheets = SheetsManager(sheets_url)
                with st.spinner("불러오는 중..."):
                    st.session_state["list_data"] = {
                        "논문 목록":       sheets.get_sheet_data("논문 목록"),
                        "논문 상세요약":   sheets.get_sheet_data("논문 상세요약"),
                        "보고서 목록":     sheets.get_sheet_data("보고서 목록"),
                        "보고서 상세요약": sheets.get_sheet_data("보고서 상세요약"),
                    }
            except Exception as e:
                st.error(f"불러오기 실패: {e}")

        if "list_data" in st.session_state:
            data = st.session_state["list_data"]
            sub1, sub2, sub3, sub4 = st.tabs(
                ["논문 목록", "논문 상세요약", "보고서 목록", "보고서 상세요약"]
            )
            for subtab, key in [
                (sub1, "논문 목록"),
                (sub2, "논문 상세요약"),
                (sub3, "보고서 목록"),
                (sub4, "보고서 상세요약"),
            ]:
                with subtab:
                    rows = data[key]
                    if len(rows) > 1:
                        df = pd.DataFrame(rows[1:], columns=rows[0])
                        st.caption(f"총 {len(df)}건")
                        st.dataframe(df, use_container_width=True)
                    elif len(rows) == 1:
                        st.info("데이터가 없습니다 (헤더만 존재).")
                    else:
                        st.info("시트가 비어 있습니다.")


# ══════════════════════════════════════════════════════════════════════════════
# 탭 4: 배치 처리
# ══════════════════════════════════════════════════════════════════════════════

with tab4:
    st.subheader("배치 처리")
    st.caption("폴더 내 전체 PDF를 일괄 분석하여 Sheets에 저장합니다.")

    folder_input = st.text_input(
        "PDF 폴더 경로",
        placeholder="예: C:/Users/.../Articles",
    )

    batch_mode = st.radio(
        "처리 모드",
        ["전체 처리", "새 파일만 (캐시 기반)"],
        help="'새 파일만'은 processed_hashes.json을 기준으로 이미 처리한 파일을 건너뜁니다.",
    )

    folder_valid = bool(folder_input and Path(folder_input).is_dir())
    if folder_input and not folder_valid:
        st.error("존재하지 않는 폴더 경로입니다.")

    if st.button(
        "배치 처리 시작",
        key="batch_run",
        disabled=not (folder_valid and sheets_url),
    ):
        # Sheets 연결
        try:
            sheets = SheetsManager(sheets_url)
        except Exception as e:
            st.error(f"Sheets 연결 실패: {e}")
            st.stop()

        # PDF 수집
        all_pdfs = collect_pdfs(folder_input)
        unique_pdfs, hash_dupes = deduplicate(all_pdfs)

        st.info(
            f"발견: **{len(all_pdfs)}**개 / 해시 중복: **{len(hash_dupes)}**개 / "
            f"처리 대상: **{len(unique_pdfs)}**개"
        )

        existing_paper_titles = sheets.get_existing_titles("paper")
        existing_report_titles = sheets.get_existing_titles("report")
        all_existing_titles = existing_paper_titles | existing_report_titles

        processed_hashes = (
            _load_processed_hashes()
            if batch_mode == "새 파일만 (캐시 기반)"
            else set()
        )

        total = len(unique_pdfs)
        progress_bar = st.progress(0)
        status_text = st.empty()

        success_paper = 0
        success_report = 0
        skipped_cache = 0
        skipped_title = 0
        skipped_scan = 0
        failed = 0
        failed_list = []

        for idx, path in enumerate(unique_pdfs):
            progress_bar.progress((idx + 1) / total)
            status_text.write(f"[{idx + 1}/{total}] {path.name}")

            # 캐시 필터
            fhash = compute_hash(path)
            if batch_mode == "새 파일만 (캐시 기반)" and fhash in processed_hashes:
                skipped_cache += 1
                continue

            # 제목 사전 필터
            if all_existing_titles:
                first_text = get_first_page_text(path)
                if _title_in_text(all_existing_titles, first_text):
                    skipped_title += 1
                    _save_processed_hash(fhash, processed_hashes)
                    continue

            # PDF 처리
            pdf_result = process_pdf(path)

            if pdf_result.get("is_scan"):
                log_failure(path.name, "스캔 PDF - 텍스트 추출 불가")
                skipped_scan += 1
                continue

            if "error" in pdf_result:
                log_failure(path.name, pdf_result["error"])
                failed += 1
                failed_list.append((path.name, pdf_result["error"]))
                continue

            # AI 분석
            analysis = analyze_pdf(pdf_result)

            if "error" in analysis:
                log_failure(path.name, analysis["error"])
                failed += 1
                failed_list.append((path.name, analysis["error"]))
                continue

            doc_type = analysis.get("type")
            title = analysis.get("title", "").strip()

            # 제목 중복 안전망
            if doc_type == "paper" and title in existing_paper_titles:
                skipped_title += 1
                _save_processed_hash(fhash, processed_hashes)
                continue
            if doc_type == "report" and title in existing_report_titles:
                skipped_title += 1
                _save_processed_hash(fhash, processed_hashes)
                continue

            # 저장
            try:
                save_status = sheets.save_result(analysis)
                if save_status == "saved":
                    if doc_type == "paper":
                        existing_paper_titles.add(title)
                        success_paper += 1
                    else:
                        existing_report_titles.add(title)
                        success_report += 1
                    all_existing_titles.add(title)
                    _save_processed_hash(fhash, processed_hashes)
                elif save_status == "duplicate":
                    skipped_title += 1
                    _save_processed_hash(fhash, processed_hashes)
                else:
                    log_failure(path.name, "save_result error")
                    failed += 1
                    failed_list.append((path.name, "저장 오류"))
            except RuntimeError as e:
                log_failure(path.name, str(e))
                failed += 1
                failed_list.append((path.name, str(e)))

        progress_bar.progress(1.0)
        status_text.write("처리 완료!")

        # 결과 요약
        st.divider()
        st.subheader("처리 결과")
        c1, c2, c3 = st.columns(3)
        c1.metric("논문 저장", success_paper)
        c2.metric("보고서 저장", success_report)
        c3.metric("실패", failed)

        c4, c5, c6 = st.columns(3)
        c4.metric("제목 중복", skipped_title)
        c5.metric("스캔 PDF", skipped_scan)
        c6.metric("캐시 건너뜀", skipped_cache)

        if failed_list:
            with st.expander(f"실패 목록 ({len(failed_list)}개)"):
                for fname, reason in failed_list:
                    st.write(f"- **{fname}**: {reason}")

        st.link_button("Sheets 열기", sheets_url)
