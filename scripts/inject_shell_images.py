#!/usr/bin/env python3
"""
inject_shell_images.py — Phase A 三个 HTML 工作流壳子的图片注入器。

为什么需要这个脚本：
  assets/preview_shell/index.html 等三个壳子的默认状态里，
  图片 src 是写死的 SVG 占位图（写着 "Cover preview placeholder"）。
  原本设计是 agent 出完真实图后自己去替换 HTML。
  这个脚本把替换动作做成一行命令，避免出现 "壳子打开了但图没链接上" 的情况。

支持的三种壳子：

1) preview      （Stage 2 风格预览）
   data JSON 形如：
     {
       "A": {
         "scheme_title": "方案 A｜稳妥商务科技",        # 可选
         "scheme_subtitle": "适合正式汇报 ...",          # 可选
         "meta": {                                       # 可选 — 覆盖右侧 5 段 meta
           "一句话定位": "...",
           "封面页方向": "...",
           "正文页视觉语法": "...",
           "适用场景": "...",
           "风险点": "..."
         },
         "cover":  "phaseA/previews/A-cover.png",
         "toc":    "phaseA/previews/A-toc.png",
         "body":   "phaseA/previews/A-body.png",
         "captions": {                                   # 可选 — 覆盖三张图的 caption
           "cover": "...",
           "toc":   "...",
           "body":  "..."
         }
       },
       "B": { ... },
       "C": { ... }
     }
   group key 必须是已经存在于 HTML 里的方案代号（默认 "A" / "B" / "C"），
   每个方案下三张图的 key 必须是 cover / toc / body（分别对应 button 的
   data-preview-index 0 / 1 / 2）。

2) candidate    （Stage 4 多候选选图）
   data JSON 形如：
     {
       "slides": [
         {
           "id": "01-cover",                # 必须
           "title": "封面",                 # 可选
           "subtitle": "首页 / Hero",       # 可选
           "palette": ["#0F2A4D", "#F5C24A"], # 可选 — 仅作占位备用
           "candidates": [                  # 至少 1 张，可多张
             "phaseA/candidates/01/cand-01.png",
             "phaseA/candidates/01/cand-02.png"
           ]
         },
         ...
       ]
     }

3) review       （Stage 5 评审）
   data JSON 形如：
     {
       "slides": [
         {
           "id": "01-cover",                # 必须
           "title": "封面",                 # 可选
           "subtitle": "首页 / Hero",       # 可选
           "image": "phaseA/slides/01-cover.png"   # 必须
         },
         ...
       ]
     }

用法：

  python3 scripts/inject_shell_images.py preview \
      --shell  assets/preview_shell/index.html \
      --data   preview_data.json \
      [--out   phaseA/previews/preview_filled.html] \
      [--inline]   # 把图片转 base64 嵌入，离线也能开

  python3 scripts/inject_shell_images.py candidate \
      --shell  assets/candidate_picker_shell/index.html \
      --data   candidate_data.json \
      [--out   phaseA/candidates/picker_filled.html] \
      [--inline]

  python3 scripts/inject_shell_images.py review \
      --shell  assets/review_shell/index.html \
      --data   review_data.json \
      [--out   phaseA/review/review_filled.html] \
      [--inline]

默认行为：
  - 写到与 --shell 同目录的 <basename>.filled.html（不覆盖原模板）；
    用 --out 指定目标路径可改。
  - 默认把图片路径写成相对路径（相对 --out 文件所在目录）；
    --inline 会把所有图片读成 base64 data URL 嵌入到 HTML 里，
    适合离线分发或邮件发给客户。
"""

from __future__ import annotations

import argparse
import base64
import html as html_lib
import json
import mimetypes
import re
import sys
from pathlib import Path


