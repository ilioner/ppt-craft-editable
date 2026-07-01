#!/usr/bin/env python3
"""
launch_iopaint.py — Stage 5.5 retouch 用的 IOPaint 启动器

行为：
  1) 检查 IOPaint 是否已通过 setup_iopaint.py 装好
     - 未装 → 自动调用 setup_iopaint.py，提示用户等待安装
     - 已装 → 直接启动
  2) 启动 IOPaint（LaMa）的本地 web 服务
  3) 打开浏览器到 IOPaint 界面
  4) 把 Phase A 输出目录展示给用户，让用户在界面里手工涂抹去水印 / 去瑕疵

用法：
  python3 scripts/launch_iopaint.py [--slides-dir phaseA/slides] [--port 8080]

  # 自定义出口目录（保存修改后的文件位置由 IOPaint 自身控制；用户在界面右上角下载/保存）
  python3 scripts/launch_iopaint.py --slides-dir phaseA/slides

  # 强制重装
  python3 scripts/launch_iopaint.py --reinstall

  # 不自动打开浏览器
  python3 scripts/launch_iopaint.py --no-browser

退出码：
  0  正常退出（用户 Ctrl+C 关闭服务）
  1  启动失败
  2  IOPaint 未装且 setup 也失败
"""

from __future__ import annotations
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "ppt-craft-editable"
MARKER = CACHE_DIR / ".lama-installed"
SETUP_SCRIPT = Path(__file__).parent / "setup_iopaint.py"
HF_MIRROR = "https://hf-mirror.com"


def read_marker() -> dict | None:
    if not MARKER.exists():
        return None
    try:
        return json.loads(MARKER.read_text(encoding="utf-8"))
    except Exception:
        return None


def ensure_installed(reinstall: bool) -> dict:
    """确保 IOPaint 已装；未装就调 setup_iopaint.py。返回 marker dict。"""
    marker = read_marker()
    if marker and not reinstall:
        py = Path(marker.get("python", ""))
        ipt = Path(marker.get("iopaint", ""))
        if py.exists() and ipt.exists():
            return marker

    # 走安装
    print("══════════════════════════════════════════════════════════")
    print("  IOPaint 还未安装")
    print("══════════════════════════════════════════════════════════")
    print("  Stage 5.5 retouch 需要本地 IOPaint (LaMa) 做手工 inpaint。")
    print("  现在会自动安装：")
    print("    - 创建专属虚拟环境（不污染系统 Python）")
    print("    - 装 iopaint + 依赖（含 torch CPU，约 2.5GB 落盘）")
    print("    - 预下载 LaMa 模型（约 200MB）")
    print("    - 预计耗时 5–10 分钟（取决于网络）")
    print("")
    print("  默认开启 HuggingFace 镜像 (hf-mirror.com)，国内网络也能下。")
    print("  日志：~/.cache/ppt-craft-editable/setup.log")
    print("══════════════════════════════════════════════════════════")
    print("")

    setup_cmd = [sys.executable, str(SETUP_SCRIPT)]
    if reinstall:
        setup_cmd.append("--reinstall")
    code = subprocess.call(setup_cmd)
    if code != 0:
        print("")
        print("══════════════════════════════════════════════════════════")
        print("  ❌ IOPaint 安装失败。")
        print("══════════════════════════════════════════════════════════")
        print("  Phase A 已经产出的图不受影响，仍在 phaseA/slides/。")
        print("")
        print("  下一步选择：")
        print("    1) 重试安装：python3 scripts/setup_iopaint.py")
        print("    2) 跳过 retouch，直接用 Phase A 现有输出")
        print("    3) 用简单的角落水印批处理：")
        print("         python3 scripts/remove_corner_watermark.py "
              "phaseA/slides/ -o phaseA/slides_clean/ --batch")
        print("    4) 用 ImageMagick 手动遮罩兜底（如有该工具）：")
        print('         magick input.png -fill white -draw '
              '"rectangle X1,Y1 X2,Y2" output.png')
        print("══════════════════════════════════════════════════════════")
        sys.exit(2)

    # 重新读 marker
    marker = read_marker()
    if not marker:
        print("ERROR: 安装似乎完成，但 marker 文件没写出来。", file=sys.stderr)
        sys.exit(1)
    return marker


