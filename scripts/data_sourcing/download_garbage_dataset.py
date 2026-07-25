#!/usr/bin/env python3
"""
Download a mixed-garbage image dataset automatically, one folder per class.

Uses icrawler (Bing image search backend, no API key required). Each class
pulls from several query variations so results aren't dominated by one
search results page, then dedupes and re-numbers files per class.

Usage:
    pip install icrawler
    python download_garbage_dataset.py --per-class 200 --out dataset/garbage

    # subset of classes only
    python download_garbage_dataset.py --classes plastic_bottle metal_can --per-class 100
"""

import argparse
import hashlib
import shutil
from pathlib import Path

from icrawler.builtin import BingImageCrawler

CLASSES = {
    "paper": ["waste paper", "crumpled paper", "paper trash", "torn paper sheet"],
    "leaves": ["dry leaves", "fallen leaves pile", "dead leaves ground"],
    "flower": ["flower", "wilted flower", "flower isolated white background"],
    "apple": ["apple fruit", "rotten apple", "apple isolated white background"],
    "food": ["food waste", "leftover food trash", "food scraps"],
    "wood": ["wood scrap", "wood plank piece", "waste wood"],
    "cotton_cloth": ["cotton cloth rag", "old cloth fabric scrap", "torn cloth"],
    "plastic_bottle": ["plastic water bottle", "empty plastic bottle", "crushed plastic bottle"],
    "plastic_bag": ["plastic bag", "plastic bag trash", "grocery plastic bag"],
    "chips_packet": ["chips packet trash", "empty chips packet", "snack wrapper"],
    "coke_bottle": ["coca cola bottle", "coke plastic bottle", "soda bottle empty"],
    "metal_can": ["aluminum can", "soda can crushed", "metal tin can trash"],
    "mobile": ["old mobile phone", "broken smartphone", "mobile phone isolated"],
    "battery": ["used battery", "AA battery", "battery waste"],
    "remote": ["tv remote control", "old remote control"],
    "laptop": ["old laptop", "broken laptop", "laptop isolated white background"],
    "charger": ["phone charger", "laptop charger cable", "old charger adapter"],
    "keyboard": ["computer keyboard", "old keyboard", "keyboard isolated white background"],
    "mouse": ["computer mouse", "old computer mouse", "mouse isolated white background"],
    "cable": ["tangled cables", "usb cable", "electronic wire cable waste"],
}


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


def renumber(folder: Path, prefix: str) -> None:
    files = sorted(f for f in folder.iterdir() if f.is_file())
    for i, f in enumerate(files, start=1):
        ext = f.suffix.lower() or ".jpg"
        new_name = folder / f"{prefix}_{i:05d}{ext}"
        if f != new_name:
            f.rename(new_name)


def download_class(class_name: str, queries: list, target: int, out_root: Path, workers: int) -> None:
    class_dir = out_root / class_name
    class_dir.mkdir(parents=True, exist_ok=True)

    per_query = max(1, target // len(queries) + 10)  # small overshoot

    for idx, query in enumerate(queries):
        tmp_dir = class_dir / f"_tmp_{idx}"
        tmp_dir.mkdir(exist_ok=True)

        crawler = BingImageCrawler(
            feeder_threads=1,
            parser_threads=1,
            downloader_threads=workers,
            storage={"root_dir": str(tmp_dir)},
        )
        crawler.crawl(
            keyword=query,
            max_num=per_query,
            filters={"type": "photo"},
        )

        for f in tmp_dir.iterdir():
            if f.is_file():
                dest = class_dir / f"{idx}_{f.name}"
                shutil.move(str(f), str(dest))
        shutil.rmtree(tmp_dir, ignore_errors=True)

        current_count = sum(1 for f in class_dir.iterdir() if f.is_file())
        print(f"  [{class_name}] '{query}' -> total so far: {current_count}")
        if current_count >= target:
            break

    dedupe_by_hash(class_dir)

    files = sorted(f for f in class_dir.iterdir() if f.is_file())
    for extra in files[target:]:
        extra.unlink()
    renumber(class_dir, class_name)

    final_count = sum(1 for f in class_dir.iterdir() if f.is_file())
    print(f"[{class_name}] done: {final_count} images -> {class_dir}")


def main():
    ap = argparse.ArgumentParser(description="Download mixed garbage image dataset")
    ap.add_argument("--per-class", type=int, default=150, help="target images per class")
    ap.add_argument("--out", type=str, default="dataset/garbage", help="output root dir")
    ap.add_argument("--workers", type=int, default=4, help="downloader threads per query")
    ap.add_argument(
        "--classes",
        nargs="+",
        default=list(CLASSES.keys()),
        choices=list(CLASSES.keys()),
        help="subset of classes to download (default: all)",
    )
    args = ap.parse_args()

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    for class_name in args.classes:
        print(f"\n=== Class: {class_name} ===")
        download_class(class_name, CLASSES[class_name], args.per_class, out_root, args.workers)

    total = sum(1 for f in out_root.rglob("*") if f.is_file())
    print(f"\nAll done. {total} images across {len(args.classes)} classes -> {out_root}")


if __name__ == "__main__":
    main()
