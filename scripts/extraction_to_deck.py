#!/usr/bin/env python3
"""
extraction_to_deck.py — 把 Phase D 的 confirmed extraction 转成 Phase C deck.json。

输入既可以是纯 JSON，也可以是 review 页导出的整段 sentinel 文本。

用法：
  python3 scripts/extraction_to_deck.py \
      --input phaseD/extraction_confirmed.json \
      --output phaseC/deck.json

  # 顺手生成 editor.html
  python3 scripts/extraction_to_deck.py \
      --input phaseD/extraction_confirmed.json \
      --output phaseC/deck.json \
      --editor-out phaseC/editor.html
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from inject_editor_deck import rewrite_backgrounds  # noqa: E402
from phase_d_utils import clamp01, dump_json, load_extraction_payload  # noqa: E402
from validate_deck_json import print_result, validate_deck_file  # noqa: E402


DEFAULT_FONT = "PingFang SC"
DEFAULT_FONT_SIZE_PT = 18
DEFAULT_COLOR = "#1A1A1A"
ROLE_DEFAULT_SIZE = {
    "title": 1.0,
    "subtitle": 0.85,
    "body": 1.0,
    "footer": 0.78,
    "caption": 0.85,
    "label": 0.9,
    "annotation": 0.9,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", required=True, type=Path, help="confirmed extraction JSON 或导出文本")
    parser.add_argument("--output", default=Path("phaseC/deck.json"), type=Path, help="输出 deck.json")
    parser.add_argument("--backgrounds-dir", type=Path,
                        help="背景图目录；默认用 output 同级的 backgrounds/")
    parser.add_argument("--shell", default=Path("assets/editor_shell/index.html"), type=Path,
                        help="editor shell 模板")
    parser.add_argument("--editor-out", type=Path, help="若提供，则同时生成注入后的 editor.html")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--file-url", dest="editor_mode", action="store_const", const="file",
                      help="editor 背景改写为 file:// 绝对路径")
    mode.add_argument("--inline", dest="editor_mode", action="store_const", const="data",
                      help="editor 背景内联为 data URL")
    mode.add_argument("--keep-paths", dest="editor_mode", action="store_const", const="keep",
                      help="保留 deck 背景路径（默认）")
    parser.set_defaults(editor_mode="keep")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    extraction_path = args.input.resolve()
    output_path = args.output.resolve()
    backgrounds_dir = (args.backgrounds_dir.resolve()
                       if args.backgrounds_dir
                       else (output_path.parent / "backgrounds").resolve())

    extraction = load_extraction_payload(extraction_path)
    deck = build_deck(extraction, output_path.parent, backgrounds_dir)
    dump_json(output_path, deck)
    print(f"[ok] deck.json → {output_path}")

    validation = validate_deck_file(output_path)
    print_result(validation)
    if not validation.ok:
        return 1

    if args.editor_out:
        write_editor(
            shell_path=args.shell.resolve(),
            deck_path=output_path,
            out_path=args.editor_out.resolve(),
            mode=args.editor_mode,
        )

    print("[next] 如果还没生成背景图，先跑 generate_backgrounds_from_pdf.py。")
    print("[next] 拿到用户从 phaseC/editor.html 导出的 deck 包后，再跑 json_to_pptx.py 渲染 PPTX。")
    return 0


def build_deck(extraction: dict[str, Any], deck_dir: Path, backgrounds_dir: Path) -> dict[str, Any]:
    pages = extraction.get("pages", [])
    if not isinstance(pages, list):
        raise SystemExit("extraction.pages 必须是数组")

    defaults = infer_deck_defaults(pages)
    slides = []

    for idx, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            continue
        page_index = int(page.get("page_index", idx) or idx)
        slide = {
            "id": f"{page_index:02d}-{page.get('page_type', 'slide')}",
            "background": relative_background_ref(deck_dir, backgrounds_dir / f"{page_index:02d}.png"),
            "text_boxes": build_text_boxes(page, defaults),
        }
        slides.append(slide)

    return {
        "deck": {
            "ratio": extraction.get("aspect_ratio", "16:9"),
            "default_font": defaults["default_font"],
            "default_font_size_pt": defaults["default_font_size_pt"],
            "default_color": defaults["default_color"],
        },
        "slides": slides,
    }


def infer_deck_defaults(pages: list[Any]) -> dict[str, Any]:
    colors: list[str] = []
    font_sizes: list[float] = []

    for page in pages:
        if not isinstance(page, dict):
            continue
        for box in page.get("text_boxes", []):
            if not isinstance(box, dict):
                continue
            style_hint = box.get("style_hint", {})
            if isinstance(style_hint, dict):
                color = style_hint.get("color")
                if isinstance(color, str) and color.startswith("#"):
                    colors.append(color.upper())
            try:
                font_sizes.append(float(box.get("font_size_est", DEFAULT_FONT_SIZE_PT)))
            except (TypeError, ValueError):
                continue

    default_color = Counter(colors).most_common(1)[0][0] if colors else DEFAULT_COLOR
    if font_sizes:
        default_font_size = round(sum(font_sizes) / len(font_sizes), 1)
    else:
        default_font_size = DEFAULT_FONT_SIZE_PT

    return {
        "default_font": DEFAULT_FONT,
        "default_font_size_pt": max(10, default_font_size),
        "default_color": default_color,
    }


def build_text_boxes(page: dict[str, Any], defaults: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, box in enumerate(page.get("text_boxes", []), start=1):
        if not isinstance(box, dict):
            continue
        text = str(box.get("text", "")).strip()
        if not text:
            continue

        bbox_norm = normalize_bbox_norm(box.get("bbox_norm"))
        style_hint = box.get("style_hint", {})
        if not isinstance(style_hint, dict):
            style_hint = {}

        weight = str(style_hint.get("weight", "regular")).lower()
        color = str(style_hint.get("color", defaults["default_color"])).upper()
        align = str(style_hint.get("align", "left")).lower()
        italic = bool(style_hint.get("italic", False))
        font_size_pt = infer_font_size(box, defaults)

        output.append({
            "id": str(box.get("id") or f"tb-{page.get('page_index', 1)}-{index}"),
            "text": text,
            "x": bbox_norm[0],
            "y": bbox_norm[1],
            "w": bbox_norm[2],
            "h": bbox_norm[3],
            "font_family": DEFAULT_FONT,
            "font_size_pt": font_size_pt,
            "color": color if color.startswith("#") else defaults["default_color"],
            "bold": weight == "bold",
            "italic": italic,
            "align": align if align in {"left", "center", "right", "justify"} else "left",
            "valign": "top",
            "line_spacing": 1.2,
        })
    return output


def infer_font_size(box: dict[str, Any], defaults: dict[str, Any]) -> float:
    try:
        base = float(box.get("font_size_est"))
    except (TypeError, ValueError):
        role = str(box.get("role", "body")).lower()
        base = float(defaults["default_font_size_pt"]) * ROLE_DEFAULT_SIZE.get(role, 1.0)
    return round(max(8.0, base), 1)


def normalize_bbox_norm(raw_bbox: Any) -> list[float]:
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        return [0.1, 0.1, 0.8, 0.1]
    x, y, width, height = raw_bbox
    try:
        x = clamp01(float(x))
        y = clamp01(float(y))
        width = max(0.01, clamp01(float(width)))
        height = max(0.01, clamp01(float(height)))
    except (TypeError, ValueError):
        return [0.1, 0.1, 0.8, 0.1]
    if x + width > 1:
        width = max(0.01, 1 - x)
    if y + height > 1:
        height = max(0.01, 1 - y)
    return [round(x, 4), round(y, 4), round(width, 4), round(height, 4)]


def relative_background_ref(deck_dir: Path, background_path: Path) -> str:
    import os
    return os.path.relpath(background_path.resolve(), deck_dir.resolve()).replace("\\", "/")


def write_editor(shell_path: Path, deck_path: Path, out_path: Path, mode: str) -> None:
    if not shell_path.exists():
        raise SystemExit(f"editor shell 不存在: {shell_path}")
    deck = json.loads(deck_path.read_text(encoding="utf-8"))
    deck = rewrite_backgrounds(deck, deck_path.parent.resolve(), mode)
    html = shell_path.read_text(encoding="utf-8")
    inject = (
        "\n<script>window.__phaseCDeck = "
        + json.dumps(deck, ensure_ascii=False)
        + ";</script>\n"
    )
    if "</head>" not in html:
        raise SystemExit("壳子 HTML 里没有 </head>，注入失败")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html.replace("</head>", inject + "</head>", 1), encoding="utf-8")
    print(f"[ok] editor.html → {out_path} (mode={mode})")


if __name__ == "__main__":
    raise SystemExit(main())
