#!/usr/bin/env python3
"""
doctor.py — ppt-craft-editable 环境自检

用户首次启动本 skill 时必须先跑这个脚本（SKILL.md 顶层规则）。

检查项分三档：
  ★ 必备：缺了直接阻塞 Phase A，必须修
  ◎ 推荐：缺了某些功能用不了（Stage 5.5 retouch、文字预览等）
  • 加分：有更好，没有也能跑

输出格式：
  - 每项前缀 ✅/⚠️/❌
  - 末尾汇总 N OK / M WARN / K FAIL
  - 有 FAIL → 退出码 1（阻塞）+ 打印修复命令
  - 只有 WARN/OK → 退出码 0（可继续）

不会自动安装任何东西——只报告状态、给修复命令。
"""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────
# 配色（终端 ANSI；不识别就是普通文字）
# ─────────────────────────────────────────────────────────

C_OK   = "\033[32m"
C_WARN = "\033[33m"
C_FAIL = "\033[31m"
C_DIM  = "\033[2m"
C_END  = "\033[0m"

USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

def c(text: str, color: str) -> str:
    return f"{color}{text}{C_END}" if USE_COLOR else text


# ─────────────────────────────────────────────────────────
# 检查结果累计
# ─────────────────────────────────────────────────────────

results: list[dict] = []

def add(level: str, label: str, detail: str = "", fix: str = "") -> None:
    """level: 'ok' | 'warn' | 'fail'"""
    results.append({"level": level, "label": label, "detail": detail, "fix": fix})
    icon = {"ok": "✅", "warn": "⚠️", "fail": "❌"}[level]
    color = {"ok": C_OK, "warn": C_WARN, "fail": C_FAIL}[level]
    print(f"{icon} {c(label, color)}")
    if detail:
        print(f"   {c(detail, C_DIM)}")


# ─────────────────────────────────────────────────────────
# 平台无关的检查
# ─────────────────────────────────────────────────────────

def check_python() -> None:
    v = sys.version_info
    label = f"Python ≥ 3.10"
    detail = f"当前: {v.major}.{v.minor}.{v.micro}  / {sys.executable}"
    if v >= (3, 10):
        add("ok", label, detail)
    else:
        add("fail", label, detail,
            "macOS: brew install python@3.11 && python3.11 -m pip install ...\n"
            "Win/Linux: 装 Python 3.10+，并用它的 python 重跑本 skill。")


def check_pip_pkg(pkg: str, import_name: str | None = None,
                  level_if_missing: str = "fail",
                  reason: str = "") -> bool:
    """检查一个 pip 包是否能 import。返回是否存在。"""
    name = import_name or pkg
    try:
        # 用 importlib 检查，比 try-import 安静（避免触发副作用）
        spec = importlib.util.find_spec(name)
        if spec is None:
            raise ImportError
        # 尝试拿到版本
        try:
            mod = importlib.import_module(name)
            ver = getattr(mod, "__version__", "?")
        except Exception:
            ver = "?"
        add("ok", f"Python 包: {pkg}", f"版本: {ver}")
        return True
    except Exception:
        fix = f"pip3 install {pkg}"
        add(level_if_missing, f"Python 包: {pkg}",
            f"未安装{('（' + reason + '）') if reason else ''}",
            fix)
        return False


def check_imagegen_hint() -> None:
    """
    imagegen 不是一个 Python 包，是 agent harness 提供的工具。
    无法从 Python 直接探测，只能给 agent 一个 hint：
      用户首次跑 skill 时，agent 必须在 Stage 1 前测试出一张极小尺寸的图，
      确认 imagegen 通道可用。

    本检查只写 hint，不影响退出码。
    """
    print()
    print(c("ℹ️  imagegen 通道（agent 侧）", C_DIM))
    print(c("   doctor 无法直接探测 imagegen。请 agent 在进入 Stage 2 之前", C_DIM))
    print(c("   先生成一张极小测试图验证通道；失败则报「出图通道不可用」", C_DIM))
    print(c("   阻塞 Stage 2，不允许降级到文字 mockup。", C_DIM))


