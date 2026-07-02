#!/usr/bin/env python3
"""
generate_backgrounds_from_pdf.py — 根据 Phase D confirmed extraction 生成 Phase C 背景图。

输入既可以是纯 JSON，也可以是 review 页导出的整段 sentinel 文本。

MVP 策略：
- clean: 用文本框 bbox 生成 mask，局部 inpaint
- rebuild: 仍走确定性的本地 inpaint，但用更激进的参数；复杂页后续通过 Phase C review/retouch 继续修
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit("需要安装依赖：pip3 install opencv-python numpy")

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from phase_d_utils import load_extraction_payload, resolve_asset_path  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", required=True, type=Path, help="confirmed extraction JSON 或导出文本")
    parser.add_argument("--output-dir", default=Path("phaseC/backgrounds"), type=Path, help="背景图输出目录")
    parser.add_argument("--report-out", type=Path, help="可选：输出生成报告 JSON")
    parser.add_argument("--clean-radius", type=int, default=8, help="clean 策略 inpaint 半径")
    parser.add_argument("--rebuild-radius", type=int, default=12, help="rebuild 策略 inpaint 半径")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.resolve()
    output_dir = args.output_dir.resolve()
    extraction = load_extraction_payload(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = {"pages": []}
    for page in extraction.get("pages", []):
        if not isinstance(page, dict):
            continue

        page_index = int(page.get("page_index", 0) or 0)
        if page_index <= 0:
            continue

        page_image_ref = str(page.get("page_image", ""))
        source_image = resolve_asset_path(page_image_ref, input_path)
        if not source_image.exists():
            raise SystemExit(f"找不到 page_image: {page_image_ref} -> {source_image}")

        full_out = output_dir / f"{page_index:02d}-full.png"
        final_out = output_dir / f"{page_index:02d}.png"
        image = load_image(source_image)
        save_image(full_out, image)

        strategy = str(page.get("background_strategy", "clean"))
        text_boxes = page.get("text_boxes", [])
        cleaned = inpaint_background(
            image=image,
            text_boxes=text_boxes if isinstance(text_boxes, list) else [],
            strategy=strategy,
            clean_radius=args.clean_radius,
            rebuild_radius=args.rebuild_radius,
        )
        save_image(final_out, cleaned)

        report["pages"].append({
            "page_index": page_index,
            "source_image": str(source_image),
            "background_strategy": strategy,
            "text_box_count": len(text_boxes) if isinstance(text_boxes, list) else 0,
            "full_output": str(full_out),
            "background_output": str(final_out),
        })
        print(f"[ok] Page {page_index:02d} → {final_out}")

    if args.report_out:
        args.report_out.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.report_out.resolve().write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[ok] 生成报告 → {args.report_out.resolve()}")
    else:
        default_report = output_dir / "background_generation_report.json"
        default_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[ok] 生成报告 → {default_report}")

    print("[next] 用 scripts/extraction_to_deck.py 生成 phaseC/deck.json，再注入 phaseC/editor.html。")
    return 0


def load_image(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise SystemExit(f"无法读取图片: {path}")
    return image


def save_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buffer = cv2.imencode(path.suffix or ".png", image)
    if not ok:
        raise SystemExit(f"无法编码图片: {path}")
    buffer.tofile(str(path))


def inpaint_background(
    image: np.ndarray,
    text_boxes: list[Any],
    strategy: str,
    clean_radius: int,
    rebuild_radius: int,
) -> np.ndarray:
    if not text_boxes:
        return image.copy()

    has_alpha = image.ndim == 3 and image.shape[2] == 4
    if has_alpha:
        bgr = image[:, :, :3].copy()
        alpha = image[:, :, 3].copy()
    else:
        bgr = image if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        alpha = None

    height, width = bgr.shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)
    padding = compute_padding(min(height, width), strategy)
    radius = rebuild_radius if strategy == "rebuild" else clean_radius

    for text_box in text_boxes:
        bbox = text_box.get("bbox_norm") if isinstance(text_box, dict) else None
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            continue
        try:
            x, y, box_width, box_height = [float(item) for item in bbox]
        except (TypeError, ValueError):
            continue

        x0 = max(0, int(round(x * width)) - padding)
        y0 = max(0, int(round(y * height)) - padding)
        x1 = min(width, int(round((x + box_width) * width)) + padding)
        y1 = min(height, int(round((y + box_height) * height)) + padding)
        cv2.rectangle(mask, (x0, y0), (x1, y1), 255, thickness=-1)

    inpainted = cv2.inpaint(bgr, mask, radius, cv2.INPAINT_TELEA)

    if alpha is None:
        return inpainted

    alpha_out = alpha.copy()
    alpha_out[mask > 0] = 255
    return np.dstack([inpainted, alpha_out])


def compute_padding(min_dimension: int, strategy: str) -> int:
    if strategy == "rebuild":
        return max(10, int(round(min_dimension * 0.012)))
    return max(6, int(round(min_dimension * 0.006)))


if __name__ == "__main__":
    raise SystemExit(main())
