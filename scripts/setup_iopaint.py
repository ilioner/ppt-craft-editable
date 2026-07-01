#!/usr/bin/env python3
"""
setup_iopaint.py — 首次安装 + 预热 IOPaint (LaMa) 的幂等脚本

用途：
  Phase A 的 Stage 5.5 retouch 需要本地 IOPaint 做手工 inpaint 去水印 / 去瑕疵。
  本脚本一次性完成：
    1) 创建专属虚拟环境（不污染系统 Python）
    2) 装 iopaint + 依赖
    3) 预下载 LaMa 模型（200MB），避免用户首次启动时再卡几分钟
    4) 写一个 .marker 标记文件，下次跳过

幂等：
  - 已装且模型已下 → 立即返回
  - 标记文件存在但 venv 损坏 → 自动重建
  - --reinstall：强制重装

国内网络：
  默认设置 HF_ENDPOINT=https://hf-mirror.com，避免 HuggingFace 拉不到。
  用 --no-mirror 关闭。

失败兜底：
  装失败不影响 Phase A 已产出图，错误日志写到标记目录的 setup.log，
  并打印明确的下一步操作（手动重试 / 用 ImageMagick 简单遮罩兜底）。

用法：
  python3 scripts/setup_iopaint.py                  # 首次：装 + 预热；二次：直接退出
  python3 scripts/setup_iopaint.py --reinstall      # 强制重装
  python3 scripts/setup_iopaint.py --no-mirror      # 不用 HF 镜像
  python3 scripts/setup_iopaint.py --check-only     # 只检查状态，不装

退出码：
  0  已就绪 / 装好
  1  装失败（看 setup.log 与终端提示）
  2  Python / 网络 / 磁盘等环境前置不足
"""

from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import venv
from pathlib import Path

# ─────────────────────────────────────────────────────────
# 常量与路径
# ─────────────────────────────────────────────────────────

CACHE_DIR = Path.home() / ".cache" / "ppt-craft-editable"
VENV_DIR = CACHE_DIR / "venv"
MARKER = CACHE_DIR / ".lama-installed"
LOG_FILE = CACHE_DIR / "setup.log"
MIN_PY = (3, 10)
MIN_FREE_GB = 4  # PyTorch(~2.5G) + LaMa(~200M) + 缓冲

HF_MIRROR = "https://hf-mirror.com"


# ─────────────────────────────────────────────────────────
# 日志
# ─────────────────────────────────────────────────────────

def log(msg: str, *, also_print: bool = True) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    if also_print:
        print(msg, flush=True)


def fatal(msg: str, code: int = 1) -> None:
    log(f"FATAL: {msg}")
    print("\n— 终止 —", file=sys.stderr)
    print(f"日志: {LOG_FILE}", file=sys.stderr)
    sys.exit(code)


# ─────────────────────────────────────────────────────────
# 环境检查
# ─────────────────────────────────────────────────────────

def check_python() -> None:
    if sys.version_info < MIN_PY:
        fatal(
            f"需要 Python {MIN_PY[0]}.{MIN_PY[1]}+，当前 "
            f"{sys.version_info.major}.{sys.version_info.minor}。\n"
            f"建议：brew install python@3.11 后用 python3.11 重跑本脚本。",
            code=2,
        )


def check_disk() -> None:
    """检查 CACHE_DIR 所在分区剩余空间。"""
    parent = CACHE_DIR.parent
    parent.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(parent).free
    free_gb = free_bytes / (1024 ** 3)
    if free_gb < MIN_FREE_GB:
        fatal(
            f"磁盘剩余 {free_gb:.1f} GB，至少需要 {MIN_FREE_GB} GB"
            f"（PyTorch ~2.5G + LaMa ~200M + 缓冲）。\n"
            f"清理一下 {parent} 所在分区再重试。",
            code=2,
        )


def check_network() -> bool:
    """简单 ping 一下 pypi / hf-mirror。失败不致命，只警告。"""
    targets = [("pypi.org", 443), ("hf-mirror.com", 443)]
    import socket
    for host, port in targets:
        try:
            socket.create_connection((host, port), timeout=3).close()
        except Exception as e:
            log(f"WARN: 网络探测 {host}:{port} 失败 ({e})；安装中可能会很慢或失败。",
                also_print=True)
            return False
    return True


# ─────────────────────────────────────────────────────────
# venv
# ─────────────────────────────────────────────────────────

def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def venv_iopaint() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "iopaint.exe"
    return VENV_DIR / "bin" / "iopaint"


def venv_is_healthy() -> bool:
    py = venv_python()
    if not py.exists():
        return False
    try:
        out = subprocess.check_output(
            [str(py), "-c", "import sys; print(sys.version_info[:2])"],
            stderr=subprocess.STDOUT, text=True, timeout=10,
        )
        return "(" in out
    except Exception:
        return False


def create_venv() -> None:
    log(f"→ 创建虚拟环境: {VENV_DIR}")
    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR)
    builder = venv.EnvBuilder(with_pip=True, clear=True, upgrade_deps=True)
    builder.create(str(VENV_DIR))
    # 升级 pip / wheel，避免装 torch 时旧 pip 报错
    subprocess.check_call(
        [str(venv_python()), "-m", "pip", "install", "-U",
         "pip", "wheel", "setuptools"],
        env=_pip_env(),
    )


