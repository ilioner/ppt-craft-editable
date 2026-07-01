# Stage 5.5 — Retouch（图像级修瑕 / 去水印）

Phase A Stage 5 review 通过后，**默认就交付**。Stage 5.5 是**用户驱动的可选环节**，专门用来：

- 去掉出图工具叠加的水印（例如 Qoder 的 "Qoder AI生成"）
- 抹除某页角落的小瑕疵（多余字符、错位 logo、奇怪噪点）
- 局部 inpaint 一些细节不满意的区域

> Stage 5.5 **不替代** Phase A 的 review/retouch 流程。
> 内容 / 视觉的实质改动应当走 Stage 5 回到 image-first 重出；
> Stage 5.5 只解决"图整体没问题、就那一小块要擦掉"的微调。

---

## 三档工具，从轻到重

| 场景 | 工具 | 何时用 |
|---|---|---|
| **固定位置的角落水印**（位置都一样） | `scripts/remove_corner_watermark.py` | Qoder 这种工具水印；批量一次过 |
| **任意位置 / 复杂背景** | IOPaint (LaMa) | 单图手工涂抹；效果最好 |
| **简单几何遮罩**（ImageMagick fallback） | `magick -draw "rectangle ..."` | IOPaint 装不上时兜底，效果差但能用 |

---

## 工具 1：批量去角落水印（最省事）

适合："所有页右下角都印着同一行字"这种 case。Qoder 的水印就是典型。

```bash
# Step 1: 先预览框对了没
python3 scripts/remove_corner_watermark.py \
    phaseA/slides/01-cover.png \
    -o /tmp/preview.png \
    --preview-only
# 打开 /tmp/preview.png 看红框是不是刚好框住水印

# Step 2: 框对了就单图试一张
python3 scripts/remove_corner_watermark.py \
    phaseA/slides/01-cover.png \
    -o /tmp/clean.png

# Step 3: 满意就整批跑
python3 scripts/remove_corner_watermark.py \
    phaseA/slides/ \
    -o phaseA/slides_clean/ \
    --batch
```

框偏了调参数：
- `--width-pct 28`  框宽一点
- `--height-pct 3.5`  框矮一点
- `--margin-pct 3`  离边远一点
- `--corner bl`  改成左下角

对纯色 / 浅色背景效果几乎无痕；压在复杂图标上会留下轻微模糊。这种页用工具 2 手工补。

---

## 工具 2：IOPaint（LaMa，效果最强）

**首次使用会自动安装 IOPaint 和 LaMa 模型**（一次性，约 5–10 分钟、~3GB 磁盘）。之后秒启。

### 一键启动

```bash
# 直接启动；如果还没装会先自动装，装完继续
python3 scripts/launch_iopaint.py --slides-dir phaseA/slides
```

会自动：
1. 检查 IOPaint 是否已装；未装就调 `setup_iopaint.py` 装一次（用户等待）
2. 起本地服务 `http://127.0.0.1:8080`
3. 弹出浏览器到 IOPaint 界面
4. `--input phaseA/slides` 让界面直接看到你这次 Phase A 的所有图

### 界面操作流程

1. 从左侧文件列表打开一张要修的图
2. 用笔刷涂掉水印 / 瑕疵区域（涂得稍微大一点没关系，LaMa 会自然补）
3. 点界面里的 **Run**（或 `Ctrl + Enter`） → 一键 inpaint
4. 满意 → 点右上角 **Save** 下载到本地（覆盖原图或另存到 `phaseA/slides_clean/`）
5. 全部修完 → 回到终端按 `Ctrl + C` 关闭服务

### 常用参数

```bash
# 端口冲突时自动+1，也可手动指定
python3 scripts/launch_iopaint.py --port 9090

# 不要自动打开浏览器（远程/无显示环境）
python3 scripts/launch_iopaint.py --no-browser

# 强制重装（IOPaint 版本升级 / 怀疑环境坏了）
python3 scripts/launch_iopaint.py --reinstall
```

### 单独走安装 / 检查 / 维护

```bash
# 仅安装，不启动
python3 scripts/setup_iopaint.py

# 检查是否已装（不装）
python3 scripts/setup_iopaint.py --check-only

# 强制重装
python3 scripts/setup_iopaint.py --reinstall

# 不用 HuggingFace 镜像（国外网络更快时可关）
python3 scripts/setup_iopaint.py --no-mirror
```

---

## 工具 3：ImageMagick 兜底（IOPaint 都装不上时）

效果远不如前两者，但**任何 macOS / Linux 都现成可用**（`brew install imagemagick`）。

```bash
# 在右下角画一个白色矩形盖住水印（坐标自己量）
magick phaseA/slides/01-cover.png \
       -fill "rgba(255,255,255,1)" \
       -draw "rectangle 1280,680 1580,710" \
       phaseA/slides_clean/01-cover.png
```

只适合背景是纯色 / 接近纯色的场景。背景花的不要用这条。

---

## 安装机制细节（给 agent 看）

**首次使用 launch_iopaint.py 会自动安装**：

1. 创建专属 venv：`~/.cache/ppt-craft-editable/venv/`
   - 不污染系统 Python
   - 不依赖用户其他环境
2. `pip install iopaint`（含 torch CPU 版，~800MB 下载、~2.5GB 落盘）
   - 默认走清华 PyPI 镜像
3. 预下载 LaMa 权重（~200MB）
   - 默认走 `HF_ENDPOINT=https://hf-mirror.com`
4. 写标记文件：`~/.cache/ppt-craft-editable/.lama-installed`
   - 二次运行直接跳过安装

**幂等性**：
- 标记 + venv 都健康 → 不重装
- 标记在但 venv 损坏 → 自动重建
- `--reinstall` → 强制清掉重来

**日志**：所有安装输出都同时写到 `~/.cache/ppt-craft-editable/setup.log`，装失败时让用户回看这个文件。

**失败兜底**：装失败时**不会卡住**或抛栈，会清晰打印：
1. 直接重试的命令
2. 跳过 retouch 用 Phase A 原图的选择
3. 用 `remove_corner_watermark.py` 批处理的兜底
4. 用 ImageMagick 矩形遮罩的最后手段

---

## 何时不要用 Stage 5.5

- **改文案 / 改排版 / 改视觉** → 回 Stage 5 retouch 重出，不要在像素层硬改
- **整页风格不对** → 回 Stage 2 / 2.5 重选风格 → 重出
- **要原生可编辑 PPTX（后期改文字）** → 那是 Phase C 的活，不是 Stage 5.5。在 Phase A 交付后用户主动询问的环节里同意进 Phase C 即可。

---

## 校验清单（修完之后）

- [ ] 水印 / 瑕疵已消失，肉眼无明显痕迹
- [ ] 修过的页和未修过的页**视觉风格仍然一致**（没出现某页特别糊的情况）
- [ ] 文件命名仍然连续（`01-*.png` `02-*.png` ...）
- [ ] 比例仍然统一（默认 16:9）
- [ ] 修后的图替换 / 补充进 `phaseA/slides/`（或新建 `phaseA/slides_clean/` 整套交付）
