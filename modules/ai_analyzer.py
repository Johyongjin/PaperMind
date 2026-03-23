import json
import time
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

MAX_CHARS_PER_CHUNK = 15000  # 청크당 최대 전달 글자 수
CALL_INTERVAL = 20           # API 호출 간 대기 시간 (Rate Limit 방지)
RATE_LIMIT_WAIT = 65         # Rate Limit 발생 시 대기 시간 (초)

PAPER_FORCED_PROMPT = """다음 문서는 학술 논문입니다. 아래 JSON 형식으로만 반환하세요.

{{
  "type": "paper",
  "apa_citation": "APA 7th 형식 전체 인용문",
  "title": "논문 제목",
  "authors": "저자명 (여러 명이면 쉼표 구분)",
  "year": "출판연도",
  "journal": "저널/학회명",
  "keywords": "핵심 키워드 5개 이내, 쉼표 구분",
  "research_purpose": "연구 수행 이유와 목표. 핵심만 담아 5~7문장 이내. 한국어.",
  "research_method": "연구 설계·데이터·분석 방법. 핵심만 담아 5~7문장 이내. 한국어.",
  "research_result": "주요 발견과 결론. 핵심만 담아 5~7문장 이내. 한국어."
}}

규칙:
- 각 서술 필드는 반드시 5~7문장 이내로 작성하세요.
- 정보를 찾을 수 없는 필드는 "정보 없음"으로 작성하세요.
- 마크다운 코드블록 없이 순수 JSON만 반환하세요.

문서 텍스트:
{text}
"""

REPORT_FORCED_PROMPT = """다음 문서는 보고서입니다. 아래 JSON 형식으로만 반환하세요.

{{
  "type": "report",
  "citation": "인용 형식 (발행기관. (발행연도). 제목.)",
  "title": "보고서 제목",
  "institution": "발행기관명",
  "year": "발행연도",
  "keywords": "핵심 키워드 5개 이내, 쉼표 구분",
  "background": "보고서 작성 배경과 목적. 핵심만 담아 5~7문장 이내. 한국어.",
  "main_content": "핵심 내용 요약. 핵심만 담아 5~7문장 이내. 한국어.",
  "implications": "주요 시사점과 제언. 핵심만 담아 5~7문장 이내. 한국어."
}}

규칙:
- 각 서술 필드는 반드시 5~7문장 이내로 작성하세요.
- 정보를 찾을 수 없는 필드는 "정보 없음"으로 작성하세요.
- 마크다운 코드블록 없이 순수 JSON만 반환하세요.

문서 텍스트:
{text}
"""

ANALYSIS_PROMPT = """다음 문서를 분석하여 JSON 형식으로만 반환하세요.

문서 유형을 먼저 판단하세요:
- "paper": 학술 논문 (연구자 저자, 저널/학회 게재)
- "report": 보고서 (기관/기업 발행, 정책·산업·연구 보고서)

[논문인 경우 반환 형식]
{{
  "type": "paper",
  "apa_citation": "APA 7th 형식 전체 인용문",
  "title": "논문 제목",
  "authors": "저자명 (여러 명이면 쉼표 구분)",
  "year": "출판연도",
  "journal": "저널/학회명",
  "keywords": "핵심 키워드 5개 이내, 쉼표 구분",
  "research_purpose": "연구 수행 이유와 목표. 핵심만 담아 5~7문장 이내. 한국어.",
  "research_method": "연구 설계·데이터·분석 방법. 핵심만 담아 5~7문장 이내. 한국어.",
  "research_result": "주요 발견과 결론. 핵심만 담아 5~7문장 이내. 한국어."
}}

[보고서인 경우 반환 형식]
{{
  "type": "report",
  "citation": "인용 형식 (발행기관. (발행연도). 제목.)",
  "title": "보고서 제목",
  "institution": "발행기관명",
  "year": "발행연도",
  "keywords": "핵심 키워드 5개 이내, 쉼표 구분",
  "background": "보고서 작성 배경과 목적. 핵심만 담아 5~7문장 이내. 한국어.",
  "main_content": "핵심 내용 요약. 핵심만 담아 5~7문장 이내. 한국어.",
  "implications": "주요 시사점과 제언. 핵심만 담아 5~7문장 이내. 한국어."
}}

규칙:
- 각 서술 필드는 반드시 5~7문장 이내로 작성하세요.
- 정보를 찾을 수 없는 필드는 "정보 없음"으로 작성하세요.
- 마크다운 코드블록 없이 순수 JSON만 반환하세요.

문서 텍스트:
{text}
"""