# ─────────────────────────────────────────────────────────
# 安装与预热
# ─────────────────────────────────────────────────────────

def _pip_env() -> dict:
    """pip 安装时的环境变量。"""
    env = os.environ.copy()
    # 避免 user-site 干扰
    env.pop("PYTHONUSERBASE", None)
    env.pop("PIP_USER", None)
    env["PIP_USER"] = "0"
    return env


def install_iopaint(use_mirror: bool) -> None:
    log("→ 安装 iopaint（含 torch CPU 版，约 800MB 下载、2.5GB 落盘，需要几分钟）")
    pip_args = [
        str(venv_python()), "-m", "pip", "install", "--upgrade",
        "iopaint",
    ]
    if use_mirror:
        # PyPI 国内镜像（清华），torch 走默认；torch 大文件走 pip 自身重试
        pip_args += ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]
    # 一次性安装；让 pip 自带的输出走到我们的终端
    code = subprocess.call(pip_args, env=_pip_env())
    if code != 0:
        fatal(
            "iopaint 安装失败。常见原因：\n"
            "  - 网络不稳定：重跑本脚本即可续传\n"
            "  - 磁盘不够：清理后重试\n"
            "  - torch 平台不兼容：手动 `pip install torch --index-url "
            "https://download.pytorch.org/whl/cpu` 后再跑\n"
            f"完整日志：{LOG_FILE}"
        )


def preheat_lama(use_mirror: bool) -> None:
    """让 IOPaint 把 LaMa 权重提前下到本地缓存。"""
    log("→ 预下载 LaMa 权重（约 200MB）")
    env = os.environ.copy()
    if use_mirror:
        env["HF_ENDPOINT"] = HF_MIRROR
    # iopaint 自己提供了 download 子命令
    cmd = [str(venv_iopaint()), "download", "--model", "lama"]
    code = subprocess.call(cmd, env=env)
    if code != 0:
        fatal(
            "LaMa 权重下载失败。常见原因：\n"
            "  - HuggingFace 被墙：脚本默认已用镜像 hf-mirror.com，仍失败可手动跑：\n"
            f"      HF_ENDPOINT={HF_MIRROR} {venv_iopaint()} download --model lama\n"
            "  - 磁盘不够：清理后重试\n"
            "  - 网络断了：重跑本脚本即可"
        )


def write_marker(use_mirror: bool) -> None:
    payload = {
        "version": 1,
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "venv": str(VENV_DIR),
        "python": str(venv_python()),
        "iopaint": str(venv_iopaint()),
        "model": "lama",
        "hf_mirror": use_mirror,
    }
    MARKER.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    log(f"→ 写入标记文件: {MARKER}")


def read_marker() -> dict | None:
    if not MARKER.exists():
        return None
    try:
        return json.loads(MARKER.read_text(encoding="utf-8"))
    except Exception:
        return None


# ─────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--reinstall", action="store_true",
                    help="强制重装：删 venv + 重新装 + 重新下模型")
    ap.add_argument("--no-mirror", action="store_true",
                    help="不使用 HuggingFace 镜像（默认用 hf-mirror.com）")
    ap.add_argument("--check-only", action="store_true",
                    help="只检查状态，不装；已就绪退 0，否则退 1")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    use_mirror = not args.no_mirror

    # 已就绪检查
    marker = read_marker()
    if marker and not args.reinstall:
        py = Path(marker.get("python", ""))
        ipt = Path(marker.get("iopaint", ""))
        if py.exists() and ipt.exists():
            print(f"[ok] IOPaint 已安装（{marker['installed_at']}）")
            print(f"     venv:    {marker['venv']}")
            print(f"     iopaint: {ipt}")
            print("     重装请加 --reinstall")
            sys.exit(0)
        else:
            log("WARN: 标记存在但 venv 已损坏，自动重装")

    if args.check_only:
        print("[miss] IOPaint 未安装。跑：python3 scripts/setup_iopaint.py")
        sys.exit(1)

    # 真正安装
    log("══════════════════════════════════════════════════════")
    log(f"  IOPaint 首次安装  ({time.strftime('%Y-%m-%d %H:%M:%S')})")
    log("══════════════════════════════════════════════════════")
    log(f"目标 venv: {VENV_DIR}")
    log(f"HF 镜像:  {'on (' + HF_MIRROR + ')' if use_mirror else 'off'}")
    log("预计耗时: 5–10 分钟（取决于网络）")
    log("预计磁盘: ~3 GB")
    log("")

    check_python()
    check_disk()
    check_network()

    create_venv()
    install_iopaint(use_mirror)
    preheat_lama(use_mirror)
    write_marker(use_mirror)

    print("")
    print("══════════════════════════════════════════════════════")
    print("  ✅ IOPaint 已就绪，可以用 launch_iopaint.py 启动了")
    print("══════════════════════════════════════════════════════")
    print(f"  venv:    {VENV_DIR}")
    print(f"  iopaint: {venv_iopaint()}")


if __name__ == "__main__":
    main()
