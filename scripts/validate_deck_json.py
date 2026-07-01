#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


SAFE_FONT_SET = {
    "PingFang SC", "PingFang TC", "PingFang HK",
    "Microsoft YaHei", "Microsoft YaHei UI",
    "Hiragino Sans GB", "Heiti SC",
    "Source Han Sans CN", "Source Han Sans SC",
    "Arial", "Helvetica", "Helvetica Neue",
    "Verdana", "Tahoma", "Calibri",
    "Times New Roman", "Georgia",
    "SimSun", "SimHei", "KaiTi", "FangSong",
    "Courier New", "Consolas", "Menlo", "Monaco",
}

ALIGN_VALUES = {"left", "center", "right", "justify"}
VALIGN_VALUES = {"top", "middle", "bottom"}
RATIO_VALUES = {"16:9", "4:3", "3:2", "1:1"}
HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_error(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def add_warning(self, path: str, message: str) -> None:
        self.warnings.append(f"{path}: {message}")


def load_deck_data(json_path: Path) -> Any:
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON 解析失败: {json_path}:{exc.lineno}:{exc.colno} {exc.msg}") from exc


def normalize_deck(data: Any) -> tuple[dict[str, Any], list[Any]]:
    if not isinstance(data, dict):
        return {}, []
    if "slides" not in data and "text_boxes" in data:
        return {}, [data]
    deck_cfg = data.get("deck", {})
    slides = data.get("slides", [])
    return deck_cfg if isinstance(deck_cfg, dict) else {}, slides if isinstance(slides, list) else []


def validate_deck_file(json_path: Path, *, strict_fonts: bool = False) -> ValidationResult:
    data = load_deck_data(json_path)
    result = ValidationResult()
    if not isinstance(data, dict):
        result.add_error("$", "顶层必须是 JSON object")
        return result

    deck_cfg, slides = normalize_deck(data)
    base_dir = json_path.parent
    validate_deck_config(deck_cfg, result, strict_fonts)

    if not slides:
        result.add_error("slides", "缺少 slides 数组，或单页 schema 缺少 text_boxes")
        return result

    for index, slide in enumerate(slides, start=1):
        validate_slide(slide, index, base_dir, deck_cfg, result, strict_fonts)
    return result


def validate_deck_config(deck_cfg: dict[str, Any], result: ValidationResult,
                         strict_fonts: bool) -> None:
    ratio = deck_cfg.get("ratio")
    if ratio is not None and ratio not in RATIO_VALUES:
        result.add_warning("deck.ratio", f"未知比例 {ratio!r}，渲染器会回落到 16:9")

    default_font = deck_cfg.get("default_font")
    if default_font is not None:
        validate_font("deck.default_font", default_font, result, strict_fonts)

    default_size = deck_cfg.get("default_font_size_pt")
    if default_size is not None:
        validate_positive_number("deck.default_font_size_pt", default_size, result)

    default_color = deck_cfg.get("default_color")
    if default_color is not None:
        validate_color("deck.default_color", default_color, result)


def validate_slide(slide: Any, index: int, base_dir: Path, deck_cfg: dict[str, Any],
                   result: ValidationResult, strict_fonts: bool) -> None:
    path = f"slides[{index - 1}]"
    if not isinstance(slide, dict):
        result.add_error(path, "每页必须是 object")
        return

    slide_id = slide.get("id") or f"#{index}"
    slide_path = f"{path}({slide_id})"
    background = slide.get("background")
    if not background:
        result.add_error(f"{slide_path}.background", "缺少 background 字段")
    elif isinstance(background, str):
        validate_background(f"{slide_path}.background", background, base_dir, result)
    else:
        result.add_error(f"{slide_path}.background", "background 必须是字符串")

    text_boxes = slide.get("text_boxes", [])
    if not isinstance(text_boxes, list):
        result.add_error(f"{slide_path}.text_boxes", "text_boxes 必须是数组")
        return

    default_font = deck_cfg.get("default_font", "PingFang SC")
    default_color = deck_cfg.get("default_color", "#1a1a1a")
    for tb_index, text_box in enumerate(text_boxes):
        validate_text_box(text_box, f"{slide_path}.text_boxes[{tb_index}]",
                          default_font, default_color, result, strict_fonts)


def validate_background(path: str, ref: str, base_dir: Path, result: ValidationResult) -> None:
    if ref.startswith("data:"):
        header, sep, payload = ref.partition(",")
        if not sep or not payload:
            result.add_error(path, "data URL 缺少 payload")
            return
        if ";base64" in header:
            try:
                base64.b64decode(payload, validate=True)
            except Exception as exc:
                result.add_error(path, f"data URL base64 无效: {type(exc).__name__}")
        return

    parsed = urlparse(ref)
    if parsed.scheme in {"http", "https"}:
        result.add_error(path, "渲染器不支持网络背景 URL，请先下载到本地或用 data URL")
        return
    if parsed.scheme == "file":
        bg_path = Path(unquote(parsed.path))
    else:
        bg_path = Path(ref)
        if not bg_path.is_absolute():
            bg_path = (base_dir / bg_path).resolve()
    if not bg_path.exists():
        result.add_error(path, f"背景图不存在: {bg_path}")


def validate_text_box(text_box: Any, path: str, default_font: str, default_color: str,
                      result: ValidationResult, strict_fonts: bool) -> None:
    if not isinstance(text_box, dict):
        result.add_error(path, "文字框必须是 object")
        return

    for key in ("x", "y", "w", "h"):
        if key not in text_box:
            result.add_error(f"{path}.{key}", "缺少坐标字段")
    if all(key in text_box for key in ("x", "y", "w", "h")):
        validate_box(path, text_box, result)

    text = text_box.get("text", "")
    if not isinstance(text, str):
        result.add_warning(f"{path}.text", "不是字符串，渲染器会转成字符串")

    font = text_box.get("font_family", default_font)
    validate_font(f"{path}.font_family", font, result, strict_fonts)

    font_size = text_box.get("font_size_pt")
    if font_size is not None:
        validate_positive_number(f"{path}.font_size_pt", font_size, result)

    color = text_box.get("color", default_color)
    validate_color(f"{path}.color", color, result)

    align = text_box.get("align")
    if align is not None and align not in ALIGN_VALUES:
        result.add_warning(f"{path}.align", f"未知 align={align!r}，渲染器会回落到 left")

    valign = text_box.get("valign")
    if valign is not None and valign not in VALIGN_VALUES:
        result.add_warning(f"{path}.valign", f"未知 valign={valign!r}，渲染器会回落到 top")

    line_spacing = text_box.get("line_spacing")
    if line_spacing is not None:
        number = as_float(line_spacing)
        if number is None:
            result.add_error(f"{path}.line_spacing", "必须是数字")
        elif not 0.5 <= number <= 3.0:
            result.add_warning(f"{path}.line_spacing", "建议使用 0.5~3.0 的倍数")


def validate_box(path: str, text_box: dict[str, Any], result: ValidationResult) -> None:
    values = {key: as_float(text_box[key]) for key in ("x", "y", "w", "h")}
    for key, value in values.items():
        if value is None:
            result.add_error(f"{path}.{key}", "必须是数字")
    if any(value is None for value in values.values()):
        return

    x = values["x"]
    y = values["y"]
    width = values["w"]
    height = values["h"]
    assert x is not None and y is not None and width is not None and height is not None

    if not 0 <= x <= 1:
        result.add_error(f"{path}.x", "必须在 0-1 范围内")
    if not 0 <= y <= 1:
        result.add_error(f"{path}.y", "必须在 0-1 范围内")
    if not 0 < width <= 1:
        result.add_error(f"{path}.w", "必须大于 0 且不超过 1")
    if not 0 < height <= 1:
        result.add_error(f"{path}.h", "必须大于 0 且不超过 1")
    if x + width > 1:
        result.add_error(path, "x + w 超出页面右边界")
    if y + height > 1:
        result.add_error(path, "y + h 超出页面下边界")


def validate_font(path: str, font: Any, result: ValidationResult, strict_fonts: bool) -> None:
    if not isinstance(font, str) or not font.strip():
        result.add_error(path, "字体必须是非空字符串")
        return
    if font not in SAFE_FONT_SET:
        message = f"字体 {font!r} 不在 SAFE_FONT_SET，跨平台可能 fallback"
        if strict_fonts:
            result.add_error(path, message)
        else:
            result.add_warning(path, message)


def validate_color(path: str, color: Any, result: ValidationResult) -> None:
    if not isinstance(color, str) or not HEX_COLOR_RE.match(color):
        result.add_error(path, "颜色必须是 #RGB 或 #RRGGBB")


def validate_positive_number(path: str, value: Any, result: ValidationResult) -> None:
    number = as_float(value)
    if number is None:
        result.add_error(path, "必须是数字")
    elif number <= 0:
        result.add_error(path, "必须大于 0")


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def print_result(result: ValidationResult) -> None:
    for warning in result.warnings:
        print(f"[warn] {warning}")
    for error in result.errors:
        print(f"[error] {error}")
    if result.ok:
        print(f"[ok] deck.json 校验通过（{len(result.warnings)} warning）")
    else:
        print(f"[fail] deck.json 校验失败（{len(result.errors)} error, {len(result.warnings)} warning）")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="layout.json 或 deck.json")
    parser.add_argument("--strict-fonts", action="store_true",
                        help="字体不在 SAFE_FONT_SET 时按错误处理")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = validate_deck_file(args.input.resolve(), strict_fonts=args.strict_fonts)
    print_result(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
