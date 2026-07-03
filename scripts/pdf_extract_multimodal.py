#!/usr/bin/env python3
"""
Phase D - PDF 页面分类与内容抽取（多模态模型版）

这是本地可运行的 Phase D 抽取脚本，负责：
1. 渲染 PDF 每页为图片
2. 判断页面类型（extractable_text / image_only / mixed）
3. 对可提取文本页，用 PyMuPDF 提取真实文本框
4. 对图片型页面，生成需要人工补录的 review 初稿
5. 生成初版 extraction.json

依赖：
  pip install PyMuPDF  # fitz

用法：
  python3 scripts/pdf_extract_multimodal.py <pdf_path> -o phaseD/extraction.json
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError:
    print("✗ 缺少依赖: PyMuPDF")
    print("  安装: pip install PyMuPDF")
    exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from phase_d_utils import dump_json, infer_aspect_ratio, normalize_bbox, sanitize_text  # noqa: E402


DEFAULT_COLOR = "#1A1A1A"


def span_color_to_hex(color_value: Any) -> str:
    if isinstance(color_value, int):
        return f"#{(color_value >> 16) & 0xFF:02X}{(color_value >> 8) & 0xFF:02X}{color_value & 0xFF:02X}"
    return DEFAULT_COLOR


def infer_align(bbox_norm: list[float]) -> str:
    x, _y, width, _height = bbox_norm
    center = x + width / 2
    if width <= 0.75 and abs(center - 0.5) <= 0.1:
        return "center"
    if x >= 0.58:
        return "right"
    return "left"


def infer_weight(span: dict[str, Any]) -> str:
    font_name = str(span.get("font", "")).lower()
    flags = int(span.get("flags", 0) or 0)
    if "bold" in font_name or (flags & 16):
        return "bold"
    return "regular"


def infer_italic(span: dict[str, Any]) -> bool:
    flags = int(span.get("flags", 0) or 0)
    font_name = str(span.get("font", "")).lower()
    return bool(flags & 2) or "italic" in font_name or "oblique" in font_name


def classify_page(page: fitz.Page, threshold: int = 50) -> str:
    """
    判断页面类型
    - extractable_text: 有足够多的真实文本对象
    - mixed: 同时存在明显文本和图片资源
    - image_only: 几乎没有文本，主要是图片
    """
    text = page.get_text("text")
    text_len = len(text.strip())
    image_count = len(page.get_images(full=True))

    if text_len <= threshold:
        return "image_only"
    if image_count > 0 and text_len <= threshold * 4:
        return "mixed"
    return "extractable_text"


def derive_background_profile(page_type: str) -> tuple[str, str]:
    if page_type == "image_only":
        return "rebuild", "complex"
    if page_type == "mixed":
        return "clean", "moderate"
    return "clean", "simple"


def render_page_to_image(page: fitz.Page, output_path: Path, dpi: int = 150) -> None:
    """
    渲染页面为图片
    """
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    pix.save(str(output_path))


def relative_phase_d_asset(output_json: Path, asset_path: Path) -> str:
    import os
    return os.path.relpath(asset_path.resolve(), output_json.parent.resolve()).replace("\\", "/")


def generate_multimodal_prompt(page_index: int) -> str:
    """
    生成需要人工补录或外部多模态补录时的提示词模板
    """
    return f"""你正在分析第 {page_index} 页 PPT 幻灯片图片。

任务：提取页面上所有需要转成可编辑文本框的内容。

输出 JSON 格式：
{{
  "page_type": "cover | toc | content | divider",
  "background_strategy": "clean | rebuild",
  "background_complexity": "simple | moderate | complex",
  "text_boxes": [
    {{
      "role": "title | subtitle | body | footer | caption | label",
      "text": "实际文字内容",
      "bbox_norm": [x, y, width, height],
      "font_size_est": 28,
      "style_hint": {{
        "align": "left | center | right",
        "weight": "regular | bold",
        "color": "#FFFFFF"
      }},
      "confidence": 0.95
    }}
  ]
}}

