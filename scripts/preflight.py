#!/usr/bin/env python3
"""
preflight.py — agent 自动调用的前置检查 + 自动修复

用户首次触发本 skill 时，agent 调本脚本作为 Stage 0。本脚本：
  1. 检查 Python 版本（不够则停）
  2. 检查 4 个必备 pip 包，缺的自动装（含 --user fallback）
  3. 装完跑完整 doctor.py 看其它状态（字体 / 磁盘 / 网络 / IOPaint）
  4. doctor 退码 0 → preflight 退码 0：可进 Stage 1
     doctor 退码 1 → preflight 退码 1：还有不可自动修的项目，让用户处理

跟 doctor.py 的关系：
  - doctor.py = 只检查、只报告，不动用户环境（安全审计角色）
  - preflight.py = 包一层 + 自动装可装的，agent 默认调它

不会自动装的项目（明确拒绝越权）：
  - Python 版本升级
  - 系统字体安装（需要 sudo / 跨平台不一致）
  - IOPaint（不该在 preflight 里装，那是 ~3GB / 5-10 分钟的事，按需触发）
  - 磁盘清理

退出码：
  0  环境就绪，agent 可以进入 Phase A Stage 1
  1  有不可自动修的项目，agent 必须停下让用户处理
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

# 必备 pip 包：pip 包名 → import 名
AUTO_INSTALLABLE: dict[str, str] = {
    "python-pptx":   "pptx",
    "Pillow":        "PIL",
    "numpy":         "numpy",
    "opencv-python": "cv2",
}

# 磁盘空间阈值（GB）
DISK_HARD_MIN = 0.5    # 低于此值直接停（连 pip 都装不下）
DISK_SOFT_MIN = 2.0    # 低于此值警告（4 个 pip 包 + 临时下载需要约 1GB+）
DISK_RECOMMEND = 4.0   # 推荐空间（含 Stage 5.5 IOPaint 的 ~3GB）


# ─────────────────────────────────────────────────────────
# 工具
# ─────────────────────────────────────────────────────────

def is_pkg_installed(import_name: str) -> bool:
    try:
        return importlib.util.find_spec(import_name) is not None
    except Exception:
        return False


def try_install(pkg_name: str) -> tuple[bool, str]:
    """
    尝试 pip install。返回 (是否成功, 失败原因)。
    顺序：
      1. python -m pip install --upgrade <pkg>
      2. 失败：python -m pip install --user --upgrade <pkg>
      3. 再失败：不再尝试 --break-system-packages（会污染系统），
         返回失败让用户决定怎么办
    """
    base_cmd = [sys.executable, "-m", "pip", "install", "--upgrade",
                "--disable-pip-version-check", "--quiet"]

    # 试常规
    try:
        proc = subprocess.run(
            base_cmd + [pkg_name],
            timeout=600,   # 单包最多 10 分钟（OpenCV 在国内网络下可能 5+ 分钟）
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return False, "pip install 超时（>10 分钟，网络可能极慢，建议手动装）"
    except Exception as e:
        return False, f"pip 调用异常：{type(e).__name__}: {e}"

    if proc.returncode == 0:
        return True, ""

    # 看是不是 PEP 668 / 权限问题，决定要不要尝试 --user
    err_text = (proc.stderr or "") + (proc.stdout or "")
    looks_like_externally_managed = (
        "externally-managed-environment" in err_text
        or "PEP 668" in err_text
    )
    looks_like_permission = (
        "Permission denied" in err_text
        or "could not be installed" in err_text.lower()
    )

    if not (looks_like_externally_managed or looks_like_permission):
        # 别的错误，--user 也不会救
        first_line = err_text.strip().splitlines()[0] if err_text.strip() else ""
        return False, f"pip install 失败：{first_line[:200] or '(无错误输出)'}"

    # fallback：--user
    try:
        proc2 = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user", "--upgrade",
             "--disable-pip-version-check", "--quiet", pkg_name],
            timeout=600,
            capture_output=True,
            text=True,
        )
    except Exception as e:
        return False, f"--user fallback 调用异常：{type(e).__name__}: {e}"

    if proc2.returncode == 0:
        return True, ""

    err2 = (proc2.stderr or "") + (proc2.stdout or "")
    first_line = err2.strip().splitlines()[0] if err2.strip() else ""
    return False, f"--user 也失败：{first_line[:200] or '(无错误输出)'}"


def print_banner(title: str) -> None:
    bar = "═" * 60
    print(bar, flush=True)
    print(f"  {title}", flush=True)
    print(bar, flush=True)


def print_section(title: str) -> None:
    print(flush=True)
    print(f"━━━ {title} ━━━", flush=True)


# ─────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────

def main() -> int:
    print_banner("ppt-craft-editable — Stage 0 自检 + 自动修复")
    print()

    # ─── 第 1 关：Python 版本 ───
    v = sys.version_info
    if v < (3, 10):
        print(f"❌ Python {v.major}.{v.minor} 版本太低，需要 3.10+")
        print()
        print("这一项无法自动修复——动用户的 Python 太危险。请：")
        print("  macOS: brew install python@3.11")
        print("  Windows: 从 https://www.python.org/downloads/ 装 3.11+")
        print("  Linux: sudo apt install python3.11  或对应发行版的命令")
        print()
        print("装完后用新的 python 重新触发本 skill 即可。")
        return 1
    print(f"✅ Python {v.major}.{v.minor}.{v.micro}（位置: {sys.executable}）", flush=True)

    # ─── 第 1.5 关：磁盘空间（在装包前先查，省得装到一半失败）───
    home = Path.home()
    free_gb = shutil.disk_usage(home).free / (1024 ** 3)
    print(flush=True)
    if free_gb < DISK_HARD_MIN:
        print(f"❌ 磁盘空间严重不足：{home} 所在分区只剩 {free_gb:.2f} GB", flush=True)
        print(flush=True)
        print(f"   连 pip 装包（约需 500MB 临时空间）都不够，先停下让用户清理。", flush=True)
        print(flush=True)
        print(f"   清理建议（按腾出空间多少排序）：", flush=True)
        print(f"     · 清空「下载」目录、回收站", flush=True)
        print(f"     · 清理 ~/.cache/ 和 ~/Library/Caches/（macOS）", flush=True)
        print(f"     · 清理已不用的虚拟机、Docker 镜像", flush=True)
        print(f"     · macOS: 「Apple 菜单 → 关于本机 → 储存空间 → 管理」", flush=True)
        print(flush=True)
        print(f"   至少清出 {DISK_RECOMMEND:.0f} GB 后再重跑本 skill。", flush=True)
        return 1
    elif free_gb < DISK_SOFT_MIN:
        print(f"⚠️  磁盘空间不足：{home} 所在分区只剩 {free_gb:.2f} GB", flush=True)
        print(flush=True)
        print(f"   够装 4 个 pip 包，但很紧张。建议至少 {DISK_SOFT_MIN:.0f} GB；", flush=True)
        print(f"   如果之后想用 Stage 5.5 IOPaint 修瑕疵，还会再要 ~3GB（推荐 {DISK_RECOMMEND:.0f} GB+）。", flush=True)
        print(flush=True)
        print(f"   会继续装包，但生成大量图片时可能写盘失败——agent 看到", flush=True)
        print(f"   「No space left on device」这类错误时，请先告诉用户清理磁盘。", flush=True)
        print(flush=True)
    elif free_gb < DISK_RECOMMEND:
        print(f"✅ 磁盘空间够基本流程：{home} 剩余 {free_gb:.2f} GB", flush=True)
        print(f"   （Stage 5.5 IOPaint 还需要 ~3GB，建议提前清出更多空间）", flush=True)
    else:
        print(f"✅ 磁盘空间充足：{home} 剩余 {free_gb:.1f} GB", flush=True)

    # ─── 第 2 关：必备 pip 包 ───
    print_section("检查必备 Python 包")
    missing: list[str] = []
    for pkg, mod in AUTO_INSTALLABLE.items():
        if is_pkg_installed(mod):
            print(f"  ✅ {pkg}", flush=True)
        else:
            missing.append(pkg)
            print(f"  ⚠️  {pkg}（未安装，将自动装）", flush=True)

    if missing:
        print_section(f"正在自动安装 {len(missing)} 个缺失包")
        print(f"  用户可见效果：", flush=True)
        print(f"    - 首次安装可能需要 2 ~ 5 分钟（OpenCV 单独就 ~100MB）", flush=True)
        print(f"    - 期间终端看起来在卡——这是正常的，请耐心等", flush=True)
        print(f"    - 国内网络慢时可能更久；如果 5 分钟还没动静，按 Ctrl+C 中断", flush=True)
        print(f"      然后参考下面手动安装方案", flush=True)
        print(flush=True)
        failed: list[tuple[str, str]] = []
        for pkg in missing:
            print(f"  → 安装 {pkg} ...（请等待，不要中断）", flush=True)
            ok, reason = try_install(pkg)
            if ok:
                print(f"    ✅ {pkg} 安装成功", flush=True)
            else:
                print(f"    ❌ {pkg} 安装失败：{reason}", flush=True)
                failed.append((pkg, reason))

        if failed:
            print()
            print("══════════════════════════════════════════════════════════")
            print(f"  ❌ {len(failed)} 个包自动安装失败")
            print("══════════════════════════════════════════════════════════")
            print()
            for pkg, reason in failed:
                print(f"  · {pkg}：{reason}")
            print()
            print("请用户手动安装，然后重跑本 skill。推荐做法（任选一种）：")
            print()
            print("  【方案 A：常规手动装】")
            print(f"    python3 -m pip install --user {' '.join(p for p, _ in failed)}")
            print()
            print("  【方案 B：用虚拟环境（最干净，推荐）】")
            print("    python3 -m venv ~/.pife-venv")
            print(f"    ~/.pife-venv/bin/pip install {' '.join(p for p, _ in failed)}")
            print("    之后用 ~/.pife-venv/bin/python 来跑 skill（让 agent 用这个 Python）")
            print()
            print("  【方案 C：系统是 macOS Sonoma+ / Ubuntu 24+，强制装到系统 Python】")
            print(f"    python3 -m pip install --break-system-packages {' '.join(p for p, _ in failed)}")
            print("    （不推荐，但实在没别的办法时可用）")
            return 1

        # 装完验证一下确实可以 import
        still_missing = [p for p in missing
                        if not is_pkg_installed(AUTO_INSTALLABLE[p])]
        if still_missing:
            print()
            print("⚠️  装完后仍 import 不到：" + ", ".join(still_missing))
            print("   常见原因：pip 装到了一个 Python，但当前用的是另一个 Python")
            print(f"   当前 Python: {sys.executable}")
            print("   建议：让 agent 用刚才 pip 装到的 Python 重跑")
            return 1

        print()
        print(f"  ✅ {len(missing)} 个包全部安装就位")

    # ─── 第 3 关：跑完整 doctor，看其它项目状态 ───
    print_section("运行完整 doctor 检查")
    print()
    doctor_path = SCRIPT_DIR / "doctor.py"
    if not doctor_path.exists():
        print(f"❌ 找不到 doctor.py（{doctor_path}）；skill 可能装错了")
        return 1

    # 强制无颜色（避免子进程 ANSI 混乱）
    env = os.environ.copy()
    env["NO_COLOR"] = "1"
    try:
        doctor_proc = subprocess.run(
            [sys.executable, str(doctor_path)],
            env=env,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        print("❌ doctor 跑了 60 秒还没退出（网络太慢？）")
        return 1
    except Exception as e:
        print(f"❌ doctor 调用异常：{type(e).__name__}: {e}")
        return 1

    print()
    print_banner(
        "✅ 环境就绪，可以进入 Phase A Stage 1"
        if doctor_proc.returncode == 0
        else "❌ 自检仍有阻塞项（详见上面 doctor 输出）"
    )
    if doctor_proc.returncode != 0:
        print()
        print("有些项目 preflight 无法自动修（比如系统字体、imagegen 通道、")
        print("磁盘空间）。请按 doctor 给的修复命令处理后，让 agent 重跑：")
        print()
        print("  python3 scripts/preflight.py")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
