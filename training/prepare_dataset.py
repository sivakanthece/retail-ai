"""
Step 1 — Prepare SKU-110K dataset for YOLOv8 training.

What this script does:
  1. Reads SKU-110K annotation CSV files (train/val/test)
  2. Converts bounding boxes to YOLO format (normalised cx, cy, w, h)
  3. Copies a subset of images into the correct folder structure
  4. Writes data.yaml for YOLOv8

SKU-110K annotation CSV columns:
  image_name, x1, y1, x2, y2, class, image_width, image_height

Usage:
  python prepare_dataset.py --dataset_dir C:/sku110k --subset 500
  python prepare_dataset.py --dataset_dir C:/sku110k --subset 0   # 0 = use ALL images
"""

import argparse
import os
import shutil
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import yaml

# ── Single class: SKU-110K only labels objects as "object" ───────────────────
CLASSES = ["object"]

def bbox_to_yolo(x1, y1, x2, y2, img_w, img_h):
    """Convert absolute bbox to normalised YOLO format (cx, cy, w, h)."""
    cx = (x1 + x2) / 2.0 / img_w
    cy = (y1 + y2) / 2.0 / img_h
    w  = (x2 - x1) / img_w
    h  = (y2 - y1) / img_h
    # Clamp to [0, 1]
    cx = max(0.0, min(1.0, cx))
    cy = max(0.0, min(1.0, cy))
    w  = max(0.0, min(1.0, w))
    h  = max(0.0, min(1.0, h))
    return cx, cy, w, h

def process_split(csv_path, img_src_dir, out_img_dir, out_lbl_dir, subset, split_name):
    """Process one split (train/val/test)."""
    print(f"\n--- Processing {split_name} ---")

    if not Path(csv_path).exists():
        print(f"  WARNING: {csv_path} not found — skipping.")
        return 0

    df = pd.read_csv(csv_path, header=None,
                     names=["image_name","x1","y1","x2","y2","class","image_width","image_height"])

    # Get unique images
    images = df["image_name"].unique()
    if subset and subset > 0:
        images = images[:subset]
        print(f"  Using subset of {subset} images (out of {df['image_name'].nunique()} total)")
    else:
        print(f"  Using ALL {len(images)} images")

    out_img_dir.mkdir(parents=True, exist_ok=True)
    out_lbl_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for img_name in tqdm(images, desc=f"  {split_name}"):
        img_src = Path(img_src_dir) / img_name
        if not img_src.exists():
            continue

        # Copy image
        shutil.copy2(img_src, out_img_dir / img_name)

        # Write YOLO label file
        rows = df[df["image_name"] == img_name]
        lbl_path = out_lbl_dir / (Path(img_name).stem + ".txt")
        with open(lbl_path, "w") as f:
            for _, row in rows.iterrows():
                try:
                    cx, cy, w, h = bbox_to_yolo(
                        float(row.x1), float(row.y1),
                        float(row.x2), float(row.y2),
                        float(row.image_width), float(row.image_height)
                    )
                    if w > 0 and h > 0:
                        f.write(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
                except (ValueError, ZeroDivisionError):
                    continue
        copied += 1

    print(f"  Done: {copied} images prepared.")
    return copied

def main():
    parser = argparse.ArgumentParser(description="Prepare SKU-110K for YOLOv8")
    parser.add_argument("--dataset_dir", required=True,
                        help="Root folder of downloaded SKU-110K dataset")
    parser.add_argument("--output_dir", default="./sku110k_yolo",
                        help="Output folder for YOLO-formatted dataset (default: ./sku110k_yolo)")
    parser.add_argument("--subset", type=int, default=500,
                        help="Number of training images to use. 0 = use all (default: 500 for CPU demo)")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)
    output_dir  = Path(args.output_dir)

    # Expected SKU-110K folder structure:
    # dataset_dir/
    #   images/train/   ← training images
    #   images/val/     ← validation images  (some releases use test/)
    #   images/test/    ← test images
    #   annotations/annotations_train.csv
    #   annotations/annotations_val.csv
    #   annotations/annotations_test.csv

    splits = {
        "train": {
            "csv":     dataset_dir / "annotations" / "annotations_train.csv",
            "img_src": dataset_dir / "images" / "train",
            "subset":  args.subset,
        },
        "val": {
            "csv":     dataset_dir / "annotations" / "annotations_val.csv",
            "img_src": dataset_dir / "images" / "val",
            "subset":  max(50, args.subset // 5) if args.subset > 0 else 0,
        },
        "test": {
            "csv":     dataset_dir / "annotations" / "annotations_test.csv",
            "img_src": dataset_dir / "images" / "test",
            "subset":  max(50, args.subset // 5) if args.subset > 0 else 0,
        },
    }

    totals = {}
    for split, cfg in splits.items():
        n = process_split(
            csv_path    = cfg["csv"],
            img_src_dir = cfg["img_src"],
            out_img_dir = output_dir / "images" / split,
            out_lbl_dir = output_dir / "labels" / split,
            subset      = cfg["subset"],
            split_name  = split,
        )
        totals[split] = n

    # Write data.yaml
    data_yaml = {
        "path":  str(output_dir.resolve()),
        "train": "images/train",
        "val":   "images/val",
        "test":  "images/test",
        "nc":    len(CLASSES),
        "names": CLASSES,
    }
    yaml_path = output_dir / "data.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(data_yaml, f, default_flow_style=False)

    print(f"\n=== Dataset preparation complete ===")
    print(f"  Train : {totals.get('train', 0)} images")
    print(f"  Val   : {totals.get('val',   0)} images")
    print(f"  Test  : {totals.get('test',  0)} images")
    print(f"  YAML  : {yaml_path}")
    print(f"\nNext step: python train.py --data {yaml_path}")

if __name__ == "__main__":
    main()
