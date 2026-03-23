# PaperMind 작업 진행 현황

마지막 업데이트: 2026-03-23

---

## 현재 상태: Streamlit UI 완성 — 로컬 테스트 단계

---

## Google Sheets 저장 현황

| 구분 | 수량 |
|------|------|
| 이전 세션 저장 (논문) | 41개 |
| 이전 세션 저장 (보고서) | 1개 |
| 이번 세션 신규 저장 (논문) | 151개 |
| 이번 세션 신규 저장 (보고서) | 16개 |
| **총 저장 합계** | **209개** |

---

## 전체 배치 처리 결과 (마지막 실행 기준)

- 전체 PDF: 283개
- 해시 중복 제거: 7개 → 처리 대상 276개
- 캐시 건너뜀: 91개 (이전 실행에서 처리 완료된 파일)
- 제목 중복 건너뜀: 3개
- 스캔 PDF (텍스트 추출 불가): 7개
- **성공 저장: 167개**
- **실패: 8개**

---

## 미처리 파일 목록

### 실패 8개 — JSON 파싱 실패 (재처리 가능)

Claude가 응답을 max_tokens 한도에서 잘라 JSON이 불완전하게 반환됨.
`max_tokens`를 늘려 재시도하면 대부분 해결 가능.

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

## 다음 세션에서 할 일

### 우선순위 1 — Streamlit UI 완성 (`app.py`)
4개 탭 구조로 개발 (PLAN.md 6단계 참고):
- **논문 추가 탭**: PDF 업로드 → 논문으로 강제 처리 → Sheets 저장
- **보고서 추가 탭**: PDF 업로드 → 보고서로 강제 처리 → Sheets 저장
- **전체 목록 탭**: Sheets 데이터 테이블 표시 (논문/보고서 서브탭)
- **배치 처리 탭**: 폴더 경로 입력, 프로그레스 바, 결과 요약

### 우선순위 2 — 로컬 테스트
- 각 탭 기능 검증
- 엣지 케이스 (스캔 PDF, 100페이지 이상, 빈 PDF)

### 우선순위 3 — GitHub 배포
- `.gitignore` 확인: `.env`, `credentials/service_account.json` 반드시 포함
- GitHub 리포지토리 생성 및 푸시
- Streamlit Cloud 배포 → 핸드폰에서 접근 가능

### 우선순위 4 — 기능 확장 (배포 후)
- **지식그래프**: 논문/보고서 간 키워드·저자·인용 관계 시각화
- **외부 논문 검색 API**: Semantic Scholar, CrossRef 등 연결

### 잔여 미처리 파일 (별도 우선순위)
- JSON 파싱 실패 8개: `max_tokens` 1500 → 2000 후 재처리 가능
- 스캔 PDF 7개: OCR 또는 수동 입력 필요 (낮은 우선순위)

---

## 주요 파일 현황

| 파일 | 상태 | 설명 |
|------|------|------|
| `modules/pdf_processor.py` | 완성 | PDF 수집, 해시 중복, 텍스트 추출, 스캔 감지 |
| `modules/ai_analyzer.py` | 완성 | Claude API 분석 (논문/보고서 판별) |
| `modules/sheets_manager.py` | 완성 | Google Sheets 읽기/쓰기 |
| `modules/logger.py` | 완성 | 실패 로그 기록 |
| `batch_run.py` | 완성 | 전체 배치 처리 (캐시, 제목 매칭 사전 필터 포함) |
| `processed_hashes.json` | 생성됨 | 처리 완료 파일 해시 캐시 (276개) |
| `failed_files.log/.csv` | 생성됨 | 실패 파일 목록 |
| `app.py` | **완성** | Streamlit UI — 4탭 구조 (논문 추가/보고서 추가/전체 목록/배치 처리) |
| `.gitignore` | **확인 완료** | `.env`, `credentials/`, `processed_hashes.json` 포함됨 |
