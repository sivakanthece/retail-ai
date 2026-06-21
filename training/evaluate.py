"""
Step 3 — Evaluate a trained YOLOv8 model and display all accuracy metrics.

Shows:
  - mAP@0.50 and mAP@0.50:0.95
  - Precision, Recall, F1 Score
  - Per-class breakdown
  - Confusion matrix
  - Inference speed

Usage:
  python evaluate.py --model runs/detect/sku_retail/weights/best.pt --data ./sku110k_yolo/data.yaml
  python evaluate.py --model yolov8n.pt --data ./sku110k_yolo/data.yaml   # baseline comparison
"""

import argparse
from pathlib import Path
from ultralytics import YOLO
import json

def main():
    parser = argparse.ArgumentParser(description="Evaluate YOLOv8 model")
    parser.add_argument("--model", required=True, help="Path to model weights (.pt file)")
    parser.add_argument("--data",  required=True, help="Path to data.yaml")
    parser.add_argument("--split", default="test", choices=["val","test"], help="Split to evaluate on")
    parser.add_argument("--imgsz", type=int, default=320, help="Image size")
    parser.add_argument("--conf",  type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--iou",   type=float, default=0.5,  help="IoU threshold for NMS")
    args = parser.parse_args()

    print("=" * 60)
    print("  YOLOv8 Model Evaluation")
    print("=" * 60)
    print(f"  Model  : {args.model}")
    print(f"  Data   : {args.data}")
    print(f"  Split  : {args.split}")
    print(f"  Conf   : {args.conf}")
    print(f"  IoU    : {args.iou}")
    print("=" * 60)

    model = YOLO(args.model)

    metrics = model.val(
        data    = args.data,
        split   = args.split,
        imgsz   = args.imgsz,
        conf    = args.conf,
        iou     = args.iou,
        device  = "cpu",
        plots   = True,
        verbose = True,
        workers = 0,
    )

    print_full_report(metrics, args.model)

def print_full_report(metrics, model_path):
    box = metrics.box
    speed = metrics.speed

    f1 = 2 * box.mp * box.mr / (box.mp + box.mr + 1e-9)

    print(f"\n{'='*60}")
    print("  EVALUATION REPORT")
    print(f"{'='*60}")
    print(f"\n  MODEL: {model_path}")
    print(f"\n  {'Metric':<30} {'Value':>10}")
    print(f"  {'-'*40}")
    print(f"  {'mAP @ IoU=0.50':<30} {box.map50*100:>9.2f}%")
    print(f"  {'mAP @ IoU=0.50:0.95':<30} {box.map*100:>9.2f}%")
    print(f"  {'Precision (mean)':<30} {box.mp*100:>9.2f}%")
    print(f"  {'Recall (mean)':<30} {box.mr*100:>9.2f}%")
    print(f"  {'F1 Score':<30} {f1*100:>9.2f}%")

    print(f"\n  {'Speed Metrics':<30}")
    print(f"  {'-'*40}")
    print(f"  {'Pre-process (ms/img)':<30} {speed.get('preprocess',0):>9.2f}")
    print(f"  {'Inference (ms/img)':<30} {speed.get('inference',0):>9.2f}")
    print(f"  {'Post-process (ms/img)':<30} {speed.get('postprocess',0):>9.2f}")
    total_ms = sum(speed.values())
    print(f"  {'Total (ms/img)':<30} {total_ms:>9.2f}")
    print(f"  {'FPS (approx)':<30} {1000/total_ms:>9.1f}" if total_ms > 0 else "")

    # Per-class breakdown
    try:
        print(f"\n  {'Per-Class Results':<30}")
        print(f"  {'-'*40}")
        print(f"  {'Class':<20} {'P':>8} {'R':>8} {'mAP50':>8}")
        names = metrics.names
        for i, name in names.items():
            try:
                p  = box.p[i]  if hasattr(box,'p')  and i < len(box.p)  else 0
                r  = box.r[i]  if hasattr(box,'r')  and i < len(box.r)  else 0
                ap = box.ap50[i] if hasattr(box,'ap50') and i < len(box.ap50) else 0
                print(f"  {name:<20} {p*100:>7.1f}% {r*100:>7.1f}% {ap*100:>7.1f}%")
            except (IndexError, AttributeError):
                pass
    except Exception:
        pass

    print(f"\n{'='*60}")
    print("  INTERPRETATION")
    print(f"{'='*60}")
    thresholds = [
        (0.7,  "Excellent — ready for production"),
        (0.5,  "Good — suitable for demo/capstone"),
        (0.3,  "Fair — increase epochs or dataset size"),
        (0.0,  "Poor — check dataset quality or training config"),
    ]
    for thresh, msg in thresholds:
        if box.map50 >= thresh:
            print(f"  mAP@50 = {box.map50*100:.1f}%  →  {msg}")
            break

    # Save results to JSON
    results_file = Path("evaluation_results.json")
    results = {
        "model": str(model_path),
        "mAP50": round(box.map50, 4),
        "mAP50_95": round(box.map, 4),
        "precision": round(box.mp, 4),
        "recall": round(box.mr, 4),
        "f1": round(f1, 4),
        "speed_ms": {k: round(v, 2) for k, v in speed.items()},
    }
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to: {results_file.resolve()}")
    print(f"  Confusion matrix + plots saved to: runs/detect/val/")

if __name__ == "__main__":
    main()
