import os
from dotenv import load_dotenv

load_dotenv()

# API 키
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_SERVICE_ACCOUNT_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials/service_account.json")
GOOGLE_SHEETS_URL = os.getenv("GOOGLE_SHEETS_URL")

# PDF 처리 설정
PAGE_SPLIT_THRESHOLD = 100       # 이 페이지 수 이상이면 분할 처리
CHUNK_SIZE = 100                 # 분할 시 청크당 페이지 수
SCAN_PDF_CHAR_THRESHOLD = 50    # 페이지당 평균 글자 수가 이 값 미만이면 스캔 PDF로 판정

# Claude 모델
CLAUDE_MODEL = "claude-sonnet-4-6"

# 구글 스프레드시트 시트 이름
SHEET_PAPER_LIST = "논문 목록"
SHEET_PAPER_DETAIL = "논문 상세요약"
SHEET_REPORT_LIST = "보고서 목록"
SHEET_REPORT_DETAIL = "보고서 상세요약"

# 시트 헤더
PAPER_LIST_HEADERS = ["#", "APA 인용", "제목", "저자", "연도", "저널", "키워드"]
PAPER_DETAIL_HEADERS = ["#", "제목", "연구목적", "연구방법", "연구결과"]
REPORT_LIST_HEADERS = ["#", "인용", "제목", "발행기관", "연도", "키워드"]
REPORT_DETAIL_HEADERS = ["#", "제목", "배경", "주요내용", "시사점"]

# 구글 API 스코프
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]