def port_in_use(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def find_free_port(start: int) -> int:
    p = start
    for _ in range(50):
        if not port_in_use(p):
            return p
        p += 1
    raise SystemExit(f"找不到空闲端口（从 {start} 起连试 50 个都被占）")


def launch(marker: dict, slides_dir: Path, port: int, open_browser: bool) -> int:
    iopaint = Path(marker["iopaint"])
    if not iopaint.exists():
        print(f"ERROR: iopaint 可执行文件不在 {iopaint}；请重装。",
              file=sys.stderr)
        return 1

    if port_in_use(port):
        new_port = find_free_port(port + 1)
        print(f"[hint] 端口 {port} 被占，改用 {new_port}")
        port = new_port

    url = f"http://127.0.0.1:{port}"

    # IOPaint 启动命令；CPU 模式（Apple Silicon 也走 CPU，避免 MPS 不稳）
    cmd = [
        str(iopaint), "start",
        "--model", "lama",
        "--device", "cpu",
        "--port", str(port),
        "--host", "127.0.0.1",
        "--input", str(slides_dir.resolve()),
    ]

    env = os.environ.copy()
    if marker.get("hf_mirror", True):
        env["HF_ENDPOINT"] = HF_MIRROR

    print("══════════════════════════════════════════════════════════")
    print("  Stage 5.5 — IOPaint Retouch 启动")
    print("══════════════════════════════════════════════════════════")
    print(f"  源目录: {slides_dir.resolve()}")
    print(f"  地址:   {url}")
    print("")
    print("  操作方式：")
    print("    1) 浏览器自动打开 IOPaint 界面")
    print("    2) 从左侧打开 phaseA/slides/ 中要修的图")
    print("    3) 用笔刷涂掉水印 / 瑕疵 → 点 'Run' → 一键 inpaint")
    print("    4) 满意后点右上角 'Save' 下载到本地，覆盖原图或另存")
    print("    5) 全部修完，回到这个终端按 Ctrl+C 关闭服务")
    print("══════════════════════════════════════════════════════════")
    print("")

    proc = subprocess.Popen(cmd, env=env)

    # 等几秒让服务起来
    if open_browser:
        for _ in range(40):
            if port_in_use(port):
                break
            time.sleep(0.25)
        try:
            webbrowser.open(url)
            print(f"[ok] 已尝试打开浏览器：{url}")
        except Exception as e:
            print(f"[warn] 自动打开浏览器失败：{e}；手动访问 {url}")

    try:
        return proc.wait()
    except KeyboardInterrupt:
        print("\n[exit] 收到 Ctrl+C，停止 IOPaint…")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        return 0


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--slides-dir", type=Path, default=Path("phaseA/slides"),
                    help="要编辑的图片所在目录（默认 phaseA/slides）")
    ap.add_argument("--port", type=int, default=8080,
                    help="本地服务端口，默认 8080；占用时自动+1")
    ap.add_argument("--no-browser", action="store_true",
                    help="不自动打开浏览器")
    ap.add_argument("--reinstall", action="store_true",
                    help="强制重新装 IOPaint")
    return ap.parse_args()


def main() -> None:
    args = parse_args()

    slides_dir = args.slides_dir.resolve()
    if not slides_dir.exists():
        print(f"ERROR: 源目录不存在: {slides_dir}", file=sys.stderr)
        print("  把 --slides-dir 指向你 Phase A 输出的图目录，例如：", file=sys.stderr)
        print("    python3 scripts/launch_iopaint.py --slides-dir phaseA/slides",
              file=sys.stderr)
        sys.exit(1)

    marker = ensure_installed(args.reinstall)
    code = launch(marker, slides_dir, args.port, not args.no_browser)
    sys.exit(code)


if __name__ == "__main__":
    main()
