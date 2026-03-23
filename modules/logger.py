import csv
from datetime import datetime
from pathlib import Path

LOG_FILE = Path("failed_files.log")
CSV_FILE = Path("failed_files.csv")


def log_failure(file_name: str, reason: str):
    """실패 파일을 .log 및 .csv에 기록한다."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {file_name} | {reason}\n")

    file_exists = CSV_FILE.exists()
    with open(CSV_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["타임스탬프", "파일명", "실패 이유"])
        writer.writerow([timestamp, file_name, reason])
