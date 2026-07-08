import csv
import os
import sys
from pathlib import Path
from typing import Dict, List

from labelscan.pipeline import scan

FIELDS = [
    "filename",
    "application_id",
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "producer_name",
    "producer_address",
    "country_of_origin",
    "imported",
]

DEFAULT_MANIFEST = Path("label_manifest.csv")


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    input("\nPress Enter to continue...")


def header():
    print("=" * 66)
    print(" TTB LABELSCAN")
    print(" Local OCR + Label Matching")
    print("=" * 66)


def load_manifest(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            rows.append({field: (row.get(field) or "").strip() for field in FIELDS})
        return rows


def save_manifest(path: Path, rows: List[Dict[str, str]]):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def prompt_value(label: str, current: str = "") -> str:
    suffix = f" [{current}]" if current else ""
    value = input(f"{label}{suffix}: ").strip()
    return value if value else current


def choose_record(rows: List[Dict[str, str]]):
    if not rows:
        return None

    print("\nExisting labels:")
    for index, row in enumerate(rows, start=1):
        filename = row.get("filename") or "(no filename)"
        brand = row.get("brand_name") or "(no brand)"
        print(f"  {index}. {filename} — {brand}")
    print("  0. Create new label")

    while True:
        choice = input("\nSelect label number: ").strip()
        if choice == "0":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(rows):
            return int(choice) - 1
        print("Enter a valid label number.")


def edit_label():
    clear_screen()
    header()
    print("\n1. EDIT LABEL\n")

    manifest_input = input(
        f"Manifest path [{DEFAULT_MANIFEST}]: "
    ).strip()
    manifest_path = Path(manifest_input) if manifest_input else DEFAULT_MANIFEST

    rows = load_manifest(manifest_path)
    selected_index = choose_record(rows)

    if selected_index is None:
        record = {field: "" for field in FIELDS}
        print("\nCreating a new label record.")
    else:
        record = dict(rows[selected_index])
        print(f"\nEditing: {record.get('filename', '')}")

    record["filename"] = prompt_value("Image filename", record["filename"])
    if not record["filename"]:
        print("\nA filename is required. Record was not saved.")
        pause()
        return

    record["application_id"] = prompt_value(
        "Application ID", record["application_id"]
    )
    record["brand_name"] = prompt_value("Brand name", record["brand_name"])
    record["class_type"] = prompt_value("Class/type", record["class_type"])
    record["alcohol_content"] = prompt_value(
        "Alcohol content", record["alcohol_content"]
    )
    record["net_contents"] = prompt_value(
        "Net contents", record["net_contents"]
    )
    record["producer_name"] = prompt_value(
        "Producer/bottler", record["producer_name"]
    )
    record["producer_address"] = prompt_value(
        "Producer address", record["producer_address"]
    )
    record["country_of_origin"] = prompt_value(
        "Country of origin", record["country_of_origin"]
    )

    imported_current = record["imported"] or "false"
    imported = prompt_value("Imported? true/false", imported_current).lower()
    record["imported"] = "true" if imported in {"true", "yes", "y", "1"} else "false"

    if selected_index is None:
        rows.append(record)
    else:
        rows[selected_index] = record

    save_manifest(manifest_path, rows)
    print(f"\nSaved to: {manifest_path.resolve()}")
    pause()


def process_batch():
    clear_screen()
    header()
    print("\n2. PROCESS BATCH\n")

    folder = input("Folder containing label images: ").strip().strip('"')
    if not folder:
        print("\nA folder path is required.")
        pause()
        return

    manifest_default = str(DEFAULT_MANIFEST) if DEFAULT_MANIFEST.exists() else ""
    manifest_prompt = (
        f"Manifest path [{manifest_default}]: "
        if manifest_default
        else "Manifest path (leave blank for OCR only): "
    )
    manifest = input(manifest_prompt).strip().strip('"')
    if not manifest and manifest_default:
        manifest = manifest_default

    output = input("Output folder [labelscan-output]: ").strip().strip('"')
    output = output or "labelscan-output"

    workers_raw = input("Workers [2]: ").strip()
    workers = int(workers_raw) if workers_raw.isdigit() else 2
    workers = max(1, min(workers, 4))

    limit_raw = input("Image limit [50]: ").strip()
    limit = int(limit_raw) if limit_raw.isdigit() else 50

    aggressive_raw = input("Aggressive OCR recovery? y/N: ").strip().lower()
    aggressive = aggressive_raw in {"y", "yes"}

    print("\nProcessing batch...\n")
    try:
        summary = scan(
            input_path=folder,
            manifest_path=manifest or None,
            output=output,
            workers=workers,
            recursive=False,
            limit=limit,
            aggressive=aggressive,
        )
    except Exception as exc:
        print(f"\nBatch failed: {type(exc).__name__}: {exc}")
        pause()
        return

    print("\n" + "-" * 66)
    print("BATCH COMPLETE")
    print("-" * 66)
    print(f"Total:     {summary['total']}")
    print(f"Completed: {summary['completed']}")
    print(f"Errors:    {summary['errors']}")
    print(f"Pass:      {summary['pass']}")
    print(f"Review:    {summary['review']}")
    print(f"Fail:      {summary['fail']}")
    print(f"Median:    {summary['median_ms']} ms")
    print(f"P95:       {summary['p95_ms']} ms")
    print(f"\nCSV:  {summary['results_csv']}")
    print(f"JSON: {summary['results_json']}")
    print(f"Text: {summary['text_directory']}")
    pause()


def main():
    while True:
        clear_screen()
        header()
        print("\n  1. Edit Label")
        print("  2. Process Batch")
        print("  3. Quit")
        print()

        choice = input("Select an option: ").strip()

        if choice == "1":
            edit_label()
        elif choice == "2":
            process_batch()
        elif choice == "3":
            clear_screen()
            print("Goodbye.")
            return 0
        else:
            print("\nEnter 1, 2, or 3.")
            pause()


if __name__ == "__main__":
    sys.exit(main())
