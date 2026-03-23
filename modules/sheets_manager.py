from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from config import (
    GOOGLE_SERVICE_ACCOUNT_PATH, GOOGLE_SHEETS_URL, GOOGLE_SCOPES,
    SHEET_PAPER_LIST, SHEET_PAPER_DETAIL,
    SHEET_REPORT_LIST, SHEET_REPORT_DETAIL,
    PAPER_LIST_HEADERS, PAPER_DETAIL_HEADERS,
    REPORT_LIST_HEADERS, REPORT_DETAIL_HEADERS,
)


def _extract_sheet_id(url: str) -> str:
    return url.split("/d/")[1].split("/")[0]


def _get_service():
    creds = Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_PATH, scopes=GOOGLE_SCOPES
    )
    return build("sheets", "v4", credentials=creds)


class SheetsManager:
    def __init__(self, sheets_url: str = None):
        self.service = _get_service()
        self.sheet_id = _extract_sheet_id(sheets_url or GOOGLE_SHEETS_URL)
        self._ensure_sheets()

    # ── 내부 유틸 ──────────────────────────────────────────────────────────

    def _get_existing_sheet_names(self) -> list[str]:
        meta = self.service.spreadsheets().get(spreadsheetId=self.sheet_id).execute()
        return [s["properties"]["title"] for s in meta.get("sheets", [])]

    def _ensure_sheets(self):
        """4개 시트가 없으면 생성하고 헤더를 입력한다."""
        existing = self._get_existing_sheet_names()
        configs = [
            (SHEET_PAPER_LIST,   PAPER_LIST_HEADERS),
            (SHEET_PAPER_DETAIL, PAPER_DETAIL_HEADERS),
            (SHEET_REPORT_LIST,  REPORT_LIST_HEADERS),
            (SHEET_REPORT_DETAIL,REPORT_DETAIL_HEADERS),
        ]

        to_create = [(name, headers) for name, headers in configs if name not in existing]
        if not to_create:
            return

        # 시트 생성
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": name}}} for name, _ in to_create]}
        ).execute()

        # 헤더 입력
        self.service.spreadsheets().values().batchUpdate(
            spreadsheetId=self.sheet_id,
            body={
                "valueInputOption": "RAW",
                "data": [{"range": f"'{name}'!A1", "values": [headers]} for name, headers in to_create]
            }
        ).execute()

    def _get_column_values(self, sheet_name: str, col: str) -> set[str]:
        """시트에서 특정 열의 값을 집합으로 반환한다."""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=f"'{sheet_name}'!{col}2:{col}"
            ).execute()
            return {row[0].strip() for row in result.get("values", []) if row}
        except Exception:
            return set()

    def _next_number(self, sheet_name: str) -> int:
        """시트의 다음 # 번호를 반환한다."""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=f"'{sheet_name}'!A2:A"
            ).execute()
            return len(result.get("values", [])) + 1
        except Exception:
            return 1

    def _append_rows(self, sheet_name: str, row: list):
        self.service.spreadsheets().values().append(
            spreadsheetId=self.sheet_id,
            range=f"'{sheet_name}'!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]}
        ).execute()

    # ── 공개 API ────────────────────────────────────────────────────────────

    def get_existing_titles(self, doc_type: str) -> set[str]:
        """이미 저장된 제목 목록을 반환한다 (중복 확인용)."""
        sheet = SHEET_PAPER_LIST if doc_type == "paper" else SHEET_REPORT_LIST
        return self._get_column_values(sheet, "C")

    def get_processed_hashes(self) -> set[str]:
        """
        '새 파일만 추가' 모드용: 시트에 저장된 파일 해시 목록 반환.
        해시는 시트에 직접 저장하지 않으므로, 제목 기반 중복 확인으로 대체한다.
        (파일 해시 비교는 pdf_processor.deduplicate()에서 처리)
        """
        return set()

    def get_sheet_data(self, sheet_name: str) -> list:
        """시트의 모든 데이터를 반환한다 (헤더 포함)."""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=f"'{sheet_name}'!A1:Z"
            ).execute()
            return result.get("values", [])
        except Exception:
            return []

    def save_result(self, analysis: dict) -> str:
        """
        분석 결과를 적절한 시트에 저장한다.
        반환값: "saved" | "duplicate" | "error"
        """
        if "error" in analysis:
            return "error"

        doc_type = analysis.get("type")
        title = analysis.get("title", "").strip()

        try:
            if doc_type == "paper":
                if title in self.get_existing_titles("paper"):
                    return "duplicate"
                num = self._next_number(SHEET_PAPER_LIST)
                self._append_rows(SHEET_PAPER_LIST, [
                    num,
                    analysis.get("apa_citation", ""),
                    title,
                    analysis.get("authors", ""),
                    analysis.get("year", ""),
                    analysis.get("journal", ""),
                    analysis.get("keywords", ""),
                ])
                self._append_rows(SHEET_PAPER_DETAIL, [
                    num,
                    title,
                    analysis.get("research_purpose", ""),
                    analysis.get("research_method", ""),
                    analysis.get("research_result", ""),
                ])

            elif doc_type == "report":
                if title in self.get_existing_titles("report"):
                    return "duplicate"
                num = self._next_number(SHEET_REPORT_LIST)
                self._append_rows(SHEET_REPORT_LIST, [
                    num,
                    analysis.get("citation", ""),
                    title,
                    analysis.get("institution", ""),
                    analysis.get("year", ""),
                    analysis.get("keywords", ""),
                ])
                self._append_rows(SHEET_REPORT_DETAIL, [
                    num,
                    title,
                    analysis.get("background", ""),
                    analysis.get("main_content", ""),
                    analysis.get("implications", ""),
                ])

            else:
                return "error"

            return "saved"

        except Exception as e:
            raise RuntimeError(f"시트 저장 실패: {e}")
