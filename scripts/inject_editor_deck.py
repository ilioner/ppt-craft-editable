#!/usr/bin/env python3
"""
inject_editor_deck.py — 把 deck.json 注入 Phase C 编辑器壳子

工作方式：
  把 deck.json 内容序列化后，作为 window.__phaseCDeck 注入到 editor_shell/index.html，
  生成一个 *_filled.html。打开它就直接看到用户的页面 + 文字框，可以拖拽编辑。

为什么需要这个：
  浏览器出于安全限制不能跨目录读本地文件，所以编辑器要"自带数据"才能在
  file:// 协议下可靠工作。

用法:
  python3 scripts/inject_editor_deck.py \\
      --shell assets/editor_shell/index.html \\
      --deck  phaseC/deck.json \\
      --out   phaseC/editor.html

  # 默认保留 deck.json 里的相对路径背景图（适合 HTML 与背景图放在同一目录）
  # 加 --file-url 会把相对路径重写成绝对 file:// URL（适合本地打开）
  # 加 --inline 会把背景图 base64 嵌入 HTML，便于离线分发，但 HTML 可能很大
  # 推荐布局：phaseC/editor.html + phaseC/backgrounds/ 同目录旁置

依赖: 无（标准库）
"""

from __future__ import annotations
import argparse
import base64
import json
import mimetypes
import sys
from pathlib import Path


def to_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def to_file_url(path: Path) -> str:
    return f"file://{path.resolve()}"


def rewrite_backgrounds(deck: dict, deck_dir: Path,
                        mode: str) -> dict:
    """根据模式重写每页 background 路径。"""
    new = json.loads(json.dumps(deck))  # deep copy
    for s in new.get("slides", []):
        bg = s.get("background", "")
        if not bg:
            continue
        p = Path(bg)
        if not p.is_absolute():
            p = (deck_dir / p).resolve()
        if not p.exists():
            print(f"[warn] 背景图不存在：{p}", file=sys.stderr)
            continue
        if mode == "data":
            s["background"] = to_data_url(p)
        elif mode == "file":
            s["background"] = to_file_url(p)
        else:  # keep
            pass
    return new


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--shell", required=True, type=Path,
                    help="editor_shell/index.html 原模板路径")
    ap.add_argument("--deck",  required=True, type=Path,
                    help="deck.json 路径")
    ap.add_argument("--out",   required=True, type=Path,
                    help="输出 HTML 路径（建议 *_filled.html）")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--inline", action="store_true",
                   help="把背景图 base64 嵌入 HTML（适合离线分发；HTML 会变大）")
    g.add_argument("--keep-paths", action="store_true",
                   help="保留 deck.json 原本的 background 路径（默认；适合 HTML 与背景图同目录）")
    g.add_argument("--file-url", action="store_true",
                   help="把相对路径重写成绝对 file:// URL（适合本地打开）")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    if not args.shell.exists():
        sys.exit(f"shell 不存在: {args.shell}")
    if not args.deck.exists():
        sys.exit(f"deck 不存在: {args.deck}")

    mode = "data" if args.inline else ("file" if args.file_url else "keep")
    deck = json.loads(args.deck.read_text(encoding="utf-8"))
    deck = rewrite_backgrounds(deck, args.deck.parent.resolve(), mode)

    html = args.shell.read_text(encoding="utf-8")
    # 注入到 <head> 末尾的 script
    inject = (
        "\n<script>window.__phaseCDeck = "
        + json.dumps(deck, ensure_ascii=False)
        + ";</script>\n"
    )
    if "</head>" not in html:
        sys.exit("壳子 HTML 里没有 </head>，注入失败")
    html = html.replace("</head>", inject + "</head>", 1)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"[ok] 已注入 → {args.out}")
    print(f"     mode = {mode} ({len(deck.get('slides', []))} 页)")
    if mode == "file":
        print("[hint] 用 file:// 模式：HTML 和背景图需要保持相对位置；"
              "如果要打包给别人打开，改用 --keep-paths 或 --inline 重新生成")
    elif mode == "keep":
        print("[hint] keep 模式：请把 editor.html 和 backgrounds/ 放在相对稳定的位置，"
              "避免移动后背景路径失效")


if __name__ == "__main__":
    main()
