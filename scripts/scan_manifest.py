from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    choose_title,
    compute_sha256,
    ensure_dir,
    extract_doi,
    extract_standard_code,
    extract_year,
    find_executable,
    guess_document_type,
    guess_language,
    load_settings,
    run_command,
    utc_iso_from_timestamp,
    write_csv,
    write_jsonl,
)


def list_pdfs(source_dir: Path, recursive: bool) -> list[Path]:
    patterns = ["**/*.pdf", "**/*.PDF"] if recursive else ["*.pdf", "*.PDF"]
    items: set[Path] = set()
    for pattern in patterns:
        items.update(path.resolve() for path in source_dir.glob(pattern))
    return [Path(path) for path in sorted(items)]


def probe_pdf_text(pdftotext_exe: str | None, pdf_path: Path, max_pages: int) -> tuple[str, bool, str | None]:
    if not pdftotext_exe:
        return "", False, "pdftotext_not_found"
    args = [
        pdftotext_exe,
        "-f",
        "1",
        "-l",
        str(max_pages),
        "-enc",
        "UTF-8",
        str(pdf_path),
        "-",
    ]
    code, stdout, stderr = run_command(args, timeout=120)
    text = stdout.strip()
    if code != 0:
        return text, False, stderr.strip() or "pdftotext_failed"
    return text, bool(text.strip()), None


def probe_pdf_pages(pdfinfo_exe: str | None, pdf_path: Path) -> int | None:
    if not pdfinfo_exe:
        return None
    code, stdout, _stderr = run_command([pdfinfo_exe, str(pdf_path)], timeout=60)
    if code != 0:
        return None
    for line in stdout.splitlines():
        if line.lower().startswith("pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "config" / "settings.json"))
    args = parser.parse_args()

    settings = load_settings(args.config)
    work_dir = ensure_dir(settings.work_dir)
    manifest_dir = ensure_dir(work_dir / "manifest")

    pdftotext_exe = find_executable(settings.raw.get("pdftotext_exe", ""), "pdftotext")
    pdfinfo_exe = find_executable(settings.raw.get("pdfinfo_exe", ""), "pdfinfo")

    records = []
    for pdf_path in list_pdfs(settings.source_dir, settings.recursive):
        stat = pdf_path.stat()
        sha256 = compute_sha256(pdf_path)
        record = {
            "doc_id": sha256[:16],
            "path": str(pdf_path),
            "relative_path": str(pdf_path.relative_to(settings.source_dir)),
            "name": pdf_path.name,
            "stem": pdf_path.stem,
            "extension": pdf_path.suffix,
            "size_bytes": stat.st_size,
            "modified_utc": utc_iso_from_timestamp(stat.st_mtime),
            "sha256": sha256,
            "is_empty": stat.st_size == 0,
        }

        text_sample, has_text, error = probe_pdf_text(
            pdftotext_exe,
            pdf_path,
            int(settings.raw.get("text_probe_pages", 2)),
        )
        record["page_count"] = probe_pdf_pages(pdfinfo_exe, pdf_path)
        record["text_sample"] = text_sample[:4000]
        record["text_sample_chars"] = len(text_sample)
        record["pdf_has_text"] = has_text
        record["needs_ocr"] = (not has_text) and (not record["is_empty"])
        record["text_probe_error"] = error
        record["title_guess"] = choose_title(pdf_path.name, text_sample)
        record["language_guess"] = guess_language(f"{record['title_guess']}\n{text_sample[:1500]}")
        record["document_type_guess"] = guess_document_type(pdf_path.name, settings.raw["document_type_rules"])
        record["year_guess"] = extract_year(f"{pdf_path.name}\n{text_sample[:1500]}")
        record["doi_guess"] = extract_doi(text_sample[:3000])
        record["standard_code_guess"] = extract_standard_code(pdf_path.name)
        records.append(record)

    write_jsonl(manifest_dir / "manifest.jsonl", records)
    write_csv(
        manifest_dir / "manifest.csv",
        records,
        [
            "doc_id",
            "name",
            "relative_path",
            "size_bytes",
            "page_count",
            "pdf_has_text",
            "needs_ocr",
            "document_type_guess",
            "year_guess",
            "language_guess",
            "doi_guess",
            "standard_code_guess",
            "title_guess",
            "sha256",
            "text_probe_error",
        ],
    )

    summary = {
        "total_files": len(records),
        "empty_files": sum(1 for item in records if item["is_empty"]),
        "needs_ocr": sum(1 for item in records if item["needs_ocr"]),
        "with_text": sum(1 for item in records if item["pdf_has_text"]),
        "document_types": {},
    }
    for record in records:
        key = record["document_type_guess"]
        summary["document_types"][key] = summary["document_types"].get(key, 0) + 1

    with (manifest_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    print(f"Scanned {len(records)} PDF files.")
    print(f"Manifest written to: {manifest_dir}")


if __name__ == "__main__":
    main()