规则：
1. bbox_norm 是归一化坐标，左上角 (0,0)，右下角 (1,1)
2. 标题、副标题、正文、页脚等要分开识别
3. 不要遗漏小字（比如页脚、免责声明）
4. 阅读顺序要正确（左到右、上到下）
5. 如果背景简单（纯色/渐变），推荐 "clean"；如果背景复杂（照片/图案），推荐 "rebuild"
"""


def collect_line_boxes(page: fitz.Page, page_index: int) -> list[dict[str, Any]]:
    page_dict = page.get_text("dict")
    page_rect = page.rect
    raw_boxes: list[dict[str, Any]] = []

    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue

        for line in block.get("lines", []):
            spans = [span for span in line.get("spans", []) if str(span.get("text", "")).strip()]
            if not spans:
                continue

            text = sanitize_text("".join(str(span.get("text", "")) for span in spans)).strip()
            if not text:
                continue

            x0 = min(float(span["bbox"][0]) for span in spans)
            y0 = min(float(span["bbox"][1]) for span in spans)
            x1 = max(float(span["bbox"][2]) for span in spans)
            y1 = max(float(span["bbox"][3]) for span in spans)
            bbox_norm = normalize_bbox((x0, y0, x1, y1), page_rect.width, page_rect.height)

            font_sizes = [float(span.get("size", 18) or 18) for span in spans]
            colors = [span_color_to_hex(span.get("color")) for span in spans]
            weights = [infer_weight(span) for span in spans]
            italics = [infer_italic(span) for span in spans]

            raw_boxes.append({
                "role": "body",
                "text": text,
                "bbox_norm": bbox_norm,
                "font_size_est": round(max(font_sizes), 1),
                "style_hint": {
                    "align": infer_align(bbox_norm),
                    "weight": Counter(weights).most_common(1)[0][0],
                    "color": Counter(colors).most_common(1)[0][0],
                    "italic": any(italics),
                },
                "confidence": 0.98,
                "needs_review": False,
            })

    raw_boxes.sort(key=lambda item: (item["bbox_norm"][1], item["bbox_norm"][0]))
    return assign_roles(raw_boxes, page_index)


def assign_roles(boxes: list[dict[str, Any]], page_index: int) -> list[dict[str, Any]]:
    if not boxes:
        return []

    max_font = max(float(box["font_size_est"]) for box in boxes)
    title_candidate: dict[str, Any] | None = None
    subtitle_candidate: dict[str, Any] | None = None

    ordered_for_heading = sorted(
        boxes,
        key=lambda item: (-float(item["font_size_est"]), item["bbox_norm"][1], item["bbox_norm"][0]),
    )
    for candidate in ordered_for_heading:
        y = candidate["bbox_norm"][1]
        if title_candidate is None and y <= 0.45:
            title_candidate = candidate
            continue
        if title_candidate is not None and subtitle_candidate is None and y <= 0.65:
            subtitle_candidate = candidate
            break

    finalized: list[dict[str, Any]] = []
    for index, box in enumerate(boxes, start=1):
        bbox_norm = box["bbox_norm"]
        y = bbox_norm[1]
        width = bbox_norm[2]
        size = float(box["font_size_est"])

        role = "body"
        if box is title_candidate and size >= max_font * 0.85:
            role = "title"
        elif box is subtitle_candidate and size >= max_font * 0.55:
            role = "subtitle"
        elif y >= 0.9 or (y >= 0.82 and size <= max(14.0, max_font * 0.45)):
            role = "footer"
        elif size <= max(12.0, max_font * 0.45) and width <= 0.32:
            role = "label"
        elif size <= max(11.0, max_font * 0.4):
            role = "caption"

        finalized.append({
            "id": f"p{page_index + 1}_t{index}",
            **box,
            "role": role,
        })

    return finalized


def build_page_entry(page: fitz.Page, page_index: int, page_image_ref: str) -> dict[str, Any]:
    page_type = classify_page(page)
    background_strategy, background_complexity = derive_background_profile(page_type)
    text_boxes = collect_line_boxes(page, page_index) if page_type != "image_only" else []
    issues: list[dict[str, Any]] = []

    if page_type == "image_only":
        issues.append({
            "type": "missing_text",
            "description": "该页未检测到可直接提取的 PDF 文本，请在 review 页手动补录需要编辑的文本框。",
            "box_ids": [],
        })
    elif not text_boxes:
        issues.append({
            "type": "missing_text",
            "description": "该页存在可提取文本对象，但没有成功生成文本框，请在 review 页补录。",
            "box_ids": [],
        })

    return {
        "page_index": page_index + 1,
        "page_type": page_type,
        "page_image": page_image_ref,
        "background_strategy": background_strategy,
        "background_complexity": background_complexity,
        "text_boxes": text_boxes,
        "issues": issues,
    }


def process_pdf(pdf_path: Path, output_json: Path) -> int:
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    aspect_ratio = infer_aspect_ratio(doc[0].rect.width, doc[0].rect.height) if total_pages else "16:9"

    print(f"📄 PDF: {pdf_path.name}")
    print(f"📊 总页数: {total_pages}")

    work_dir = output_json.parent / "work"
    page_images_dir = work_dir / "page_images"
    page_images_dir.mkdir(parents=True, exist_ok=True)

    pages = []
    classifications = []

    for i, page in enumerate(doc):
        print(f"  处理第 {i + 1}/{total_pages} 页...", end=" ")

        image_path = page_images_dir / f"{i + 1:02d}.png"
        render_page_to_image(page, image_path)
        page_image_ref = relative_phase_d_asset(output_json, image_path)

        page_meta = build_page_entry(page, i, page_image_ref)
        classifications.append({
            "page_index": page_meta["page_index"],
            "page_type": page_meta["page_type"],
            "background_strategy": page_meta["background_strategy"],
            "text_box_count": len(page_meta["text_boxes"]),
        })

        if page_meta["page_type"] == "image_only":
            print("✓ 图片型页面 → 需在 review 页手动补录 / 外部多模态补录")
            prompt = generate_multimodal_prompt(i + 1)
            (work_dir / f"page_{i + 1:02d}_prompt.txt").write_text(prompt, encoding="utf-8")
        else:
            print(f"✓ {page_meta['page_type']} 页面 → 已提取 {len(page_meta['text_boxes'])} 个文本框")

        pages.append(page_meta)

    doc.close()

    extraction_data = {
        "source_pdf": str(pdf_path),
        "total_pages": total_pages,
        "aspect_ratio": aspect_ratio,
        "extraction_method": "pdf_parse",
        "pages": pages,
    }

    dump_json(output_json, extraction_data)
    dump_json(work_dir / "page_classifications.json", {"pages": classifications})

    print(f"\n✓ 已生成: {output_json}")
    print(f"✓ 页面图片: {page_images_dir}")
    print(f"✓ 分类清单: {work_dir / 'page_classifications.json'}")
    print(f"\n下一步：")
    print("  1. 打开/检查 phaseD/extraction.json")
    print("  2. 对图片型页面，可参考 work/page_*_prompt.txt 在 review 页手动补录文本框")
    print(f"  3. 运行: python3 scripts/inject_extraction_review.py \\")
    print(f"           --shell assets/phaseD_extraction_review_shell/index.html \\")
    print(f"           --data {output_json} \\")
    print(f"           --out phaseD/extraction_review.html")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF 内容抽取（多模态版）")
    parser.add_argument('pdf', help="PDF 文件路径")
    parser.add_argument('-o', '--output', default='phaseD/extraction.json', help="输出 JSON 路径")

    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    output_json = Path(args.output)

    if not pdf_path.exists():
        print(f"✗ PDF 文件不存在: {pdf_path}")
        return 1

    return process_pdf(pdf_path, output_json)


if __name__ == '__main__':
    exit(main())
