# PaperMind 작업 진행 현황

마지막 업데이트: 2026-03-23

---

## 현재 상태: 배포 완료 ✅

---

## 배포 정보

| 항목 | 내용 |
|------|------|
| GitHub | https://github.com/Johyongjin/PaperMind |
| Streamlit Cloud | https://coop-papermind.streamlit.app |

---

## 2026-03-23 완료 내용

### Streamlit UI 완성 (`app.py`)
5개 탭 구조로 완성:

| 탭 | 기능 |
|---|---|
| 📄 논문 추가 | PDF 업로드 → 논문 강제 분석 → Sheets 저장 |
| 📊 보고서 추가 | PDF 업로드 → 보고서 강제 분석 → Sheets 저장 |
| 📋 전체 목록 | Sheets 데이터 테이블 조회 (4개 시트 서브탭) |
| ⚙️ 배치 처리 | 폴더 일괄 처리, 프로그레스 바, 결과 요약 |
| 🔑 설정 | API 키·서비스 계정·Sheets URL 개인 입력 |

### 다중 사용자 지원
- 설정 탭에서 각자의 Anthropic API 키, Google 서비스 계정 JSON, Sheets URL 입력
- 설정값 우선순위: 설정 탭 입력 > `st.secrets` (Streamlit Cloud) > `.env` (로컬)
- API 키 없이 앱 시작해도 크래시 없이 안내 메시지 표시

### GitHub 배포
- 리포지토리: https://github.com/Johyongjin/PaperMind
- `.env`, `credentials/`, `processed_hashes.json`, `.streamlit/secrets.toml` 모두 gitignore 처리 확인
- `README.md`, `.env.example`, `.streamlit/secrets.toml.example` 포함

### Streamlit Cloud 배포
- URL: https://coop-papermind.streamlit.app
- Secrets 설정: `ANTHROPIC_API_KEY`, `GOOGLE_SHEETS_URL`, `[gcp_service_account]`
- 로컬·배포 환경 모두 테스트 완료

---

## Google Sheets 저장 현황

| 구분 | 수량 |
|------|------|
| 이전 세션 저장 (논문) | 41개 |
| 이전 세션 저장 (보고서) | 1개 |
| 배치 처리 신규 저장 (논문) | 151개 |
| 배치 처리 신규 저장 (보고서) | 16개 |
| **총 저장 합계** | **209개** |

---

## 전체 배치 처리 결과 (마지막 실행 기준)

- 전체 PDF: 283개
- 해시 중복 제거: 7개 → 처리 대상 276개
- 캐시 건너뜀: 91개
- 제목 중복 건너뜀: 3개
- 스캔 PDF (텍스트 추출 불가): 7개
- **성공 저장: 167개**
- **실패: 8개** (JSON 파싱 실패 — 재처리 가능)

---

## 미처리 파일 목록

### 실패 8개 — JSON 파싱 실패 (선택적 재처리)

Claude가 응답을 max_tokens 한도에서 잘라 JSON이 불완전하게 반환됨.
`ai_analyzer.py`의 `max_tokens`를 1500 → 2000으로 올리면 대부분 해결 가능.

| 파일명 |
|--------|
| `@@Boook - Decentralized Finance_ The Impact of Blockchain-Based Financial Innovations on Entrepreneurship.pdf` (196p) |
| `DAO治理框架分析規劃書.pdf` (중국어) |
| `GOV_2014_PRISM_001130.pdf` |
| `KBB_SCHOLAR_협동조합의 협력적 공급사슬 구축 방식 - 아이쿱 생활협동조합의 사례.pdf` |
| `新 가치 창출 디지털 이노베이션 패션 플랫폼 모델 제안.pdf` |
| `블록체인 DAO(분산 자율조직) 현황과 발전 방향 분석.pdf` |
| `토큰 증권 (Security Token) 사업화를 위한 리걸 디자인 (Legal Desig.pdf` |
| `한국협동조합협의회_2017)Guidance notes to the co-operat.pdf` |

### 스캔 PDF 7개 — 텍스트 추출 불가 (재처리 불가)

OCR 도구 없이는 처리 불가. 수동 입력 또는 OCR 적용 필요.

| 파일명 |
|--------|
| `000000031499_01.pdf` |
| `Emerging conversation surrounding DAOs in ASIA.pdf` |
| `부동산 디지털유동화와 감정평가 역할 카사의 DABS 사례를 중심으로.pdf` |
| `블록체인 연구.pdf` |
| `시장 실패의 이론과 시장의 재발견.pdf` |
| `자원순환형 사회를 위한 지역생태산업단지의 개발 전략.pdf` |
| `탈중앙화금융 현황 및 이용 요인에 관한 연구.pdf` |

---

## 다음 단계 (미래 확장)

| 우선순위 | 항목 | 메모 |
|---------|------|------|
| 낮음 | 실패 8개 재처리 | `max_tokens` 2000으로 올려 재시도 |
| 낮음 | 스캔 PDF 7개 | OCR(pytesseract) 또는 수동 입력 |
| 미래 | 지식그래프 추가 | 키워드·저자·인용 관계 네트워크 시각화 (networkx + pyvis) |
| 미래 | 외부 논문 검색 API | Semantic Scholar, CrossRef 연결 |

---

## 주요 파일 현황

| 파일 | 상태 | 설명 |
|------|------|------|
| `modules/pdf_processor.py` | ✅ 완성 | PDF 수집, 해시 중복, 텍스트 추출, 스캔 감지 |
| `modules/ai_analyzer.py` | ✅ 완성 | Claude API 분석, force_type·api_key 파라미터 지원 |
| `modules/sheets_manager.py` | ✅ 완성 | Google Sheets 읽기/쓰기, service_account_info 지원 |
| `modules/logger.py` | ✅ 완성 | 실패 로그 기록 |
| `batch_run.py` | ✅ 완성 | CLI 배치 처리 스크립트 |
| `app.py` | ✅ 완성 | Streamlit 5탭 UI (설정 탭 포함, 다중 사용자 지원) |
| `.streamlit/secrets.toml.example` | ✅ 완성 | Streamlit Cloud secrets 설정 템플릿 |
| `.streamlit/config.toml` | ✅ 완성 | 테마·업로드 크기 설정 |
| `README.md` | ✅ 완성 | 설치·배포 가이드 |
| `.env.example` | ✅ 완성 | 로컬 환경변수 템플릿 |
| `.gitignore` | ✅ 완성 | 민감 파일 전체 제외 확인 |
