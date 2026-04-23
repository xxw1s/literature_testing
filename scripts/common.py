from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INVALID_FILENAME_CHARS = '<>:"/\\|?*'
WHITESPACE_RE = re.compile(r"\s+")
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
STANDARD_RE = re.compile(
    r"\b((?:GB|GB/T|GA|ISO|ASTM)[ _-]?[A-Z0-9.]+(?:[ _-]?\d{4})?)\b",
    re.IGNORECASE,
)


@dataclass
class Settings:
    raw: dict[str, Any]

    @property
    def source_dir(self) -> Path:
        return Path(self.raw["source_dir"])

    @property
    def work_dir(self) -> Path:
        return Path(self.raw["work_dir"])

    @property
    def normalized_dir(self) -> Path:
        return Path(self.raw["normalized_dir"])

    @property
    def recursive(self) -> bool:
        return bool(self.raw.get("recursive", False))


def load_settings(path: str | Path) -> Settings:
    with open(path, "r", encoding="utf-8") as handle:
        return Settings(json.load(handle))


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def find_executable(config_value: str, command_name: str) -> str | None:
    if config_value:
        return config_value
    return shutil.which(command_name)


def run_command(args: list[str], timeout: int = 120) -> tuple[int, str, str]:
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def compute_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def utc_iso_from_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def normalize_text(value: str) -> str:
    cleaned = value.replace("\x00", " ")
    return WHITESPACE_RE.sub(" ", cleaned).strip()


def safe_filename(value: str, max_length: int = 140) -> str:
    value = normalize_text(value)
    if not value:
        value = "untitled"
    for char in INVALID_FILENAME_CHARS:
        value = value.replace(char, "_")
    value = value.rstrip(". ")
    if len(value) > max_length:
        value = value[:max_length].rstrip(" ._")
    return value or "untitled"


def guess_language(text: str) -> str:
    if not text:
        return "unknown"
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_count = len(re.findall(r"[A-Za-z]", text))
    if cjk_count > latin_count:
        return "zh"
    if latin_count > 0:
        return "en"
    return "unknown"


def guess_document_type(name: str, rules: dict[str, list[str]]) -> str:
    lowered = name.lower()
    for doc_type, keywords in rules.items():
        for keyword in keywords:
            if keyword.lower() in lowered:
                return doc_type
    return "journal_or_report"


def extract_year(text: str) -> int | None:
    match = YEAR_RE.search(text)
    return int(match.group(1)) if match else None


def extract_doi(text: str) -> str | None:
    match = DOI_RE.search(text)
    return match.group(0) if match else None


def extract_standard_code(text: str) -> str | None:
    match = STANDARD_RE.search(text)
    if not match:
        return None
    code = match.group(1).upper().replace(" ", "")
    code = code.replace("GBT", "GB/T").replace("GA-", "GA")
    return code


def choose_title(name: str, text_sample: str) -> str:
    stem = Path(name).stem
    if not stem.lower().startswith("1-s2.0-"):
        return stem
    lines = [
        normalize_text(line)
        for line in text_sample.splitlines()
        if normalize_text(line)
    ]
    for line in lines[:20]:
        if 8 <= len(line) <= 220:
            return line
    return stem


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_csv(path: Path, records: list[dict[str, Any]], fieldnames: list[str]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(record)


def keyword_tags(text: str, taxonomy: dict[str, dict[str, list[str]]]) -> dict[str, list[str]]:
    lowered = text.lower()
    result: dict[str, list[str]] = {}
    for dimension, tag_rules in taxonomy.items():
        hits: list[str] = []
        for tag, keywords in tag_rules.items():
            if any(keyword.lower() in lowered for keyword in keywords):
                hits.append(tag)
        result[dimension] = sorted(set(hits))
    return result


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(normalized[start:end])
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks
