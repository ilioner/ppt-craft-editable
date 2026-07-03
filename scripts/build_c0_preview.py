#!/usr/bin/env python3
"""
build_c0_preview.py — build the Phase C-only C0 overlay preview bundle.

C0 is the lightweight gate before full Phase C-only background generation. This
helper makes the gate concrete by producing three inspectable artifacts:

  phaseC/c0/deck.json
  phaseC/c0/editor.html
  phaseC/c0/preview/slide_*.png

The HTML editor is the real editable-text overlay surface. The PNG previews are
static visual checks rendered from the same text_boxes data.

Usage:
  python3 scripts/build_c0_preview.py \
      --deck phaseC/c0-source-deck.json \
      --shell assets/editor_shell/index.html \
      --out-dir phaseC/c0
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from inject_editor_deck import rewrite_backgrounds  # noqa: E402
from json_to_pptx import (  # noqa: E402
    DEFAULT_COLOR,
    DEFAULT_FONT,
    DEFAULT_FONT_SIZE_PT,
    clone_background_source,
    load_deck,
    make_presentation,
    render_preview_via_pil,
    resolve_background_source,
)
from validate_deck_json import print_result, validate_deck_file  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--deck", required=True, type=Path,
                        help="Temporary C0 deck JSON with 1-2 representative slides")
    parser.add_argument("--shell", default=Path("assets/editor_shell/index.html"), type=Path,
                        help="Editor shell template")
    parser.add_argument("--out-dir", default=Path("phaseC/c0"), type=Path,
                        help="Output directory for C0 artifacts")
    parser.add_argument("--preview-dpi", default=150, type=int,
                        help="Static preview DPI, default 150")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--file-url", dest="mode", action="store_const", const="file",
                      help="Inject editor backgrounds as absolute file:// URLs (default)")
    mode.add_argument("--inline", dest="mode", action="store_const", const="data",
                      help="Embed backgrounds as data URLs in editor.html")
    mode.add_argument("--keep-paths", dest="mode", action="store_const", const="keep",
                      help="Keep deck background paths as written")
    parser.set_defaults(mode="file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_deck = args.deck.resolve()
    shell = args.shell.resolve()
    out_dir = args.out_dir.resolve()

    if not source_deck.exists():
        print(f"[error] deck 不存在: {source_deck}", file=sys.stderr)
        return 1
    if not shell.exists():
        print(f"[error] editor shell 不存在: {shell}", file=sys.stderr)
        return 1

    validation = validate_deck_file(source_deck)
    print_result(validation)
    if not validation.ok:
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    deck_out = out_dir / "deck.json"
    preview_dir = out_dir / "preview"
    editor_out = out_dir / "editor.html"

    deck_data = json.loads(source_deck.read_text(encoding="utf-8"))
    deck_data = rewrite_relative_backgrounds(deck_data, source_deck.parent, out_dir)
    deck_out.write_text(json.dumps(deck_data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"[ok] C0 deck → {deck_out}")

    render_static_previews(deck_out, preview_dir, args.preview_dpi)
    print(f"[ok] C0 静态叠字预览 → {preview_dir}")

    write_editor(shell, deck_out, editor_out, args.mode)
    print(f"[ok] C0 可编辑叠字预览 → {editor_out}")
    print("[next] 请打开上面的 editor.html 检查背景 + 可编辑文字框；PNG 预览只作静态对照。")
    return 0


def rewrite_relative_backgrounds(deck: dict, source_dir: Path, out_dir: Path) -> dict:
    """Rewrite local relative backgrounds so copied deck.json remains valid."""
    rewritten = json.loads(json.dumps(deck))
    slides = rewritten.get("slides", [])
    if not isinstance(slides, list):
        return rewritten

    for slide in slides:
        if not isinstance(slide, dict):
            continue
        bg = slide.get("background")
        if not isinstance(bg, str) or not bg:
            continue
        if is_nonlocal_or_absolute_ref(bg):
            continue
        absolute_bg = (source_dir / bg).resolve()
        import os
        slide["background"] = os.path.relpath(absolute_bg, out_dir).replace("\\", "/")
    return rewritten


def is_nonlocal_or_absolute_ref(ref: str) -> bool:
    if ref.startswith("data:"):
        return True
    parsed = urlparse(ref)
    if parsed.scheme in {"http", "https"}:
        return True
    if parsed.scheme == "file":
        return True
    return Path(ref).is_absolute()


def render_static_previews(deck_path: Path, preview_dir: Path, dpi: int) -> None:
    deck_cfg, slides, base_dir = load_deck(deck_path)
    _prs, slide_w_in, slide_h_in = make_presentation(deck_cfg)
    default_font = deck_cfg.get("default_font", DEFAULT_FONT)
    default_font_size_pt = float(deck_cfg.get("default_font_size_pt", DEFAULT_FONT_SIZE_PT))
    default_color = deck_cfg.get("default_color", DEFAULT_COLOR)

    if preview_dir.exists():
        shutil.rmtree(preview_dir)
    preview_dir.mkdir(parents=True, exist_ok=True)

    for index, slide in enumerate(slides, start=1):
        bg_ref = slide.get("background")
        bg_source = resolve_background_source(bg_ref, base_dir)
        out_path = preview_dir / f"slide_{index:02d}.png"
        render_preview_via_pil(
            clone_background_source(bg_source),
            slide.get("text_boxes", []),
            slide_w_in,
            slide_h_in,
            out_path,
            dpi=dpi,
            default_font=default_font,
            default_font_size_pt=default_font_size_pt,
            default_color=default_color,
        )
        if not out_path.exists():
            raise SystemExit(f"C0 静态预览未生成: {out_path}")


def write_editor(shell_path: Path, deck_path: Path, out_path: Path, mode: str) -> None:
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
    html = html.replace("</head>", inject + "</head>", 1)
    out_path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