SUPPLEMENT_PROMPT = """다음은 긴 문서의 추가 섹션입니다. 아래 필드를 보완하여 JSON으로만 반환하세요.
문서 유형: {doc_type}

{fields}

규칙:
- 각 필드는 3문장 이내로 핵심만 작성하세요.
- 내용이 없으면 빈 문자열("")로 반환하세요.
- 마크다운 코드블록 없이 순수 JSON만 반환하세요.

추가 텍스트:
{text}
"""

PAPER_SUPPLEMENT_FIELDS = """{
  "research_purpose": "추가 연구목적 (없으면 빈 문자열)",
  "research_method": "추가 연구방법 (없으면 빈 문자열)",
  "research_result": "추가 연구결과 (없으면 빈 문자열)"
}"""

REPORT_SUPPLEMENT_FIELDS = """{
  "background": "추가 배경 (없으면 빈 문자열)",
  "main_content": "추가 주요내용 (없으면 빈 문자열)",
  "implications": "추가 시사점 (없으면 빈 문자열)"
}"""


def _parse_json(raw: str) -> dict:
    """Claude 응답에서 JSON을 파싱한다. 코드블록 포함 시 제거."""
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _call_claude(prompt: str, max_tokens: int = 1500) -> dict:
    """Rate Limit 발생 시 자동 재시도한다."""
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            time.sleep(CALL_INTERVAL)  # 호출 간 간격 유지
            return _parse_json(response.content[0].text)
        except anthropic.RateLimitError:
            if attempt < 2:
                print(f"\n  Rate Limit 대기 중 ({RATE_LIMIT_WAIT}초)...", end=" ", flush=True)
                time.sleep(RATE_LIMIT_WAIT)
            else:
                raise


def _merge_supplement(base: dict, supplement: dict) -> dict:
    """추가 청크 분석 결과를 기본 결과에 병합한다."""
    merged = base.copy()
    if base["type"] == "paper":
        fields = ["research_purpose", "research_method", "research_result"]
    else:
        fields = ["background", "main_content", "implications"]

    for field in fields:
        extra = supplement.get(field, "").strip()
        if extra:
            existing = merged.get(field, "")
            if not existing or existing == "정보 없음":
                merged[field] = extra
            else:
                merged[field] = f"{existing} {extra}"
    return merged


def analyze_pdf(pdf_result: dict, force_type: str = None) -> dict:
    """
    process_pdf() 결과를 받아 Claude API로 분석한다.

    force_type: "paper" 또는 "report" 지정 시 해당 유형으로 강제 분석.
                None이면 Claude가 유형을 자동 판별.

    반환 dict:
    - 성공: {"file_name", "file_hash", "type", ...추출 필드...}
    - 실패: {"file_name", "error": "이유"}
    """
    file_name = pdf_result.get("file_name", "")

    if pdf_result.get("is_scan"):
        return {"file_name": file_name, "error": "스캔 PDF — 텍스트 추출 불가"}

    if "error" in pdf_result:
        return {"file_name": file_name, "error": pdf_result["error"]}

    chunks = pdf_result.get("chunks", [])
    if not chunks or not chunks[0].strip():
        return {"file_name": file_name, "error": "추출된 텍스트 없음"}

    try:
        # 첫 번째 청크로 전체 분석
        if force_type == "paper":
            prompt = PAPER_FORCED_PROMPT.format(text=chunks[0][:MAX_CHARS_PER_CHUNK])
        elif force_type == "report":
            prompt = REPORT_FORCED_PROMPT.format(text=chunks[0][:MAX_CHARS_PER_CHUNK])
        else:
            prompt = ANALYSIS_PROMPT.format(text=chunks[0][:MAX_CHARS_PER_CHUNK])

        result = _call_claude(prompt)
        result["file_name"] = file_name
        result["file_hash"] = pdf_result.get("file_hash", "")

        # 추가 청크 보완 처리
        doc_type = result.get("type", "paper")
        fields_template = PAPER_SUPPLEMENT_FIELDS if doc_type == "paper" else REPORT_SUPPLEMENT_FIELDS

        for chunk in chunks[1:]:
            supplement = _call_claude(
                SUPPLEMENT_PROMPT.format(
                    doc_type=doc_type,
                    fields=fields_template,
                    text=chunk[:MAX_CHARS_PER_CHUNK]
                ),
                max_tokens=600
            )
            result = _merge_supplement(result, supplement)

        return result

    except json.JSONDecodeError as e:
        return {"file_name": file_name, "error": f"JSON 파싱 실패: {e}"}
    except Exception as e:
        return {"file_name": file_name, "error": f"API 호출 실패: {e}"}
