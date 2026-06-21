"""
Step 2 — Train YOLOv8 on the prepared SKU-110K dataset.

This script:
  - Trains YOLOv8n (nano) — the fastest/smallest model, ideal for CPU
  - Prints live metrics (box loss, cls loss, mAP) after every epoch
  - Saves the best model weights to runs/detect/sku_retail/weights/best.pt
  - Generates training plots (loss curves, mAP curves)

Usage:
  python train.py --data ./sku110k_yolo/data.yaml
  python train.py --data ./sku110k_yolo/data.yaml --epochs 20 --imgsz 416
"""

import argparse
import os
import time
from pathlib import Path
from ultralytics import YOLO

def main():
    parser = argparse.ArgumentParser(description="Train YOLOv8 on SKU-110K")
    parser.add_argument("--data",    required=True,       help="Path to data.yaml")
    parser.add_argument("--model",   default="yolov8n.pt",help="Base model (yolov8n/s/m/l/x.pt)")
    parser.add_argument("--epochs",  type=int, default=10, help="Number of epochs (default: 10 for CPU demo)")
    parser.add_argument("--imgsz",   type=int, default=320,help="Image size (default: 320 for CPU speed)")
    parser.add_argument("--batch",   type=int, default=4,  help="Batch size (default: 4 for CPU)")
    parser.add_argument("--name",    default="sku_retail", help="Run name")
    parser.add_argument("--resume",  action="store_true",  help="Resume from last checkpoint")
    args = parser.parse_args()

    print("=" * 60)
    print("  YOLOv8 Training — Retail Product Detection")
    print("=" * 60)
    print(f"  Model      : {args.model}")
    print(f"  Dataset    : {args.data}")
    print(f"  Epochs     : {args.epochs}")
    print(f"  Image size : {args.imgsz}x{args.imgsz}")
    print(f"  Batch size : {args.batch}")
    print(f"  Device     : CPU")
    print("=" * 60)
    print()

    # Estimate training time
    est_mins = args.epochs * 2  # rough estimate for CPU with 500 images
    print(f"  Estimated time on CPU: ~{est_mins}-{est_mins*2} minutes for {args.epochs} epochs")
    print(f"  Tip: For faster results, reduce epochs to 3-5 just to see metrics.\n")

    model = YOLO(args.model)

    start = time.time()

    results = model.train(
        data      = args.data,
        epochs    = args.epochs,
        imgsz     = args.imgsz,
        batch     = args.batch,
        device    = "cpu",
        name      = args.name,
        project   = "runs/detect",
        patience  = 5,           # early stopping if no improvement for 5 epochs
        save      = True,
        plots     = True,        # generate loss/mAP plots
        verbose   = True,
        resume    = args.resume,

        # Augmentation — helps with retail shelf variations
        hsv_h     = 0.015,
        hsv_s     = 0.7,
        hsv_v     = 0.4,
        flipud    = 0.0,
        fliplr    = 0.5,
        mosaic    = 0.5,
        degrees   = 5.0,
        translate = 0.1,
        scale     = 0.3,

        # CPU optimisation
        workers   = 0,           # 0 = no multiprocessing (avoids Windows issues)
        cache     = False,
    )

    elapsed = (time.time() - start) / 60
    print(f"\n{'='*60}")
    print(f"  Training complete in {elapsed:.1f} minutes")
    print(f"{'='*60}")

    # Print final metrics
    metrics = model.val()
    print_metrics(metrics)

    best_path = Path("runs/detect") / args.name / "weights" / "best.pt"
    print(f"\n  Best model saved to: {best_path.resolve()}")
    print(f"  To use this model in the app, update backend/.env:")
    print(f"  YOLO_MODEL={best_path.resolve()}")
    print(f"\n  To evaluate: python evaluate.py --model {best_path.resolve()} --data {args.data}")

def print_metrics(metrics):
    print(f"\n{'='*60}")
    print("  FINAL VALIDATION METRICS")
    print(f"{'='*60}")
    try:
        box = metrics.box
        print(f"  mAP@0.50       : {box.map50:.4f}  ({box.map50*100:.1f}%)")
        print(f"  mAP@0.50:0.95  : {box.map:.4f}  ({box.map*100:.1f}%)")
        print(f"  Precision      : {box.mp:.4f}  ({box.mp*100:.1f}%)")
        print(f"  Recall         : {box.mr:.4f}  ({box.mr*100:.1f}%)")
        f1 = 2 * box.mp * box.mr / (box.mp + box.mr + 1e-9)
        print(f"  F1 Score       : {f1:.4f}  ({f1*100:.1f}%)")
        print(f"{'='*60}")
        print("  Interpretation:")
        if box.map50 >= 0.6:
            print("  mAP@50 >= 60%  : Good detection performance")
        elif box.map50 >= 0.4:
            print("  mAP@50 >= 40%  : Moderate — try more epochs or larger model")
        else:
            print("  mAP@50 < 40%   : Low — increase epochs, dataset size, or image size")
    except Exception as e:
        print(f"  (Could not parse metrics: {e})")
        print(f"  Raw: {metrics}")

if __name__ == "__main__":
    main()