# ─────────────────────────────────────────────────────────
# 通用工具
# ─────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_image(img: str, data_dir: Path, out_dir: Path, inline: bool) -> str:
    """
    把用户在 JSON 里写的 img 路径，转成 HTML 的 src 字段。

    - inline=True：读图 → base64 data URL（离线可开，文件变大）
    - inline=False（默认）：写成相对 out 文件目录的相对路径
    """
    p = Path(img)
    if not p.is_absolute():
        # 用户给的相对路径，相对 data JSON 所在目录解析
        p = (data_dir / p).resolve()

    if inline:
        if not p.exists():
            raise SystemExit(f"[inject] 图片不存在: {p}")
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"

    # 非 inline：返回相对 out 目录的相对路径
    try:
        rel = Path.relative_to(p, out_dir)
        return str(rel).replace("\\", "/")
    except ValueError:
        # 不在 out 子树下，退化成绝对路径
        return f"file://{p}"


def _js_escape(text: str) -> str:
    """把字符串放进 JS 模板字符串里时的最小转义。"""
    return (
        text.replace("\\", "\\\\")
            .replace("`", "\\`")
            .replace("${", "\\${")
    )


# ─────────────────────────────────────────────────────────
# preview 壳子注入
# ─────────────────────────────────────────────────────────

INDEX_TO_KEY = {0: "cover", 1: "toc", 2: "body"}


def inject_preview(html: str, data: dict, data_dir: Path, out_dir: Path,
                   inline: bool) -> str:
    """
    替换每个 button 后面的 <img class="preview-image" src="..."> 为真实图。
    定位方式：data-preview-group + data-preview-index。
    """
    # 匹配 <button class="preview-button" ... data-preview-group="X" data-preview-index="N" ...>...<img class="preview-image" src="...">
    pattern = re.compile(
        r'(<button class="preview-button"[^>]*?'
        r'data-preview-group="([^"]+)"[^>]*?'
        r'data-preview-index="(\d+)"[^>]*?>\s*)'
        r'(<img class="preview-image" src=")([^"]*)(")',
        flags=re.DOTALL,
    )

    missing: list[tuple[str, str]] = []

    def repl(m: re.Match) -> str:
        head, group, idx_str, img_prefix, _old_src, img_suffix = m.groups()
        idx = int(idx_str)
        key = INDEX_TO_KEY.get(idx)
        scheme = data.get(group)
        if scheme is None or key is None or key not in scheme:
            missing.append((group, key or f"index={idx}"))
            return m.group(0)  # 保持原占位
        new_src = _resolve_image(scheme[key], data_dir, out_dir, inline)
        return f"{head}{img_prefix}{new_src}{img_suffix}"

    new_html = pattern.sub(repl, html)

    if missing:
        sys.stderr.write(
            f"[preview] 警告：以下方案缺图，保持占位：{missing}\n"
        )

    # 同时按需替换方案标题 / 副标 / meta / caption
    new_html = _patch_preview_meta(new_html, data)

    return new_html


