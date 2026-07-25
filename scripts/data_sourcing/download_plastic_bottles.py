#!/usr/bin/env python3
"""
Download a plastic bottle image dataset automatically.

Uses icrawler (Bing image search backend, no API key required) to pull
images across several query variations so the dataset isn't dominated by
one search result page, then dedupes and re-numbers the final files.

Usage:
    pip install icrawler
    python download_plastic_bottles.py --total 1000 --out dataset/plastic_bottles
"""

import argparse
import hashlib
import os
import shutil
from pathlib import Path

from icrawler.builtin import BingImageCrawler

QUERIES = [
    "plastic bottle",
    "plastic water bottle",
    "plastic soda bottle",
    "empty plastic bottle",
    "crushed plastic bottle",
    "plastic bottle isolated white background",
    "plastic bottle trash",
    "plastic bottle recycling",
    "PET plastic bottle",
    "plastic bottle on table",
]


def dedupe_by_hash(folder: Path) -> None:
    seen = {}
    for f in sorted(folder.iterdir()):
        if not f.is_file():
            continue
        h = hashlib.md5(f.read_bytes()).hexdigest()
        if h in seen:
            f.unlink()
        else:
            seen[h] = f


def renumber(folder: Path, prefix: str = "plastic_bottle") -> None:
    files = sorted(f for f in folder.iterdir() if f.is_file())
    for i, f in enumerate(files, start=1):
        ext = f.suffix.lower() or ".jpg"
        new_name = folder / f"{prefix}_{i:05d}{ext}"
        if f != new_name:
            f.rename(new_name)


def main():
    ap = argparse.ArgumentParser(description="Download plastic bottle image dataset")
    ap.add_argument("--total", type=int, default=1000, help="target total image count")
    ap.add_argument("--out", type=str, default="dataset/plastic_bottles", help="output dir")
    ap.add_argument("--workers", type=int, default=4, help="downloader threads per query")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    per_query = max(1, args.total // len(QUERIES) + 10)  # small overshoot per query

    for idx, query in enumerate(QUERIES):
        tmp_dir = out_dir / f"_tmp_{idx}"
        tmp_dir.mkdir(exist_ok=True)

        crawler = BingImageCrawler(
            feeder_threads=1,
            parser_threads=1,
            downloader_threads=args.workers,
            storage={"root_dir": str(tmp_dir)},
        )
        crawler.crawl(
            keyword=query,
            max_num=per_query,
            filters={"type": "photo"},
        )

        # move downloaded files into out_dir with unique names, then drop tmp dir
        for f in tmp_dir.iterdir():
            if f.is_file():
                dest = out_dir / f"{idx}_{f.name}"
                shutil.move(str(f), str(dest))
        shutil.rmtree(tmp_dir, ignore_errors=True)

        current_count = sum(1 for f in out_dir.iterdir() if f.is_file())
        print(f"[{query}] done. total so far: {current_count}")
        if current_count >= args.total:
            break

    print("Deduping...")
    dedupe_by_hash(out_dir)

    print("Trimming to target and renumbering...")
    files = sorted(f for f in out_dir.iterdir() if f.is_file())
    for extra in files[args.total:]:
        extra.unlink()
    renumber(out_dir)

    final_count = sum(1 for f in out_dir.iterdir() if f.is_file())
    print(f"Done. {final_count} images saved to {out_dir}")


if __name__ == "__main__":
    main()
