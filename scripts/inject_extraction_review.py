#!/usr/bin/env python3
"""
Phase D - 注入 extraction.json 到 extraction review shell

用法:
  python3 scripts/inject_extraction_review.py \\
    --shell assets/phaseD_extraction_review_shell/index.html \\
    --data phaseD/extraction.json \\
    --out phaseD/extraction_review.html
"""

import argparse
import os
import re
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from phase_d_utils import load_extraction_payload, resolve_asset_path, serialize_html_json_payload  # noqa: E402


def rewrite_review_asset_paths(extraction_data: dict, data_path: Path, output_path: Path) -> dict:
    pages = extraction_data.get("pages")
    if not isinstance(pages, list):
        return extraction_data

    for page in pages:
        if not isinstance(page, dict):
            continue
        page_image = page.get("page_image")
        if isinstance(page_image, str) and page_image and not page_image.startswith("data:"):
            resolved = resolve_asset_path(page_image, data_path)
            page["page_image"] = os.path.relpath(resolved, output_path.parent.resolve()).replace("\\", "/")
    return extraction_data


def inject_extraction_data(shell_path: Path, data_path: Path, output_path: Path):
    """
    把 extraction.json 注入到 extraction review shell 里
    """
    # 读取 shell 模板
    shell_html = shell_path.read_text(encoding='utf-8')

    # 读取 extraction data
    extraction_data = load_extraction_payload(data_path)
    extraction_data = rewrite_review_asset_paths(extraction_data, data_path.resolve(), output_path.resolve())

    payload = serialize_html_json_payload(extraction_data)

    data_script_pattern = r'<script id="extractionDataJson" type="application/json">.*?</script>'
    data_script_replacement = (
        '<script id="extractionDataJson" type="application/json">\n'
        f'{payload}\n'
        '</script>'
    )

    injected_html = re.sub(
        data_script_pattern,
        lambda _match: data_script_replacement,
        shell_html,
        count=1,
        flags=re.S,
    )

    # 写入输出
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(injected_html, encoding='utf-8')

    print(f"✓ 已注入 {len(extraction_data['pages'])} 页数据")
    print(f"✓ 输出: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="注入 extraction.json 到 review shell")
    parser.add_argument('--shell', required=True, help="Shell 模板路径")
    parser.add_argument('--data', required=True, help="extraction.json 路径")
    parser.add_argument('--out', required=True, help="输出 HTML 路径")

    args = parser.parse_args()

    shell_path = Path(args.shell)
    data_path = Path(args.data)
    output_path = Path(args.out)

    if not shell_path.exists():
        print(f"✗ Shell 文件不存在: {shell_path}")
        return 1

    if not data_path.exists():
        print(f"✗ 数据文件不存在: {data_path}")
        return 1

    inject_extraction_data(shell_path, data_path, output_path)
    return 0


if __name__ == '__main__':
    exit(main())
