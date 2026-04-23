from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path

from common import ensure_dir, load_settings, read_jsonl, safe_filename, write_csv, write_jsonl


def build_proposed_filename(record: dict, max_length: int) -> str:
    year = record.get("year_guess") or "unknown"
    title = record.get("title_guess") or record["stem"]
    base = f"{title}_{year}"
    return safe_filename(base, max_length=max_length) + ".pdf"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "config" / "settings.json"))
    parser.add_argument("--apply", action="store_true", help="Copy primary files into normalized_dir.")
    args = parser.parse_args()

    settings = load_settings(args.config)
    manifest_path = settings.work_dir / "manifest" / "manifest.jsonl"
    records = read_jsonl(manifest_path)
    if not records:
        raise SystemExit("Manifest not found. Run scan_manifest.py first.")

    dedupe_dir = ensure_dir(settings.work_dir / "dedupe")
    max_length = int(settings.raw.get("filename_max_length", 140))

    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        groups[record["sha256"]].append(record)

    plan = []
    rename_map = []
    used_targets: dict[str, int] = {}

    for sha256, group in groups.items():
        group_sorted = sorted(group, key=lambda item: (item["is_empty"], -item["size_bytes"], item["name"]))
        primary = group_sorted[0]
        duplicate_count = len(group_sorted) - 1
        base_name = build_proposed_filename(primary, max_length)
        target_subdir = primary.get("document_type_guess") or "unclassified"
        target_key = str(Path(target_subdir) / base_name).lower()
        suffix_index = used_targets.get(target_key, 0)
        used_targets[target_key] = suffix_index + 1
        if suffix_index:
            stem = Path(base_name).stem
            base_name = f"{stem}_{suffix_index + 1}.pdf"

        target_path = settings.normalized_dir / target_subdir / base_name
        for index, record in enumerate(group_sorted):
            is_primary = index == 0
            plan_record = {
                "doc_id": record["doc_id"],
                "sha256": sha256,
                "name": record["name"],
                "path": record["path"],
                "document_type_guess": record["document_type_guess"],
                "is_primary": is_primary,
                "duplicate_count": duplicate_count,
                "skip_reason": "duplicate" if not is_primary else ("empty_file" if record["is_empty"] else ""),
                "proposed_target": str(target_path),
            }
            plan.append(plan_record)

            if is_primary and (not record["is_empty"]):
                rename_map.append(
                    {
                        "doc_id": record["doc_id"],
                        "source_path": record["path"],
                        "target_path": str(target_path),
                        "proposed_name": target_path.name,
                        "document_type_guess": record["document_type_guess"],
                        "title_guess": record["title_guess"],
                        "year_guess": record["year_guess"],
                    }
                )
                if args.apply:
                    ensure_dir(target_path.parent)
                    shutil.copy2(record["path"], target_path)

    write_jsonl(dedupe_dir / "dedupe_plan.jsonl", plan)
    write_csv(
        dedupe_dir / "dedupe_plan.csv",
        plan,
        [
            "doc_id",
            "name",
            "document_type_guess",
            "is_primary",
            "duplicate_count",
            "skip_reason",
            "proposed_target",
            "path",
        ],
    )
    write_jsonl(dedupe_dir / "rename_map.jsonl", rename_map)
    write_csv(
        dedupe_dir / "rename_map.csv",
        rename_map,
        [
            "doc_id",
            "document_type_guess",
            "year_guess",
            "title_guess",
            "source_path",
            "target_path",
            "proposed_name",
        ],
    )

    with (dedupe_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "input_records": len(records),
                "primary_records": len(rename_map),
                "exact_duplicate_groups": sum(1 for group in groups.values() if len(group) > 1),
                "apply_mode": args.apply,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Dedupe plan written to: {dedupe_dir}")
    if args.apply:
        print(f"Primary files copied to: {settings.normalized_dir}")
    else:
        print("Dry-run only. Re-run with --apply to copy primary files.")


if __name__ == "__main__":
    main()