def _patch_preview_meta(html: str, data: dict) -> str:
    """
    可选：替换每个 scheme 的标题/副标/meta/caption。
    通过 data-scheme + data-preview-group 的组合定位区块，
    再用更细的局部正则替换。

    注意：壳子 HTML 里没有 data-scheme-code 这种区分属性，三个 <section class="scheme">
    按出现顺序对应 A / B / C，本函数也按这个顺序做替换。
    """
    sections = list(re.finditer(
        r'(<section class="scheme" data-scheme>)(.*?)(</section>)',
        html,
        flags=re.DOTALL,
    ))
    if not sections:
        return html

    group_keys = sorted(data.keys())  # 例如 ['A','B','C']
    new_html_parts = []
    last_end = 0
    for idx, m in enumerate(sections):
        new_html_parts.append(html[last_end:m.start()])
        block_open, block_body, block_close = m.groups()
        # 找当前 section 内嵌的 group key（从 data-preview-group 抽）
        gmatch = re.search(r'data-preview-group="([^"]+)"', block_body)
        if gmatch:
            current_group = gmatch.group(1)
        else:
            current_group = group_keys[idx] if idx < len(group_keys) else None

        scheme = data.get(current_group, {}) if current_group else {}

        # 替换方案标题
        if "scheme_title" in scheme:
            block_body = re.sub(
                r'(<h2 class="scheme-title">)(.*?)(</h2>)',
                lambda mm: mm.group(1) + html_lib.escape(scheme["scheme_title"]) + mm.group(3),
                block_body,
                count=1,
                flags=re.DOTALL,
            )
        if "scheme_subtitle" in scheme:
            block_body = re.sub(
                r'(<p class="scheme-subtitle">)(.*?)(</p>)',
                lambda mm: mm.group(1) + html_lib.escape(scheme["scheme_subtitle"]) + mm.group(3),
                block_body,
                count=1,
                flags=re.DOTALL,
            )

        # 替换 meta 区段
        meta_dict = scheme.get("meta") or {}
        if meta_dict:
            def meta_repl(mm: re.Match) -> str:
                label = mm.group(2).strip()
                new_value = meta_dict.get(label)
                if new_value is None:
                    return mm.group(0)
                return (
                    mm.group(1) + mm.group(2) + mm.group(3) +
                    mm.group(4) + html_lib.escape(new_value) + mm.group(6)
                )
            block_body = re.sub(
                r'(<div class="meta-label">)([^<]+)(</div>\s*)'
                r'(<div class="meta-value">)([^<]+)(</div>)',
                meta_repl,
                block_body,
                flags=re.DOTALL,
            )

        # 替换 caption（按 cover/toc/body 顺序对应三个 preview-caption）
        captions = scheme.get("captions") or {}
        if captions:
            caption_iter = iter(["cover", "toc", "body"])
            def caption_repl(mm: re.Match) -> str:
                try:
                    key = next(caption_iter)
                except StopIteration:
                    return mm.group(0)
                if key not in captions:
                    return mm.group(0)
                return mm.group(1) + html_lib.escape(captions[key]) + mm.group(3)
            block_body = re.sub(
                r'(<div class="preview-caption">)([^<]*)(</div>)',
                caption_repl,
                block_body,
                flags=re.DOTALL,
            )

        new_html_parts.append(block_open + block_body + block_close)
        last_end = m.end()

    new_html_parts.append(html[last_end:])
    return "".join(new_html_parts)


# ─────────────────────────────────────────────────────────
# candidate_picker 壳子注入
# ─────────────────────────────────────────────────────────

def inject_candidate(html: str, data: dict, data_dir: Path, out_dir: Path,
                     inline: bool) -> str:
    """
    用真实数据替换 candidate_picker_shell 里写死的 slideBlueprints 数组。
    替换策略：直接替换 `const slideBlueprints = [...]` 这段 JS 字面量。
    """
    slides = data.get("slides") or []
    if not slides:
        raise SystemExit("[candidate] data JSON 缺少 'slides' 字段或为空")

    js_slides = []
    for s in slides:
        sid = s.get("id")
        if not sid:
            raise SystemExit(f"[candidate] slide 缺少 id: {s}")
        cands_raw = s.get("candidates") or []
        if not cands_raw:
            raise SystemExit(f"[candidate] slide {sid} 没有 candidates")
        cand_srcs = [_resolve_image(c, data_dir, out_dir, inline) for c in cands_raw]
        js_slides.append({
            "id": sid,
            "title": s.get("title", sid),
            "subtitle": s.get("subtitle", ""),
            "palette": s.get("palette", ["#1f2937", "#f59e0b", "#ffffff"]),
            "candidates": cand_srcs,
        })

    # 渲染为 JS 字面量
    js_literal = "const slideBlueprints = " + json.dumps(js_slides, ensure_ascii=False, indent=2) + ";"

    # 同时禁用原 buildCandidates 占位生成（候选直接来自数据，不再 SVG 生成）
    # 用一段 JS 钩子：如果 slide 已有 candidates，就跳过生成
    js_hook = (
        "\n    // injected: skip SVG candidate generation when real images provided\n"
        "    const __origBuildCandidates = typeof buildCandidates === 'function' ? buildCandidates : null;\n"
        "    if (__origBuildCandidates) {\n"
        "      window.buildCandidates = function(slide) {\n"
        "        if (Array.isArray(slide.candidates) && slide.candidates.length) {\n"
        "          return slide.candidates.map((src, i) => ({\n"
        "            code: `${slide.id}-${String(i+1).padStart(2,'0')}`,\n"
        "            image: src,\n"
        "            description: ''\n"
        "          }));\n"
        "        }\n"
        "        return __origBuildCandidates(slide);\n"
        "      };\n"
        "    }\n"
    )

    new_html, n = re.subn(
        r'const slideBlueprints = \[[\s\S]*?\];',
        lambda m: js_literal + js_hook,
        html,
        count=1,
    )
    if n == 0:
        raise SystemExit(
            "[candidate] 未在 HTML 中找到 'const slideBlueprints = [...]'，"
            "壳子结构可能已变化，请检查 candidate_picker_shell/index.html"
        )
    return new_html


