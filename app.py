import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from config import ANTHROPIC_API_KEY, GOOGLE_SERVICE_ACCOUNT_PATH, GOOGLE_SHEETS_URL
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

# ── 설정 헬퍼 ─────────────────────────────────────────────────────────────────
# 우선순위: 설정 탭 입력값 > .env 기본값

def _cfg_api_key() -> str:
    return st.session_state.get("cfg_api_key") or ANTHROPIC_API_KEY or ""

def _cfg_sa_info() -> dict | None:
    return st.session_state.get("cfg_sa_info")  # 업로드된 서비스 계정 JSON dict

def _cfg_sheets_url() -> str:
    return st.session_state.get("cfg_sheets_url") or GOOGLE_SHEETS_URL or ""

def _is_ready() -> bool:
    """분석 실행에 필요한 설정이 모두 갖춰졌는지 확인한다."""
    has_sa = bool(_cfg_sa_info()) or Path(GOOGLE_SERVICE_ACCOUNT_PATH).exists()
    return bool(_cfg_api_key()) and has_sa and bool(_cfg_sheets_url())

def _make_sheets(url: str = None) -> SheetsManager:
    """설정 탭 값을 우선 사용하여 SheetsManager를 생성한다."""
    return SheetsManager(
        sheets_url=url or _cfg_sheets_url(),
        service_account_info=_cfg_sa_info(),  # None이면 파일 경로 fallback
    )


# ── 처리 헬퍼 ─────────────────────────────────────────────────────────────────

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
        st.write("**연구목적**"); st.write(analysis.get("research_purpose", ""))
        st.write("**연구방법**"); st.write(analysis.get("research_method", ""))
        st.write("**연구결과**"); st.write(analysis.get("research_result", ""))


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
        st.write("**배경**"); st.write(analysis.get("background", ""))
        st.write("**주요내용**"); st.write(analysis.get("main_content", ""))
        st.write("**시사점**"); st.write(analysis.get("implications", ""))


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
        json.dumps(list(processed_hashes), ensure_ascii=False), encoding="utf-8"
    )


def _title_in_text(titles: set, text: str) -> bool:
    text_lower = text.lower()
    return any(len(t) >= 15 and t.lower() in text_lower for t in titles)


