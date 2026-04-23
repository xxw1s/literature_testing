from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from shutil import which

from common import (
    chunk_text,
    ensure_dir,
    extract_doi,
    keyword_tags,
    load_settings,
    normalize_text,
    read_jsonl,
    run_command,
    write_csv,
    write_jsonl,
)


AUTHOR_LINE_RE = re.compile(r"^[A-Z][A-Za-z .,\-]{3,120}$")


def extract_full_text(pdftotext_exe: str | None, pdf_path: Path) -> tuple[str, str | None]:
    if not pdftotext_exe:
        return "", "pdftotext_not_found"
    code, stdout, stderr = run_command(
        [pdftotext_exe, "-enc", "UTF-8", str(pdf_path), "-"],
        timeout=300,
    )
    if code != 0:
        return stdout, stderr.strip() or "pdftotext_failed"
    return stdout, None


def first_meaningful_lines(text: str, limit: int = 20) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = normalize_text(raw)
        if line:
            lines.append(line)
        if len(lines) >= limit:
            break
    return lines


def extract_title_author(lines: list[str]) -> tuple[str | None, str | None]:
    title = lines[0] if lines else None
    author = None
    for line in lines[1:8]:
        if AUTHOR_LINE_RE.match(line):
            author = line
            break
    return title, author


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "config" / "settings.json"))
    args = parser.parse_args()

    settings = load_settings(args.config)
    pdftotext_exe = settings.raw.get("pdftotext_exe") or which("pdftotext")

    manifest_records = {item["doc_id"]: item for item in read_jsonl(settings.work_dir / "manifest" / "manifest.jsonl")}
    rename_map = read_jsonl(settings.work_dir / "dedupe" / "rename_map.jsonl")
    if not rename_map:
        raise SystemExit("rename_map not found. Run dedupe_rename.py first.")

    text_dir = ensure_dir(settings.work_dir / "text")
    extract_dir = ensure_dir(settings.work_dir / "extract")
    chunk_dir = ensure_dir(settings.work_dir / "chunks")

    structured_records = []
    chunk_records = []
    ocr_queue = []

    for item in rename_map:
        source_path = Path(item["source_path"])
        manifest = manifest_records[item["doc_id"]]
        full_text, error = extract_full_text(pdftotext_exe, source_path)
        cleaned = normalize_text(full_text)
        (text_dir / f"{item['doc_id']}.txt").write_text(cleaned, encoding="utf-8")

        text_quality = "ok"
        if manifest.get("needs_ocr"):
            text_quality = "needs_ocr"
            ocr_queue.append(
                {
                    "doc_id": item["doc_id"],
                    "source_path": str(source_path),
                    "reason": "scan_like_pdf_or_text_missing",
                }
            )
        elif len(cleaned) < int(settings.raw.get("fulltext_min_chars", 800)):
            text_quality = "text_too_short"

        lines = first_meaningful_lines(full_text)
        title_from_text, author_guess = extract_title_author(lines)
        merged_text = "\n".join(filter(None, [item.get("title_guess", ""), title_from_text or "", cleaned[:8000]]))
        tags = keyword_tags(merged_text, settings.raw["taxonomy"])

        structured = {
            "doc_id": item["doc_id"],
            "source_path": item["source_path"],
            "normalized_target": item["target_path"],
            "document_type_guess": item["document_type_guess"],
            "year_guess": item["year_guess"],
            "title_guess": title_from_text or item.get("title_guess"),
            "author_guess": author_guess,
            "doi_guess": extract_doi(merged_text),
            "materials": tags["materials"],
            "processes": tags["processes"],
            "properties": tags["properties"],
            "text_chars": len(cleaned),
            "text_quality": text_quality,
            "extract_error": error,
        }
        structured_records.append(structured)

        for idx, chunk in enumerate(
            chunk_text(
                cleaned,
                int(settings.raw.get("chunk_size", 1200)),
                int(settings.raw.get("chunk_overlap", 200)),
            ),
            start=1,
        ):
            chunk_records.append(
                {
                    "chunk_id": f"{item['doc_id']}_{idx:04d}",
                    "doc_id": item["doc_id"],
                    "chunk_index": idx,
                    "text": chunk,
                    "document_type_guess": item["document_type_guess"],
                    "year_guess": item["year_guess"],
                }
            )

    write_jsonl(extract_dir / "structured_records.jsonl", structured_records)
    write_csv(
        extract_dir / "structured_records.csv",
        structured_records,
        [
            "doc_id",
            "document_type_guess",
            "year_guess",
            "title_guess",
            "author_guess",
            "doi_guess",
            "materials",
            "processes",
            "properties",
            "text_chars",
            "text_quality",
            "source_path",
            "normalized_target",
        ],
    )
    write_jsonl(chunk_dir / "chunks.jsonl", chunk_records)
    write_csv(extract_dir / "ocr_queue.csv", ocr_queue, ["doc_id", "source_path", "reason"])

    with (extract_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "documents_processed": len(structured_records),
                "chunks_created": len(chunk_records),
                "ocr_queue_count": len(ocr_queue),
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Structured records written to: {extract_dir}")
    print(f"Chunks written to: {chunk_dir}")


if __name__ == "__main__":
    main()
