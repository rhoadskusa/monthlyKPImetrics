#!/usr/bin/env python3
"""
Convert Work Orders -- pre-cache Yardi Work Order Directory exports

Yardi's Work Order Directory .xlsx export puts a hyperlink on nearly every
cell (back to the ticket/property/unit in Yardi), which are useless for
this report but make openpyxl very slow to open -- especially on a large
multi-year historical backfill. This script parses each .xlsx once, strips
it down to the plain data (dropping the useless links), and writes a fast
Parquet cache next to each file. It also writes a matching .csv so you can
eyeball the extracted data.

The main report (main.py) already does this caching automatically the
first time it touches each file, so running this script isn't required --
but running it once up front on a big historical folder means the first
real report run isn't the one that pays the slow-parse cost, and lets you
confirm the extraction looks right before relying on it.

Requirements:
    pip install -r requirements.txt

Usage:
    python convert_work_orders.py                  # opens a folder picker
    python convert_work_orders.py "C:\\path\\to\\WorkOrders"
    python convert_work_orders.py --force           # re-convert even if a cache already exists

Output (written next to each source .xlsx):
    <name>.parquet   -- fast-loading cache used by main.py
    <name>.csv       -- same data, for spot-checking in Excel/a text editor
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import work_orders as wo


def pick_folder() -> Path:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        sys.exit(
            "No folder given and tkinter isn't available to prompt for one.\n"
            "Run again with a folder path, e.g.:\n"
            "  python convert_work_orders.py \"C:\\path\\to\\WorkOrders\""
        )

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    selected = filedialog.askdirectory(title="Select the folder of Yardi Work Order Directory exports")
    root.destroy()

    if not selected:
        sys.exit("No folder selected -- nothing to do.")
    return Path(selected)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pre-cache Yardi Work Order Directory .xlsx exports as Parquet + CSV.")
    parser.add_argument(
        "folder",
        type=str,
        nargs="?",
        default=None,
        help="Folder containing .xlsx work order exports. Opens a folder picker if omitted.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-convert every file even if an up-to-date cache already exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    folder = Path(args.folder) if args.folder else pick_folder()

    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")

    files = sorted(folder.glob("*.xlsx"))
    if not files:
        sys.exit(f"No .xlsx files found in {folder}")

    print(f"Found {len(files)} .xlsx file(s) in {folder}\n")

    converted = 0
    skipped = 0
    failed = 0
    total_tickets = 0

    for i, path in enumerate(files, start=1):
        print(f"[{i}/{len(files)}] {path.name} ... ", end="", flush=True)

        cache_path = path.with_suffix(".parquet")
        was_fresh = not args.force and cache_path.exists() and cache_path.stat().st_mtime >= path.stat().st_mtime

        try:
            cache_path, df = wo.convert_to_cache(path, force=args.force)
        except ImportError as exc:
            sys.exit(f"\n{exc}")
        except Exception as exc:  # noqa: BLE001 -- one bad file shouldn't stop the batch
            print(f"FAILED ({exc})")
            failed += 1
            continue

        csv_path = path.with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        total_tickets += len(df)

        if was_fresh:
            skipped += 1
            print(f"already cached ({len(df)} tickets)")
        else:
            converted += 1
            print(f"converted ({len(df)} tickets) -> {cache_path.name}, {csv_path.name}")

    print(
        f"\nDone: {converted} converted, {skipped} already up to date, {failed} failed. "
        f"{total_tickets} total tickets across all files."
    )
    if failed:
        print("Some files failed to convert -- check the messages above.")


if __name__ == "__main__":
    main()