def _process_and_save(upf, force_type: str, sheets: SheetsManager):
    """업로드 파일 1개를 처리하고 저장한다. (논문/보고서 공통)
    반환: ("saved"|"duplicate"|"scan"|"error", result_data)
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

        analysis = analyze_pdf(pdf_result, force_type=force_type, api_key=_cfg_api_key() or None)

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

# ── 사이드바: 연결 상태 요약 ──────────────────────────────────────────────────

with st.sidebar:
    st.header("연결 상태")

    api_ok = bool(_cfg_api_key())
    sa_ok  = bool(_cfg_sa_info()) or Path(GOOGLE_SERVICE_ACCOUNT_PATH).exists()
    url_ok = bool(_cfg_sheets_url())

    st.write("Anthropic API 키", "✅" if api_ok else "❌ 미설정")
    st.write("Google 서비스 계정", "✅" if sa_ok else "❌ 미설정")
    st.write("Sheets URL", "✅" if url_ok else "❌ 미설정")

    if not _is_ready():
        st.warning("🔑 설정 탭에서 연결 정보를 입력하세요.")
    else:
        st.success("모든 설정 완료")


# ── 탭 ───────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📄 논문 추가", "📊 보고서 추가", "📋 전체 목록", "⚙️ 배치 처리", "🔑 설정"]
)


# ══════════════════════════════════════════════════════════════════════════════
# 탭 5: 설정 (먼저 구현 — 나머지 탭이 의존함)
# ══════════════════════════════════════════════════════════════════════════════

with tab5:
    st.subheader("연결 설정")
    st.caption("각자의 API 키와 Google 서비스 계정을 입력하세요. 입력값은 이 세션 동안만 유지됩니다.")

    st.divider()

    # ── Anthropic API 키 ─────────────────────────────────────────────────────
    st.markdown("#### 1. Anthropic API 키")
    st.caption("https://console.anthropic.com 에서 발급")

    api_key_input = st.text_input(
        "API 키",
        value=st.session_state.get("cfg_api_key", ""),
        type="password",
        placeholder="sk-ant-api03-...",
        label_visibility="collapsed",
    )

    st.divider()

    # ── Google 서비스 계정 JSON ───────────────────────────────────────────────
    st.markdown("#### 2. Google 서비스 계정 JSON")
    st.caption("Google Cloud Console → 서비스 계정 → 키 발급 → JSON 다운로드")

    uploaded_sa = st.file_uploader(
        "service_account.json 업로드",
        type="json",
        label_visibility="collapsed",
    )

    if uploaded_sa:
        try:
            sa_info = json.load(uploaded_sa)
            if "client_email" not in sa_info:
                st.error("올바른 서비스 계정 JSON이 아닙니다.")
                sa_info = None
            else:
                st.success(f"서비스 계정 인식됨: `{sa_info.get('client_email', '')}`")
        except Exception:
            st.error("JSON 파싱 실패. 올바른 파일인지 확인하세요.")
            sa_info = None
    else:
        sa_info = st.session_state.get("cfg_sa_info")
        if sa_info:
            st.info(f"현재 설정된 계정: `{sa_info.get('client_email', '')}`")
        elif Path(GOOGLE_SERVICE_ACCOUNT_PATH).exists():
            st.info(f"로컬 파일 사용 중: `{GOOGLE_SERVICE_ACCOUNT_PATH}`")
        else:
            st.warning("서비스 계정 JSON을 업로드하세요.")

    st.divider()

    # ── Google Sheets URL ────────────────────────────────────────────────────
    st.markdown("#### 3. Google Sheets URL")
    st.caption("결과를 저장할 스프레드시트 URL. 서비스 계정 이메일을 편집자로 공유해야 합니다.")

    sheets_url_input = st.text_input(
        "Sheets URL",
        value=st.session_state.get("cfg_sheets_url", GOOGLE_SHEETS_URL or ""),
        placeholder="https://docs.google.com/spreadsheets/d/...",
        label_visibility="collapsed",
    )

    st.divider()

    # ── 저장 버튼 ────────────────────────────────────────────────────────────
    if st.button("설정 저장", type="primary", use_container_width=True):
        st.session_state["cfg_api_key"]   = api_key_input.strip()
        st.session_state["cfg_sheets_url"] = sheets_url_input.strip()
        if sa_info:
            st.session_state["cfg_sa_info"] = sa_info

        missing = []
        if not api_key_input.strip():
            missing.append("Anthropic API 키")
        if not (sa_info or st.session_state.get("cfg_sa_info") or Path(GOOGLE_SERVICE_ACCOUNT_PATH).exists()):
            missing.append("Google 서비스 계정 JSON")
        if not sheets_url_input.strip():
            missing.append("Sheets URL")

        if missing:
            st.warning(f"아직 미입력: {', '.join(missing)}")
        else:
            st.success("설정이 저장됐습니다. 다른 탭에서 분석을 시작할 수 있습니다.")
            st.rerun()

    # ── 연결 테스트 ──────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 연결 테스트")

    if st.button("Sheets 연결 테스트", disabled=not (url_ok and sa_ok)):
        try:
            with st.spinner("연결 중..."):
                sheets = _make_sheets()
            st.success("Google Sheets 연결 성공!")
        except Exception as e:
            st.error(f"연결 실패: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# 탭 1: 논문 추가
# ══════════════════════════════════════════════════════════════════════════════

with tab1:
    st.subheader("논문 추가")
    st.caption("업로드한 PDF를 학술 논문으로 분석하여 Sheets에 저장합니다.")

    if not _is_ready():
        st.warning("🔑 설정 탭에서 API 키, 서비스 계정, Sheets URL을 먼저 입력하세요.")
    else:
        paper_files = st.file_uploader(
            "PDF 파일 선택", type="pdf", accept_multiple_files=True, key="paper_uploader"
        )

        if paper_files:
            st.info(f"{len(paper_files)}개 파일 선택됨")

        if st.button("분석 및 저장", key="paper_run", disabled=not paper_files):
            try:
                sheets = _make_sheets()
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

    if not _is_ready():
        st.warning("🔑 설정 탭에서 API 키, 서비스 계정, Sheets URL을 먼저 입력하세요.")
    else:
        report_files = st.file_uploader(
            "PDF 파일 선택", type="pdf", accept_multiple_files=True, key="report_uploader"
        )

        if report_files:
            st.info(f"{len(report_files)}개 파일 선택됨")

        if st.button("분석 및 저장", key="report_run", disabled=not report_files):
            try:
                sheets = _make_sheets()
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

    if not (sa_ok and url_ok):
        st.warning("🔑 설정 탭에서 서비스 계정과 Sheets URL을 먼저 입력하세요.")
    else:
        if st.button("데이터 불러오기", key="list_load"):
            try:
                sheets = _make_sheets()
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

    if not _is_ready():
        st.warning("🔑 설정 탭에서 API 키, 서비스 계정, Sheets URL을 먼저 입력하세요.")
    else:
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

        if st.button("배치 처리 시작", key="batch_run", disabled=not folder_valid):
            try:
                sheets = _make_sheets()
            except Exception as e:
                st.error(f"Sheets 연결 실패: {e}")
                st.stop()

            all_pdfs = collect_pdfs(folder_input)
            unique_pdfs, hash_dupes = deduplicate(all_pdfs)

            st.info(
                f"발견: **{len(all_pdfs)}**개 / 해시 중복: **{len(hash_dupes)}**개 / "
                f"처리 대상: **{len(unique_pdfs)}**개"
            )

            existing_paper_titles  = sheets.get_existing_titles("paper")
            existing_report_titles = sheets.get_existing_titles("report")
            all_existing_titles    = existing_paper_titles | existing_report_titles

            processed_hashes = (
                _load_processed_hashes()
                if batch_mode == "새 파일만 (캐시 기반)"
                else set()
            )

            total = len(unique_pdfs)
            progress_bar = st.progress(0)
            status_text  = st.empty()

            success_paper = 0
            success_report = 0
            skipped_cache = 0
            skipped_title = 0
            skipped_scan  = 0
            failed = 0
            failed_list = []

            for idx, path in enumerate(unique_pdfs):
                progress_bar.progress((idx + 1) / total)
                status_text.write(f"[{idx + 1}/{total}] {path.name}")

                fhash = compute_hash(path)
                if batch_mode == "새 파일만 (캐시 기반)" and fhash in processed_hashes:
                    skipped_cache += 1
                    continue

                if all_existing_titles:
                    first_text = get_first_page_text(path)
                    if _title_in_text(all_existing_titles, first_text):
                        skipped_title += 1
                        _save_processed_hash(fhash, processed_hashes)
                        continue

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

                analysis = analyze_pdf(
                    pdf_result, api_key=_cfg_api_key() or None
                )

                if "error" in analysis:
                    log_failure(path.name, analysis["error"])
                    failed += 1
                    failed_list.append((path.name, analysis["error"]))
                    continue

                doc_type = analysis.get("type")
                title    = analysis.get("title", "").strip()

                if doc_type == "paper" and title in existing_paper_titles:
                    skipped_title += 1
                    _save_processed_hash(fhash, processed_hashes)
                    continue
                if doc_type == "report" and title in existing_report_titles:
                    skipped_title += 1
                    _save_processed_hash(fhash, processed_hashes)
                    continue

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

            st.link_button("Sheets 열기", _cfg_sheets_url())
