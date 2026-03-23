import hashlib
from pathlib import Path
import fitz  # PyMuPDF
from config import PAGE_SPLIT_THRESHOLD, CHUNK_SIZE, SCAN_PDF_CHAR_THRESHOLD


def collect_pdfs(folder_path: str) -> list[Path]:
    """폴더 내 모든 PDF 파일 경로를 반환한다."""
    folder = Path(folder_path)
    return sorted(folder.rglob("*.pdf"))


def compute_hash(file_path: Path) -> str:
    """파일 MD5 해시를 반환한다."""
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def deduplicate(pdf_paths: list[Path]) -> tuple[list[Path], list[dict]]:
    """
    해시 기반 중복 제거.
    반환: (중복 제거된 파일 목록, 중복으로 건너뛴 파일 정보 목록)
    """
    seen_hashes: dict[str, Path] = {}
    unique: list[Path] = []
    skipped: list[dict] = []

    for path in pdf_paths:
        file_hash = compute_hash(path)
        if file_hash in seen_hashes:
            skipped.append({
                "file": path.name,
                "reason": f"해시 중복 — {seen_hashes[file_hash].name}과 동일",
            })
        else:
            seen_hashes[file_hash] = path
            unique.append(path)

    return unique, skipped


def is_scan_pdf(doc: fitz.Document) -> bool:
    """
    페이지당 평균 추출 글자 수가 임계값 미만이면 스캔 PDF로 판정한다.
    첫 10페이지(또는 전체)만 샘플로 확인한다.
    """
    sample_pages = min(10, len(doc))
    if sample_pages == 0:
        return True

    total_chars = sum(
        len(doc[i].get_text("text")) for i in range(sample_pages)
    )
    avg_chars = total_chars / sample_pages
    return avg_chars < SCAN_PDF_CHAR_THRESHOLD


def extract_text_by_pages(doc: fitz.Document, start: int, end: int) -> str:
    """start 이상 end 미만 페이지 텍스트를 하나의 문자열로 반환한다."""
    texts = []
    for i in range(start, end):
        texts.append(doc[i].get_text("text"))
    return "\n".join(texts)


def get_first_page_text(file_path: Path, max_pages: int = 3) -> str:
    """첫 몇 페이지 텍스트를 소문자로 반환한다 (제목 사전 확인용)."""
    try:
        doc = fitz.open(str(file_path))
        text = ""
        for i in range(min(max_pages, len(doc))):
            text += doc[i].get_text("text")
        doc.close()
        return text.lower()
    except Exception:
        return ""


def process_pdf(file_path: Path) -> dict:
    """
    단일 PDF 파일을 처리하여 텍스트 청크 목록을 반환한다.

    반환 dict 구조:
    {
        "file_path": Path,
        "file_name": str,
        "file_hash": str,
        "page_count": int,
        "is_scan": bool,         # True면 텍스트 추출 불가
        "chunks": [str, ...],    # 텍스트 청크 (100페이지 이상이면 여러 개)
    }
    """
    file_hash = compute_hash(file_path)

    try:
        doc = fitz.open(str(file_path))
    except Exception as e:
        return {
            "file_path": file_path,
            "file_name": file_path.name,
            "file_hash": file_hash,
            "page_count": 0,
            "is_scan": False,
            "chunks": [],
            "error": f"PDF 열기 실패: {e}",
        }

    page_count = len(doc)

    if is_scan_pdf(doc):
        doc.close()
        return {
            "file_path": file_path,
            "file_name": file_path.name,
            "file_hash": file_hash,
            "page_count": page_count,
            "is_scan": True,
            "chunks": [],
        }

    # 100페이지 이상이면 청크 분할
    if page_count >= PAGE_SPLIT_THRESHOLD:
        chunks = []
        for start in range(0, page_count, CHUNK_SIZE):
            end = min(start + CHUNK_SIZE, page_count)
            chunks.append(extract_text_by_pages(doc, start, end))
    else:
        chunks = [extract_text_by_pages(doc, 0, page_count)]

    doc.close()

    return {
        "file_path": file_path,
        "file_name": file_path.name,
        "file_hash": file_hash,
        "page_count": page_count,
        "is_scan": False,
        "chunks": chunks,
    }
