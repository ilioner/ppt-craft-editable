#!/usr/bin/env python3
"""
remove_corner_watermark.py — 去除图像固定角落（默认右下角）的文字水印。

适用场景：
  - 自己拥有版权 / 已付费 / AI 工具强行叠加的水印（例如 Qoder 的 "Qoder AI生成"）。
  - 水印位置固定在图像某个角落，是后期叠加的图层。
  - 不适用于授权不明的第三方图库样图。

工作原理：
  在指定区域生成 mask，调用 cv2.inpaint（TELEA / NS 算法）按周围像素恢复。
  对纯色 / 渐变 / 简单纹理背景效果极好；对密集复杂细节区域可能留下轻微痕迹。

用法：

  # 单张图
  python3 remove_corner_watermark.py input.png -o output.png

  # 批量（目录里所有 png/jpg）
  python3 remove_corner_watermark.py /path/to/dir --batch -o /path/to/out

  # 自定义水印区域（像素 / 百分比都行）
  python3 remove_corner_watermark.py input.png -o output.png \
      --corner br --width-pct 22 --height-pct 5 --margin-pct 2

  # 调试：先看一下框在哪里再决定要不要真的擦
  python3 remove_corner_watermark.py input.png --preview-only -o preview.png

参数详解见 -h。
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit("需要安装依赖：pip3 install opencv-python numpy")


CORNERS = {"br": "bottom-right", "bl": "bottom-left",
           "tr": "top-right",    "tl": "top-left"}


def compute_box(img_h: int, img_w: int, args) -> tuple[int, int, int, int]:
    """根据用户参数算出水印区域 (x, y, w, h)，全部像素整数。"""
    # 宽 / 高 / margin：像素优先；像素没给就用百分比
    w = args.width  if args.width  is not None else int(img_w * args.width_pct  / 100)
    h = args.height if args.height is not None else int(img_h * args.height_pct / 100)
    mx = args.margin_x if args.margin_x is not None else int(img_w * args.margin_pct / 100)
    my = args.margin_y if args.margin_y is not None else int(img_h * args.margin_pct / 100)

    corner = args.corner
    if corner == "br":
        x = img_w - w - mx
        y = img_h - h - my
    elif corner == "bl":
        x = mx
        y = img_h - h - my
    elif corner == "tr":
        x = img_w - w - mx
        y = my
    elif corner == "tl":
        x = mx
        y = my
    else:
        raise ValueError(f"未知 corner: {corner}")

    # 防越界
    x = max(0, min(x, img_w - 1))
    y = max(0, min(y, img_h - 1))
    w = min(w, img_w - x)
    h = min(h, img_h - y)
    return x, y, w, h


def process_one(in_path: Path, out_path: Path, args) -> bool:
    img = cv2.imdecode(np.fromfile(str(in_path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"[skip] 读不出来: {in_path}", file=sys.stderr)
        return False

    # 处理 alpha 通道：inpaint 不支持 4 通道，先拆分再合回
    has_alpha = img.ndim == 3 and img.shape[2] == 4
    if has_alpha:
        bgr, alpha = img[:, :, :3].copy(), img[:, :, 3].copy()
    else:
        bgr = img if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    h, w = bgr.shape[:2]
    x, y, bw, bh = compute_box(h, w, args)

    if args.preview_only:
        # 只画框，不擦
        preview = bgr.copy()
        cv2.rectangle(preview, (x, y), (x + bw, y + bh), (0, 0, 255), 3)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imencode(out_path.suffix, preview)[1].tofile(str(out_path))
        print(f"[preview] 框: x={x} y={y} w={bw} h={bh} → {out_path}")
        return True

    # 真擦：生成 mask
    mask = np.zeros((h, w), dtype=np.uint8)
    # 给一点 padding 让 inpaint 有更多上下文（防止边缘留痕）
    pad = args.mask_pad
    cv2.rectangle(mask,
                  (max(0, x - pad), max(0, y - pad)),
                  (min(w, x + bw + pad), min(h, y + bh + pad)),
                  255, thickness=-1)

    algo = cv2.INPAINT_TELEA if args.algo == "telea" else cv2.INPAINT_NS
    out_bgr = cv2.inpaint(bgr, mask, args.radius, algo)

    if has_alpha:
        # alpha 通道也按相同 mask 抹平（水印的半透明描边也擦掉）
        # 用周围 alpha 的中位数填回，最简单稳妥
        surrounding = alpha[max(0, y - pad - 5):min(h, y + bh + pad + 5),
                            max(0, x - pad - 5):min(w, x + bw + pad + 5)]
        fill_val = int(np.median(surrounding)) if surrounding.size else 255
        alpha_out = alpha.copy()
        alpha_out[mask > 0] = fill_val
        result = np.dstack([out_bgr, alpha_out])
    else:
        result = out_bgr

    out_path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(out_path.suffix, result)
    if not ok:
        print(f"[fail] 编码失败: {out_path}", file=sys.stderr)
        return False
    buf.tofile(str(out_path))
    print(f"[ok] {in_path.name} → {out_path}")
    return True


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("input", type=Path, help="单张图片，或 --batch 模式下的目录")
    ap.add_argument("-o", "--out", required=True, type=Path,
                    help="输出文件（单图模式）或目录（批量模式）")
    ap.add_argument("--batch", action="store_true",
                    help="把 input 当目录处理；递归找 .png/.jpg/.jpeg/.webp")

    g = ap.add_argument_group("水印区域")
    g.add_argument("--corner", choices=list(CORNERS.keys()), default="br",
                   help="水印所在角，默认 br=右下角")
    g.add_argument("--width-pct",  type=float, default=22.0,
                   help="水印宽度占整图宽度的百分比，默认 22")
    g.add_argument("--height-pct", type=float, default=5.0,
                   help="水印高度占整图高度的百分比，默认 5")
    g.add_argument("--margin-pct", type=float, default=1.5,
                   help="水印离图像边缘的距离百分比，默认 1.5")
    g.add_argument("--width",      type=int, help="水印宽度（像素，覆盖 width-pct）")
    g.add_argument("--height",     type=int, help="水印高度（像素，覆盖 height-pct）")
    g.add_argument("--margin-x",   type=int, help="水印离左/右边距（像素）")
    g.add_argument("--margin-y",   type=int, help="水印离上/下边距（像素）")

    g2 = ap.add_argument_group("inpaint 参数")
    g2.add_argument("--algo", choices=["telea", "ns"], default="telea",
                    help="算法：telea=快速、ns=Navier-Stokes 更平滑；默认 telea")
    g2.add_argument("--radius", type=int, default=8,
                    help="inpaint 半径，越大越平滑但越慢，默认 8")
    g2.add_argument("--mask-pad", type=int, default=4,
                    help="mask 向外扩张的像素，确保擦干净边缘抗锯齿，默认 4")

    ap.add_argument("--preview-only", action="store_true",
                    help="只画框预览，不真的擦；用来调参数")

    return ap.parse_args()


def main() -> None:
    args = parse_args()

    if args.batch:
        if not args.input.is_dir():
            sys.exit(f"--batch 模式下 input 必须是目录: {args.input}")
        out_dir = args.out
        out_dir.mkdir(parents=True, exist_ok=True)
        exts = {".png", ".jpg", ".jpeg", ".webp"}
        files = [p for p in args.input.rglob("*") if p.suffix.lower() in exts]
        if not files:
            sys.exit(f"目录里没有图: {args.input}")
        ok_count = 0
        for f in files:
            rel = f.relative_to(args.input)
            out_path = out_dir / rel
            if process_one(f, out_path, args):
                ok_count += 1
        print(f"\n完成：{ok_count}/{len(files)} 张")
    else:
        if not args.input.is_file():
            sys.exit(f"input 不是文件（要批量请加 --batch）: {args.input}")
        process_one(args.input, args.out, args)


if __name__ == "__main__":
    main()
