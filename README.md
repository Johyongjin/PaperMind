# 📚 PaperMind

PDF 논문·보고서를 AI로 자동 분석하여 Google Sheets에 정리해주는 도구입니다.
Claude AI가 논문/보고서를 판별하고, 제목·저자·키워드·요약 등을 추출하여 스프레드시트에 저장합니다.

---

## 주요 기능

| 탭 | 기능 |
|---|---|
| 📄 논문 추가 | PDF 업로드 → 학술 논문으로 분석 → Sheets 저장 |
| 📊 보고서 추가 | PDF 업로드 → 보고서로 분석 → Sheets 저장 |
| 📋 전체 목록 | 저장된 논문·보고서 데이터 테이블 조회 |
| ⚙️ 배치 처리 | 폴더 내 PDF 전체 일괄 분석 및 저장 |

---

## 설치 방법

### 1. 저장소 클론

```bash
git clone https://github.com/YOUR_USERNAME/PaperMind.git
cd PaperMind
```

### 2. 패키지 설치

Python 3.10 이상 권장

```bash
pip install -r requirements.txt
```

### 3. 환경변수 설정

`.env.example`을 복사하여 `.env` 파일을 생성합니다.

```bash
cp .env.example .env
```

`.env` 파일을 열고 아래 세 가지를 입력합니다.

```
ANTHROPIC_API_KEY=sk-ant-api03-...       # Anthropic API 키
GOOGLE_SERVICE_ACCOUNT_PATH=credentials/service_account.json
GOOGLE_SHEETS_URL=https://docs.google.com/spreadsheets/d/.../edit
```

### 4. Google 서비스 계정 설정

1. [Google Cloud Console](https://console.cloud.google.com)에서 프로젝트 생성
2. **Google Sheets API** 활성화
3. **서비스 계정** 생성 → JSON 키 발급
4. 발급받은 JSON 파일을 `credentials/service_account.json` 경로에 저장
5. Google Sheets에서 해당 서비스 계정 이메일을 **편집자**로 공유

### 5. 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속

---

## API 키 발급 방법

### Anthropic API 키
1. [https://console.anthropic.com](https://console.anthropic.com) 접속
2. 로그인 → **API Keys** 메뉴 → **Create Key**
3. 발급된 키를 `.env`의 `ANTHROPIC_API_KEY`에 입력

### Google Sheets API (서비스 계정)
1. [Google Cloud Console](https://console.cloud.google.com) → 새 프로젝트 생성
2. **API 및 서비스 > 라이브러리** → `Google Sheets API` 검색 후 활성화
3. **API 및 서비스 > 사용자 인증 정보** → **서비스 계정 만들기**
4. 서비스 계정 생성 완료 후 → **키 탭** → **키 추가 > JSON** → 다운로드
5. 다운로드한 파일을 `credentials/service_account.json`으로 저장
6. 결과를 저장할 Google Sheets를 열고, 서비스 계정 이메일(`...@...iam.gserviceaccount.com`)을 **편집자**로 공유

---

## 프로젝트 구조

```
PaperMind/
├── app.py                      # Streamlit 메인 앱 (4탭 UI)
├── batch_run.py                # CLI 배치 처리 스크립트
├── config.py                   # 설정값 모음
├── requirements.txt
├── .env                        # API 키 (직접 생성, git 제외)
├── .env.example                # 환경변수 템플릿
├── modules/
│   ├── pdf_processor.py        # PDF 읽기, 해시 중복 감지, 페이지 분할
│   ├── ai_analyzer.py          # Claude API 호출, 논문/보고서 분석
│   ├── sheets_manager.py       # Google Sheets 읽기/쓰기
│   └── logger.py               # 실패 로그 기록
└── credentials/
    └── service_account.json    # Google 서비스 계정 (직접 저장, git 제외)
```

---

## 분석 결과 형식

### 논문 (Google Sheets — "논문 목록" / "논문 상세요약")

| 필드 | 설명 |
|---|---|
| APA 인용 | APA 7th 형식 전체 인용문 |
| 제목 | 논문 제목 |
| 저자 | 저자명 (쉼표 구분) |
| 연도 | 출판연도 |
| 저널 | 저널/학회명 |
| 키워드 | 핵심 키워드 5개 이내 |
| 연구목적 | 연구 배경 및 목표 요약 (한국어) |
| 연구방법 | 연구 설계·데이터·분석 방법 요약 (한국어) |
| 연구결과 | 주요 발견 및 결론 요약 (한국어) |

### 보고서 (Google Sheets — "보고서 목록" / "보고서 상세요약")

| 필드 | 설명 |
|---|---|
| 인용 | 발행기관. (연도). 제목. 형식 |
| 제목 | 보고서 제목 |
| 발행기관 | 기관명 |
| 연도 | 발행연도 |
| 키워드 | 핵심 키워드 5개 이내 |
| 배경 | 작성 배경 및 목적 요약 (한국어) |
| 주요내용 | 핵심 내용 요약 (한국어) |
| 시사점 | 주요 시사점 및 제언 요약 (한국어) |

---

## 주의 사항

- **스캔 PDF** (이미지 기반)는 텍스트 추출이 불가하여 건너뜁니다.
- **100페이지 이상** PDF는 100페이지 단위로 분할하여 분석합니다.
- API 호출 제한(Rate Limit) 방지를 위해 파일당 약 20초 간격이 적용됩니다.
- 실패한 파일은 `failed_files.log` 및 `failed_files.csv`에 기록됩니다.
- `.env`와 `credentials/service_account.json`은 절대 git에 커밋하지 마세요.

---

## 사용 기술

- [Streamlit](https://streamlit.io) — 웹 UI
- [Claude API (Anthropic)](https://www.anthropic.com) — AI 분석 (claude-sonnet-4-6)
- [PyMuPDF](https://pymupdf.readthedocs.io) — PDF 텍스트 추출
- [Google Sheets API](https://developers.google.com/sheets/api) — 스프레드시트 연동
