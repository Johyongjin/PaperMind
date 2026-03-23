# PaperMind 개발 계획

## 전제 조건 (확인 완료)
- Anthropic API 키 준비됨
- 구글 서비스 계정 JSON 및 Sheets API 준비됨
- 실패 파일: 로그 기록만, 재처리 기능 불필요
- 대용량 PDF: 100페이지 이상 시 분할 처리

---

## 프로젝트 폴더 구조

```
4_PaperMind/
├── app.py                      # Streamlit 메인 앱
├── .env                        # API 키 (gitignore 대상)
├── .gitignore
├── requirements.txt
├── modules/
│   ├── __init__.py
│   ├── pdf_processor.py        # PDF 읽기, 해시 중복 감지, 페이지 분할
│   ├── ai_analyzer.py          # Claude API 호출, 논문/보고서 분석
│   ├── sheets_manager.py       # Google Sheets 읽기/쓰기
│   └── logger.py               # 실패 로그 기록
└── credentials/
    └── service_account.json    # 구글 서비스 계정 (gitignore 대상)
```

---

## 단계별 개발 계획

### 1단계 — 프로젝트 초기 설정
- 폴더 구조 생성
- `requirements.txt` 작성 (streamlit, pymupdf, anthropic, google-api-python-client, python-dotenv 등)
- `.env` 템플릿 및 `.gitignore` 생성
- 각 모듈 파일 빈 껍데기 생성

### 2단계 — PDF 처리 모듈 (`pdf_processor.py`)
- 폴더 내 전체 PDF 파일 목록 수집
- 파일 MD5 해시로 중복 감지
- PyMuPDF로 텍스트 추출
- 100페이지 이상 시 챕터별(또는 균등) 분할
- 스캔 PDF 감지 (텍스트 추출량 기준)

### 3단계 — AI 분석 모듈 (`ai_analyzer.py`)
- Claude API로 논문/보고서 유형 자동 판별
- 논문 정보 추출: APA인용, 제목, 저자, 연도, 저널, 키워드, 연구목적, 연구방법, 연구결과 (한국어)
- 보고서 정보 추출: 인용, 제목, 발행기관, 연도, 키워드, 배경, 주요내용, 시사점 (한국어)
- 100페이지 이상 분할 파일: 각 청크 분석 후 결과 합산

### 4단계 — Google Sheets 모듈 (`sheets_manager.py`)
- 서비스 계정으로 스프레드시트 연결
- 4개 시트 자동 생성/확인 (논문 목록, 논문 상세요약, 보고서 목록, 보고서 상세요약)
- 헤더 자동 설정
- 데이터 행 추가
- 제목 기준 중복 확인 (시트 내 이미 존재하는 제목 체크)
- "새 파일만 추가" 모드용 기처리 파일 목록 조회

### 5단계 — 실패 로거 (`logger.py`)
- 처리 실패 파일 기록 (파일명, 실패 이유, 타임스탬프)
- 로그 파일: `failed_files.log` (텍스트) + `failed_files.csv` (스프레드시트 열람용)
- 실패 유형: 스캔 PDF, API 오류, 텍스트 추출 실패

### 6단계 — Streamlit UI (`app.py`)

4개 탭 구조:

**탭 1 — 논문 추가**
- PDF 파일 업로드 (단일 또는 다중)
- "논문"으로 강제 지정하여 AI 분석 실행
- 처리 결과 인라인 표시 (제목, 저자, APA 인용 등)
- Google Sheets 논문 시트에 저장

**탭 2 — 보고서 추가**
- PDF 파일 업로드 (단일 또는 다중)
- "보고서"로 강제 지정하여 AI 분석 실행
- 처리 결과 인라인 표시 (제목, 발행기관, 키워드 등)
- Google Sheets 보고서 시트에 저장

**탭 3 — 전체 목록**
- 스프레드시트 URL 입력
- 논문 목록 / 보고서 목록 서브탭 전환
- 시트 데이터를 테이블로 표시 (검색/필터 포함)

**탭 4 — 배치 처리**
- 폴더 경로 입력
- 스프레드시트 URL 입력
- 처리 모드 선택 (전체 / 새 파일만)
- 프로그레스 바, 현재 파일명, 성공/실패 카운트 실시간 표시
- 완료 후 결과 요약 및 실패 파일 목록, 스프레드시트 링크

### 7단계 — 로컬 테스트 및 배포
- 소수 PDF로 전체 흐름 테스트 (각 탭)
- 엣지 케이스 확인 (빈 PDF, 스캔 PDF, 100페이지 이상)
- `.gitignore` 확인 (`.env`, `credentials/service_account.json` 포함 여부)
- GitHub 리포지토리 생성 및 푸시
- Streamlit Cloud 배포 (핸드폰 접근 가능)
- README 작성

### 8단계 — 기능 확장 (배포 후)
- **지식그래프 추가**: 논문/보고서 간 키워드·저자·인용 관계 시각화 (networkx + pyvis 또는 Streamlit graph)
- **외부 논문 검색 API 연결**: Semantic Scholar, CrossRef 등으로 논문 메타데이터 자동 보완 및 신규 논문 검색

---

## 주요 기술 결정 사항

| 항목 | 결정 |
|------|------|
| PDF 분할 기준 | 100페이지 이상 시 100페이지 단위 청크로 분할 |
| 중복 감지 순서 | ① 파일 해시 → ② 시트 내 제목 비교 |
| 스캔 PDF 감지 | 추출 텍스트 길이 기준 (페이지당 평균 50자 미만 시 스캔 PDF로 판정) |
| Claude 모델 | claude-sonnet-4-6 |
| 실패 처리 | 로그 기록 후 다음 파일로 계속 진행 |
| 새 파일 모드 | 시트에 이미 있는 파일명/해시 목록과 비교하여 건너뜀 |
| UI 탭 구조 | 논문 추가 / 보고서 추가 / 전체 목록 / 배치 처리 (4탭) |
| 배포 방식 | GitHub + Streamlit Cloud (모바일 접근 가능) |
| .gitignore 필수 항목 | `.env`, `credentials/service_account.json` |