def check_fonts() -> None:
    """检查系统是否至少有一个 CJK 安全字体。"""
    candidates = [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        # Windows
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/arial.ttf",
        # Linux
        "/usr/share/fonts/opentype/source-han-sans/SourceHanSansSC-Regular.otf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    found = [p for p in candidates if Path(p).exists()]
    if found:
        add("ok", "系统字体（SAFE_FONT_SET 至少一个）",
            f"找到 {len(found)} 个: {Path(found[0]).name} 等")
    else:
        add("warn", "系统字体（SAFE_FONT_SET）",
            "没找到 PingFang / Microsoft YaHei / Hiragino / Arial 等任一系统字体",
            "macOS/Win 默认应该都有；Linux 装：\n"
            "  Debian/Ubuntu: sudo apt install fonts-noto-cjk\n"
            "  Fedora:        sudo dnf install google-noto-sans-cjk-fonts")


def check_disk_space(min_gb: float = 1.0, recommend_gb: float = 4.0) -> None:
    """检查临时目录所在分区剩余空间。"""
    home = Path.home()
    free_gb = shutil.disk_usage(home).free / (1024 ** 3)
    label = f"磁盘剩余空间（{home} 分区）"
    detail = f"剩余: {free_gb:.1f} GB"
    if free_gb < min_gb:
        add("fail", label, detail,
            f"清出至少 {min_gb} GB，否则连基础任务都跑不下。")
    elif free_gb < recommend_gb:
        add("warn", label, detail + f"（建议 ≥ {recommend_gb} GB，用于 IOPaint 安装）",
            "如果不打算用 Stage 5.5 IOPaint 修瑕疵，可以忽略。")
    else:
        add("ok", label, detail)


def check_network(host: str, label: str) -> None:
    """快速 TCP 连通性测试。"""
    try:
        socket.create_connection((host, 443), timeout=3).close()
        add("ok", f"网络: {label}", f"{host}:443 可达")
    except Exception as e:
        add("warn", f"网络: {label}",
            f"{host}:443 不通 ({type(e).__name__})",
            "如果不打算装 IOPaint / 不在 Phase A 走 imagegen 中转，可以忽略。")


def check_optional_cmd(cmd: str, label: str, reason: str) -> None:
    """检查可选的命令行工具。"""
    p = shutil.which(cmd)
    if p:
        add("ok", f"命令行工具: {cmd}", f"路径: {p}")
    else:
        add("warn", f"命令行工具: {cmd}",
            f"未安装{('（' + reason + '）') if reason else ''}",
            {
                "magick":     "macOS: brew install imagemagick\nWin: https://imagemagick.org/script/download.php",
                "convert":    "（属于 ImageMagick）见 magick 项。",
            }.get(cmd, ""))


def check_iopaint_state() -> None:
    """检查 IOPaint 是否已装（不强制）。"""
    marker = Path.home() / ".cache" / "ppt-craft-editable" / ".lama-installed"
    if marker.exists():
        try:
            info = json.loads(marker.read_text(encoding="utf-8"))
            ipt = Path(info.get("iopaint", ""))
            if ipt.exists():
                add("ok", "IOPaint (LaMa)", f"已就绪: {info.get('installed_at', '?')}")
                return
        except Exception:
            pass
    add("warn", "IOPaint (LaMa)",
        "未安装（用户首次需要时会自动装，~5-10 分钟、~3GB）",
        "现在不用装；只在 Stage 5.5 retouch 或 Phase C 局部擦字时才用到。")


def check_skill_self() -> None:
    """检查 skill 自身的关键文件是否齐全（防止用户拷漏了）。"""
    here = Path(__file__).resolve().parent.parent
    must = [
        "SKILL.md",
        "scripts/json_to_pptx.py",
        "scripts/validate_deck_json.py",
        "scripts/inject_shell_images.py",
        "scripts/inject_editor_deck.py",
        "scripts/detect_reserved_zones.py",
        "scripts/remove_corner_watermark.py",
        "scripts/setup_iopaint.py",
        "scripts/launch_iopaint.py",
        "scripts/render_review_markup.py",
        "assets/preview_shell/index.html",
        "assets/candidate_picker_shell/index.html",
        "assets/review_shell/index.html",
        "assets/editor_shell/index.html",
        "references/phaseA/workflow.md",
        "references/phaseC/workflow.md",
        "templates/design_spec_reference.md",
    ]
    missing = [m for m in must if not (here / m).exists()]
    if missing:
        add("fail", "Skill 自身完整性",
            f"缺失 {len(missing)} 个关键文件：{', '.join(missing[:3])}...",
            "重新复制整个 ppt-craft-editable/ 目录到 skills 目录。")
    else:
        add("ok", "Skill 自身完整性", f"{len(must)} 个关键文件齐全")


def check_platform_info() -> None:
    """打印平台信息（不打分）。"""
    print()
    print(c(f"━━━ 平台信息 ━━━", C_DIM))
    print(c(f"  OS:       {platform.system()} {platform.release()}", C_DIM))
    print(c(f"  机器:     {platform.machine()}", C_DIM))
    print(c(f"  Python:   {sys.version.split()[0]}", C_DIM))
    print(c(f"  CWD:      {Path.cwd()}", C_DIM))
    skill_root = Path(__file__).resolve().parent.parent
    print(c(f"  Skill 根: {skill_root}", C_DIM))


# ─────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────

def main() -> int:
    print(c("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", C_DIM))
    print(c("  ppt-craft-editable — 启动自检", C_DIM))
    print(c("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", C_DIM))
    print()

    print(c("[必备项]", C_DIM))
    check_python()
    check_skill_self()
    check_pip_pkg("python-pptx", "pptx", level_if_missing="fail",
                  reason="Phase A 图片型 PPTX 合成 / Phase C json_to_pptx 都用它")
    check_pip_pkg("Pillow", "PIL", level_if_missing="fail",
                  reason="所有图像操作的基础")
    check_pip_pkg("numpy", "numpy", level_if_missing="fail",
                  reason="多个脚本用")
    check_pip_pkg("opencv-python", "cv2", level_if_missing="fail",
                  reason="remove_corner_watermark / detect_reserved_zones 用")

    print()
    print(c("[推荐项]", C_DIM))
    check_fonts()
    check_disk_space()
    check_optional_cmd("magick", "ImageMagick",
                       "Stage 5.5 retouch 在 IOPaint 装不上时的兜底矩形遮罩")
    check_iopaint_state()

    print()
    print(c("[网络（可选）]", C_DIM))
    check_network("pypi.org", "PyPI")
    check_network("hf-mirror.com", "HuggingFace 镜像（IOPaint 用）")

    check_platform_info()
    check_imagegen_hint()

    # 汇总
    n_ok   = sum(1 for r in results if r["level"] == "ok")
    n_warn = sum(1 for r in results if r["level"] == "warn")
    n_fail = sum(1 for r in results if r["level"] == "fail")

    print()
    print(c("━━━ 汇总 ━━━", C_DIM))
    print(f"  ✅ OK:   {n_ok}")
    print(f"  ⚠️  WARN: {n_warn}")
    print(f"  ❌ FAIL: {n_fail}")
    print()

    if n_fail > 0:
        print(c("❌ 阻塞：缺必备项，无法进入 Phase A。请按下面修复后重跑 doctor：", C_FAIL))
        print()
        for r in results:
            if r["level"] == "fail" and r["fix"]:
                print(c(f"  ▸ {r['label']}", C_FAIL))
                for line in r["fix"].splitlines():
                    print(f"    {line}")
                print()
        return 1

    if n_warn > 0:
        print(c("⚠️  有可选项缺失，部分功能可能受限。Phase A 主流程仍可继续。", C_WARN))
        print(c("   想现在修也可以，对照上面 fix 命令执行。", C_DIM))
    else:
        print(c("✅ 全部就绪，可以进入 Phase A 主流程。", C_OK))

    return 0


if __name__ == "__main__":
    sys.exit(main())
