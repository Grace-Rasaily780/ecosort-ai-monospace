#!/usr/bin/env python3
"""
Download second waste-classification dataset, new classes, balanced across
3 categories (bio-degradable / non-biodegradable / e-waste). 400 images
total by default, split evenly per category then per class.

Uses icrawler (Bing backend, no API key). Real photos only: filters={"type":
"photo"} (drops clipart/lineart/render/animated), plus negative keywords in
each query to push out AI-generated/illustrated results.

Usage:
    pip install icrawler
    python download_waste_dataset_v2.py --total 400 --out dataset/garbage_v2

    # subset of classes only
    python download_waste_dataset_v2.py --classes weeds diapers cd --total 90
"""

import argparse
import hashlib
import shutil
from pathlib import Path

from icrawler.builtin import BingImageCrawler

NEG = "-AI -generated -art -illustration -render -drawing -cartoon -clipart"

CATEGORIES = {
    "bio_degradable": {
        "animal_manure": ["animal manure pile", "cow dung waste", "livestock manure"],
        "garden_waste": ["garden waste pile", "yard waste clippings", "green waste bin garden"],
        "weeds": ["pulled weeds pile", "garden weeds waste", "uprooted weeds"],
        "fruit_waste": ["rotten fruit waste", "fruit peels trash", "spoiled fruit compost"],
    },
    "non_biodegradable": {
        "rubber_tyres": ["scrap rubber tyre", "old car tyre waste", "discarded tyre pile"],
        "aluminium_foil": ["used aluminium foil trash", "crumpled aluminum foil waste", "foil wrapper trash"],
        "diapers": ["used diaper waste", "disposable diaper trash", "diaper landfill"],
        "plastic_toys": ["broken plastic toy waste", "discarded plastic toys", "old plastic toy trash"],
    },
    "e_waste": {
        "circuit_boards": ["scrap circuit board", "e-waste circuit board", "broken PCB electronics"],
        "resistors": ["electronic resistors scrap", "resistor components waste", "e-waste resistors"],
        "washing_machine": ["old washing machine scrap", "broken washing machine junk", "washing machine e-waste"],
        "cd": ["old CD disc waste", "scratched CD DVD trash", "broken compact disc"],
    },
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
            keyword=f"{query} {NEG}",
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
    ap = argparse.ArgumentParser(description="Download balanced bio/non-bio/e-waste image dataset")
    ap.add_argument("--total", type=int, default=400, help="total images across all classes")
    ap.add_argument("--out", type=str, default="dataset/garbage_v2", help="output root dir")
    ap.add_argument("--workers", type=int, default=4, help="downloader threads per query")

    all_classes = {c: q for cat in CATEGORIES.values() for c, q in cat.items()}
    ap.add_argument(
        "--classes",
        nargs="+",
        default=list(all_classes.keys()),
        choices=list(all_classes.keys()),
        help="subset of classes to download (default: all)",
    )
    args = ap.parse_args()

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    selected = set(args.classes)
    # balance: total split evenly per category, then evenly per class within category
    active_categories = {
        cat: {c: q for c, q in classes.items() if c in selected}
        for cat, classes in CATEGORIES.items()
    }
    active_categories = {cat: classes for cat, classes in active_categories.items() if classes}

    per_category = args.total // len(active_categories)

    for cat, classes in active_categories.items():
        per_class = per_category // len(classes)
        print(f"\n### Category: {cat} -> {per_category} images ({per_class}/class) ###")
        for class_name, queries in classes.items():
            print(f"\n=== Class: {class_name} ===")
            download_class(class_name, queries, per_class, out_root, args.workers)

    total = sum(1 for f in out_root.rglob("*") if f.is_file())
    print(f"\nAll done. {total} images across {len(args.classes)} classes -> {out_root}")


if __name__ == "__main__":
    main()