# ─────────────────────────────────────────────────────────
# review 壳子注入
# ─────────────────────────────────────────────────────────

def inject_review(html: str, data: dict, data_dir: Path, out_dir: Path,
                  inline: bool) -> str:
    """
    用真实数据替换 review_shell 里写死的 sampleSlides 数组。
    """
    slides = data.get("slides") or []
    if not slides:
        raise SystemExit("[review] data JSON 缺少 'slides' 字段或为空")

    js_slides = []
    for s in slides:
        sid = s.get("id")
        if not sid:
            raise SystemExit(f"[review] slide 缺少 id: {s}")
        img = s.get("image")
        if not img:
            raise SystemExit(f"[review] slide {sid} 缺少 image 字段")
        js_slides.append({
            "id": sid,
            "title": s.get("title", sid),
            "subtitle": s.get("subtitle", ""),
            "image": _resolve_image(img, data_dir, out_dir, inline),
        })

    js_literal = "const sampleSlides = " + json.dumps(js_slides, ensure_ascii=False, indent=2) + ";"

    # 同时清空 localStorage 缓存，避免上一次评审遗留把新数据盖住
    js_hook = (
        "\n    // injected: clear stale review state when new data is loaded\n"
        "    try { localStorage.removeItem(STORAGE_KEY); } catch (e) { /* noop */ }\n"
    )

    new_html, n = re.subn(
        r'const sampleSlides = \[[\s\S]*?\];',
        lambda m: js_literal,
        html,
        count=1,
    )
    if n == 0:
        raise SystemExit(
            "[review] 未在 HTML 中找到 'const sampleSlides = [...]'，"
            "壳子结构可能已变化，请检查 review_shell/index.html"
        )

    # 在 STORAGE_KEY 定义之后插入清缓存的 hook
    new_html, n2 = re.subn(
        r"(const STORAGE_KEY = '[^']+';)",
        lambda m: m.group(1) + js_hook,
        new_html,
        count=1,
    )
    return new_html


# ─────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────

INJECTORS = {
    "preview": inject_preview,
    "candidate": inject_candidate,
    "review": inject_review,
}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="把真实生成图注入 Phase A 三个工作流壳子（preview / candidate / review）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("shell_type", choices=sorted(INJECTORS.keys()),
                    help="要注入的壳子类型")
    ap.add_argument("--shell", required=True, type=Path,
                    help="原始壳子 HTML 路径（assets/.../index.html）")
    ap.add_argument("--data", required=True, type=Path,
                    help="包含图片路径和元数据的 JSON 文件")
    ap.add_argument("--out", type=Path,
                    help="输出 HTML 路径（默认与 --shell 同目录的 <basename>.filled.html）")
    ap.add_argument("--inline", action="store_true",
                    help="把图片转 base64 嵌入 HTML（离线可开，但文件较大）")
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    shell_path: Path = args.shell.resolve()
    data_path: Path = args.data.resolve()

    if not shell_path.exists():
        raise SystemExit(f"shell 不存在: {shell_path}")
    if not data_path.exists():
        raise SystemExit(f"data 不存在: {data_path}")

    if args.out:
        out_path = args.out.resolve()
    else:
        out_path = shell_path.with_name(shell_path.stem + ".filled.html")

    html = _read(shell_path)
    data = _load_json(data_path)

    out_dir = out_path.parent
    data_dir = data_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    new_html = INJECTORS[args.shell_type](html, data, data_dir, out_dir, args.inline)
    _write(out_path, new_html)

    print(f"[ok] 已注入 {args.shell_type} 壳子 → {out_path}")
    if not args.inline:
        print("[hint] 当前为相对路径模式。打开此 HTML 时图片必须仍存在于 JSON 指定路径；"
              "如需打包分发可加 --inline。")


if __name__ == "__main__":
    main()
