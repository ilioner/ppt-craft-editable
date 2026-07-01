#!/usr/bin/env python3
"""
detect_reserved_zones.py — 检测背景图里的"预留文字区"是否真的留白了

Phase C 的第 2 步：
  1) 优先直编 Phase A 定稿图
  2) 若直编后不干净，再回退到 imagegen：先出第一稿（完整稿）
  3) 再以第一稿为 edit target 擦掉可编辑文字、保留装饰
  4) 本脚本：检测擦字稿里的"预留区"是否真的被擦干净了
  5) 不合规 → 报出来，让 agent 决定重出 / 用 IOPaint 局部擦

判定方法：
  对每个声明的 reserved zone，取该矩形内的像素：
  - 计算颜色方差（std）—— 越接近纯色 std 越小
  - 计算边缘密度（Canny 边缘像素比例）—— 越少越好
  两个指标都达标 = 合规

用法:
  python3 scripts/detect_reserved_zones.py background.png zones.json [--report report.json]

zones.json schema:
{
  "ref_width": 1920,           # 可选；背景的逻辑参考宽（默认用图实际宽）
  "ref_height": 1080,          # 可选
  "zones": [
    {
      "id": "title",
      "x": 0.08, "y": 0.15,    # fraction，左上角
      "w": 0.50, "h": 0.20,
      "expected_color": "#f5f5f5",  # 可选；如果有，会额外检查"平均色是否接近"
      "tolerance": 25                # 可选；颜色容差，默认 25（每通道 0-255）
    }
  ]
}

阈值（可通过 --strict / --loose 调）：
  - std (默认): <= 12 才算合规（pure 背景 std 通常 < 5；噪点轻微的渐变 < 12）
  - edge_ratio (默认): <= 0.02（边缘像素比例 < 2%）
  - color_diff (有 expected_color 时): 每通道差 <= tolerance

退出码:
  0  所有 zone 合规
  1  至少一个 zone 不合规（详情看终端 / --report JSON）
  2  输入文件/参数有问题
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit("缺少依赖：pip3 install opencv-python numpy")


# ─────────────────────────────────────────────────────────
# 阈值预设
# ─────────────────────────────────────────────────────────

THRESH_PRESETS = {
    "default": {"std": 12.0, "edge_ratio": 0.02, "tolerance": 25},
    "strict":  {"std":  6.0, "edge_ratio": 0.008, "tolerance": 12},
    "loose":   {"std": 20.0, "edge_ratio": 0.05, "tolerance": 40},
}


# ─────────────────────────────────────────────────────────
# 工具
# ─────────────────────────────────────────────────────────

def hex_to_bgr(s: str) -> tuple[int, int, int]:
    s = s.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise ValueError(f"颜色格式不对: {s}")
    r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    return (b, g, r)  # OpenCV 用 BGR


def crop_zone(img: np.ndarray, zone: dict) -> np.ndarray:
    h, w = img.shape[:2]
    x = int(float(zone["x"]) * w)
    y = int(float(zone["y"]) * h)
    bw = int(float(zone["w"]) * w)
    bh = int(float(zone["h"]) * h)
    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))
    bw = max(1, min(bw, w - x))
    bh = max(1, min(bh, h - y))
    return img[y:y + bh, x:x + bw]


def measure(patch: np.ndarray) -> dict:
    """对一个矩形 patch 计算各项指标。"""
    # 颜色方差：取每个通道 std 的平均
    bgr_std = float(np.mean(patch.std(axis=(0, 1))))

    # 边缘密度：Canny
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edge_ratio = float(np.count_nonzero(edges)) / float(edges.size)

    # 平均色
    mean_b, mean_g, mean_r = patch.mean(axis=(0, 1)).tolist()

    return {
        "std": round(bgr_std, 3),
        "edge_ratio": round(edge_ratio, 4),
        "mean_bgr": [round(mean_b, 1), round(mean_g, 1), round(mean_r, 1)],
    }


def color_diff(measured_bgr: list[float], expected_hex: str) -> int:
    expected_bgr = hex_to_bgr(expected_hex)
    return int(max(abs(a - b) for a, b in zip(measured_bgr, expected_bgr)))


def evaluate_zone(zone: dict, patch: np.ndarray, thresh: dict) -> dict:
    m = measure(patch)
    reasons = []

    if m["std"] > thresh["std"]:
        reasons.append(
            f"颜色方差过高 std={m['std']} > {thresh['std']}（可能仍有文字/图案残留）"
        )
    if m["edge_ratio"] > thresh["edge_ratio"]:
        reasons.append(
            f"边缘密度过高 edge_ratio={m['edge_ratio']} > {thresh['edge_ratio']}"
            f"（仍能检出大量轮廓）"
        )

    expected_color = zone.get("expected_color")
    if expected_color:
        diff = color_diff(m["mean_bgr"], expected_color)
        tol = float(zone.get("tolerance", thresh["tolerance"]))
        m["color_diff_max"] = diff
        if diff > tol:
            reasons.append(
                f"平均色偏离 expected={expected_color}, diff_max={diff} > 容差 {tol}"
            )

    return {
        "id": zone.get("id", "?"),
        "ok": len(reasons) == 0,
        "metrics": m,
        "reasons": reasons,
    }


# ─────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("background", type=Path, help="待检测背景图（优先是直编结果；回退时是擦字稿）")
    ap.add_argument("zones", type=Path, help="zones.json")
    ap.add_argument("--report", type=Path, help="把详细结果写入 JSON")
    ap.add_argument("--strict", action="store_true", help="收紧阈值")
    ap.add_argument("--loose", action="store_true", help="放宽阈值")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    if not args.background.exists():
        sys.exit(f"背景图不存在: {args.background}")
    if not args.zones.exists():
        sys.exit(f"zones.json 不存在: {args.zones}")

    if args.strict and args.loose:
        sys.exit("--strict 和 --loose 二选一")
    if args.strict:
        thresh = THRESH_PRESETS["strict"]
    elif args.loose:
        thresh = THRESH_PRESETS["loose"]
    else:
        thresh = THRESH_PRESETS["default"]

    img = cv2.imdecode(np.fromfile(str(args.background), dtype=np.uint8),
                       cv2.IMREAD_COLOR)
    if img is None:
        sys.exit(f"读不出图: {args.background}")

    spec = json.loads(args.zones.read_text(encoding="utf-8"))
    zones = spec.get("zones") or []
    if not zones:
        sys.exit("zones.json 里没有 zones 数组或为空")

    results = []
    for z in zones:
        patch = crop_zone(img, z)
        result = evaluate_zone(z, patch, thresh)
        results.append(result)

    n_total = len(results)
    n_bad = sum(1 for r in results if not r["ok"])
    overall_ok = n_bad == 0

    # 打印人类可读
    print(f"\n背景: {args.background}")
    print(f"阈值: std<={thresh['std']}  edge_ratio<={thresh['edge_ratio']}")
    print("─" * 60)
    for r in results:
        flag = "✅" if r["ok"] else "❌"
        print(f"{flag}  zone={r['id']}  metrics={r['metrics']}")
        for reason in r["reasons"]:
            print(f"     - {reason}")
    print("─" * 60)
    print(f"汇总: {n_total - n_bad}/{n_total} 合规")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(
                {
                    "background": str(args.background),
                    "thresholds": thresh,
                    "ok": overall_ok,
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"详细报告: {args.report}")

    sys.exit(0 if overall_ok else 1)


if __name__ == "__main__":
    main()
