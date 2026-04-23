# Literature KB Pipeline

## This Project Does

This starter project is for a materials-research literature pipeline on Windows.
It is designed to help you run a 100-document pilot first, then scale to 10,000+ PDFs.

Current pipeline stages:

1. Scan PDFs and build a manifest.
2. Detect exact duplicates by SHA256.
3. Generate normalized filenames and a copy plan.
4. Extract text with `pdftotext`.
5. Build structured records and text chunks for later RAG or local LLM use.

## Directory Layout

- `config/settings.json`: main configuration.
- `scripts/scan_manifest.py`: scans PDFs and builds the manifest.
- `scripts/dedupe_rename.py`: generates dedupe and rename plans.
- `scripts/extract_classify.py`: extracts text, tags, and chunks.
- `run_pipeline.ps1`: one-click entry point.
- `work/`: generated outputs.
- `normalized/`: normalized primary PDFs after `--apply`.

## Quick Start

Open PowerShell in this directory and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_pipeline.ps1
```

This first run is a dry-run for rename/copy.
It will not copy PDFs into `normalized/`.

If the outputs look correct, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_pipeline.ps1 -ApplyRename
```

## What Each Stage Produces

### 1. Manifest

Files are written to `work/manifest/`.

- `manifest.csv`: overview for Excel review.
- `manifest.jsonl`: machine-friendly detail.
- `summary.json`: counts for empty files, OCR candidates, and type guesses.

Important fields:

- `sha256`: exact-file dedupe key.
- `pdf_has_text`: whether `pdftotext` extracted visible text.
- `needs_ocr`: likely scanned or image-only PDF.
- `document_type_guess`: rule-based type guess.
- `title_guess`: filename-based or first-line guess.

### 2. Dedupe And Rename

Files are written to `work/dedupe/`.

- `dedupe_plan.csv`: every PDF, whether it is primary or duplicate.
- `rename_map.csv`: only the chosen primary files.
- `summary.json`: number of exact duplicate groups.

By default this stage does not rename the original PDFs.
It only proposes normalized output names.

When `-ApplyRename` is used:

- primary PDFs are copied to `normalized/<document_type>/`.
- duplicates are skipped.
- empty files are skipped.

### 3. Extract And Classify

Files are written to:

- `work/text/`: full extracted text.
- `work/extract/structured_records.csv`: document-level structured summary.
- `work/extract/ocr_queue.csv`: files that should go through OCR.
- `work/chunks/chunks.jsonl`: chunked text for vector indexing.

## Recommended Real Workflow

For your institute, do not jump directly to model fine-tuning.
Use this order:

1. Pilot with 100 PDFs.
2. Review duplicates and rename rules manually.
3. Verify which PDFs are scans and need OCR.
4. Improve taxonomy and metadata extraction.
5. Build local RAG on clean text and chunks.
6. Only after stable retrieval, consider instruction tuning.

## Where GROBID Fits

GROBID is professional for academic PDF structure extraction.
It is especially good at:

- title
- authors
- affiliations
- abstract
- references
- section structure

But GROBID is not a replacement for OCR.

Use this rule:

- born-digital academic papers: `pdftotext` first, then consider GROBID for better metadata structure.
- scanned PDFs: OCR first, then structured extraction.
- standards, patents, brochures, internal reports: GROBID is often less useful than rule-based extraction.

For a materials institute, GROBID should be one module, not the whole system.

## Suggested Next Improvements

1. Add OCR with Tesseract or PaddleOCR for `ocr_queue.csv`.
2. Add a metadata-review page with FastAPI.
3. Add SQLite or PostgreSQL instead of only CSV/JSONL.
4. Add semantic near-duplicate detection using text fingerprints.
5. Add table extraction for composition, process parameters, and performance data.

## Notes

- Original PDFs are not modified.
- Duplicate detection is exact-file only in this first version.
- Classification is keyword-based and should be refined by your domain team.
=======
# literature_testing

