from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - runtime dependency message
    raise SystemExit(
        "Pillow is required to render review markup. Install it with: python -m pip install pillow"
    ) from exc


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
DEFAULT_MARKUP_COLOR = "#bc5b28"
CIRCLED_DIGITS = {
    "①": "1",
    "②": "2",
    "③": "3",
    "④": "4",
    "⑤": "5",
    "⑥": "6",
    "⑦": "7",
    "⑧": "8",
    "⑨": "9",
    "⑩": "10",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render review-shell coordinate markup onto local slide images."
    )
    parser.add_argument("payload", type=Path, help="Path to copied review-shell-v2 JSON.")
    parser.add_argument(
        "--images",
        type=Path,
        required=True,
        help="Directory containing source slide images, usually named S01.png, S02.png, etc.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("review_marked"),
        help="Output directory for marked images and note text files.",
    )
    parser.add_argument(
        "--image-map",
        type=Path,
        help="Optional JSON object mapping page_id/page_code to exact source image paths.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_image_map(path: Path | None) -> dict[str, Path]:
    if not path:
        return {}
    raw = load_json(path)
    if not isinstance(raw, dict):
        raise ValueError("--image-map must point to a JSON object.")
    base = path.parent
    return {str(key): (base / Path(str(value))).resolve() for key, value in raw.items()}


def find_source_image(page: dict[str, Any], image_dir: Path, image_map: dict[str, Path]) -> Path:
    keys = [str(page.get("page_id") or ""), str(page.get("page_code") or "")]
    for key in keys:
        if key and key in image_map:
            return image_map[key]

    candidates: list[Path] = []
    for key in keys:
        if not key:
            continue
        for ext in IMAGE_EXTENSIONS:
            candidates.append(image_dir / f"{key}{ext}")
            candidates.append(image_dir / f"{key.lower()}{ext}")
        for ext in IMAGE_EXTENSIONS:
            candidates.extend(sorted(image_dir.glob(f"{key}*{ext}")))
            candidates.extend(sorted(image_dir.glob(f"{key.lower()}*{ext}")))

    for candidate in candidates:
        if candidate.exists():
            return candidate

    label = page.get("page_id") or page.get("page_code") or "<unknown>"
    raise FileNotFoundError(f"Could not find a source image for page {label} in {image_dir}")


def clamp01(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(max(number, 0.0), 1.0)


def hex_to_rgba(color: str | None, alpha: int = 235) -> tuple[int, int, int, int]:
    raw = (color or DEFAULT_MARKUP_COLOR).strip()
    if raw.startswith("#") and len(raw) in {4, 7}:
        if len(raw) == 4:
            r, g, b = [int(ch * 2, 16) for ch in raw[1:]]
        else:
            r, g, b = [int(raw[index : index + 2], 16) for index in (1, 3, 5)]
        return (r, g, b, alpha)
    return (188, 91, 40, alpha)


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = [
        "arialbd.ttf" if bold else "arial.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def line_width(raw_width: Any, image_width: int) -> int:
    try:
        width = float(raw_width)
    except (TypeError, ValueError):
        width = 4.0
    return max(2, round(width * image_width / 1600))


def draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    fill: tuple[int, int, int, int],
    width: int,
    dash: int,
    gap: int,
) -> None:
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    distance = math.hypot(dx, dy)
    if distance <= 0:
        return
    ux = dx / distance
    uy = dy / distance
    position = 0.0
    while position < distance:
        segment_end = min(position + dash, distance)
        draw.line(
            (
                x1 + ux * position,
                y1 + uy * position,
                x1 + ux * segment_end,
                y1 + uy * segment_end,
            ),
            fill=fill,
            width=width,
        )
        position += dash + gap


def draw_dashed_rect(
    draw: ImageDraw.ImageDraw,
    rect: tuple[float, float, float, float],
    *,
    fill: tuple[int, int, int, int],
    width: int,
) -> None:
    x, y, w, h = rect
    dash = max(10, width * 5)
    gap = max(7, width * 4)
    draw_dashed_line(draw, (x, y), (x + w, y), fill=fill, width=width, dash=dash, gap=gap)
    draw_dashed_line(draw, (x + w, y), (x + w, y + h), fill=fill, width=width, dash=dash, gap=gap)
    draw_dashed_line(draw, (x + w, y + h), (x, y + h), fill=fill, width=width, dash=dash, gap=gap)
    draw_dashed_line(draw, (x, y + h), (x, y), fill=fill, width=width, dash=dash, gap=gap)


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    draw.text((xy[0] - width / 2, xy[1] - height / 2 - bbox[1]), text, font=font, fill=fill)


def marker_text(value: Any, fallback: int) -> str:
    raw = str(value or fallback)
    return CIRCLED_DIGITS.get(raw, raw)


def render_markup(base: Image.Image, page: dict[str, Any]) -> Image.Image:
    image = base.convert("RGBA")
    draw = ImageDraw.Draw(image)
    width, height = image.size
    markup = page.get("markup") or {}

    for stroke in markup.get("pen_strokes") or []:
        points = [
            (clamp01(point.get("x")) * width, clamp01(point.get("y")) * height)
            for point in stroke.get("points") or []
        ]
        if len(points) < 2:
            continue
        draw.line(
            points,
            fill=hex_to_rgba(stroke.get("color")),
            width=line_width(stroke.get("width"), width),
        )

    for item in markup.get("rects") or []:
        x = clamp01(item.get("x")) * width
        y = clamp01(item.get("y")) * height
        w = clamp01(item.get("w")) * width
        h = clamp01(item.get("h")) * height
        draw_dashed_rect(
            draw,
            (x, y, w, h),
            fill=hex_to_rgba(item.get("color")),
            width=line_width(item.get("width"), width),
        )

    marker_font = load_font(max(18, round(width * 0.018)), bold=True)
    radius = max(18, round(width * 0.018))
    for index, note in enumerate(markup.get("notes") or []):
        marker = marker_text(note.get("marker"), index + 1)
        x = clamp01(note.get("x")) * width
        y = clamp01(note.get("y")) * height
        fill = hex_to_rgba(DEFAULT_MARKUP_COLOR, alpha=245)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)
        draw_centered_text(draw, (x, y), marker, marker_font, (255, 255, 255, 255))

    return image


def write_note_text(path: Path, page: dict[str, Any]) -> None:
    markup = page.get("markup") or {}
    lines = [
        f"page_id: {page.get('page_id', '')}",
        f"requested_action: {page.get('requested_action', '')}",
        f"page_comment: {page.get('page_comment', '')}",
        "",
        "notes:",
    ]
    for note in markup.get("notes") or []:
        lines.append(
            f"- {note.get('marker', '')} ({note.get('x', '')}, {note.get('y', '')}): {note.get('comment', '')}"
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    payload = load_json(args.payload)
    image_map = load_image_map(args.image_map)
    args.out.mkdir(parents=True, exist_ok=True)

    pages = payload.get("pages") or []
    if not pages:
        raise SystemExit("No pages found in review payload.")

    for page in pages:
        source = find_source_image(page, args.images, image_map)
        with Image.open(source) as base:
            marked = render_markup(base, page)
        page_id = str(page.get("page_id") or page.get("page_code") or source.stem)
        output_path = args.out / f"{page_id}_marked.png"
        marked.convert("RGB").save(output_path)
        write_note_text(args.out / f"{page_id}_notes.txt", page)
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
