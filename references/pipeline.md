# Pipeline — 端到端运行手册

`ppt-craft-editable` 是**自包含技能**：本目录已包含 Phase A（conversation-first + image-first + Stage 5.5 retouch）和 Phase C（分层生成 + HTML 文字编辑 + 渲染 PPTX）的全部资产，不依赖任何外部 skill。

> **关键路由**（也是 SKILL.md 顶层规则）：
> - **★ Stage 0**：用户首次触发本 skill，agent 默默跑 `python3 scripts/preflight.py`（自动装缺失 Python 包 + 调 doctor 看其它状态）。FAIL 才打断用户
> - **Phase A 默认主路径**：跑完 Stage 5（含可选 Stage 5.5 retouch）就交付图片型 PPTX
> - **Phase A 交付后必须主动询问 Phase C**：开放式问句，不强推、不沉默
> - **Phase C 用户驱动才执行**：用户明确同意才走 C1-C6
> - **Phase C 完成 = 终态**：不要再追问其他路径

---

## 总览

```
[用户] ─▶ Phase A (含 Stage 5.5) ─▶ [交付 + 主动询问 Phase C]
            │                          │
            ├ 3 规划文件               └ 图片型 PPTX + 全页定稿图
            ├ 风格预览
            ├ 终图
            └ 可选 retouch（去水印 / IOPaint）

如果用户在询问中同意 ↓

[Phase C 全流程] ─▶ [追加交付]
                       │
                       ├ phaseC/backgrounds/*.png
                       ├ phaseC/deck.json
                       └ <topic>-editable.pptx
```

---

## Phase A 执行

按 **`references/phaseA/workflow.md`** 跑 Stage 1 → Stage 5，不跳任何确认门禁。

### Stage 1 / 1.25 / 1.5 — 需求 → 内容基底 → 风格边界
- 轻量 intake，输出 baseline judgment
- 停 `需求确认`
- 内容稀薄就先做 `content_report.md`（模板：`templates/content_report_reference.md`）
- 风格边界只问 3 个问题（明暗 / 常规 vs 风格化 / 几套方向）

### Stage 2 / 2.5 / 2.75 — 风格预览 + refinement + 反演确认
- 用 `assets/preview_shell/index.html` 打开真实预览（必须先用 `inject_shell_images.py` 注入图）
- 出"首页 + 目录页 + 正文页"三类
- 拿到偏好后做风格反演，把视觉特征写成可复用规则
- 停 `风格确认`

### Stage 3 — 规划文件（顺序不能错）
1. `design_spec.md`（模板：`templates/design_spec_reference.md`）
2. `slide_blueprint.md`（模板：`templates/slide_blueprint_reference.md`）
3. `spec_lock.md`（模板：`templates/spec_lock_reference.md`）

停 `生成前确认`。

### Stage 4 — 出终图
- 先问用户：单图直出 / 多候选 picker
- 若多候选，先用 `assets/candidate_picker_shell/index.html` 让用户选
- 按 `spec_lock.md` 出整套页面
- 全程 image-first，禁用 PIL / SVG / PPT shapes / 截图渲染兜底

### Stage 5 — Review
- 用 `assets/review_shell/index.html` 评审
- 用户给 review JSON 时，用 `scripts/render_review_markup.py` 渲染标注图
- 用户**明确批准**整套终图

### Stage 5.5 — Retouch（用户驱动，可选）
详见 **[`references/phaseA/retouch.md`](phaseA/retouch.md)**。

### Phase A 完成后必须落盘的产物
```
phaseA/
├── previews/                # 风格预览
├── candidates/              # 多候选模式时
├── slides/NN-*.png          # 评审通过的终图（编号连续）
├── slides_clean/            # Stage 5.5 retouch 修过的版本（可选）
├── review/                  # 评审产物
├── imagegen-manifest.json   # 生成日志
└── <topic>-image-deck.pptx  # 图片型 PPTX
```

---

## ★ 必跨的交付动作：主动询问 Phase C

Phase A 跑完不能直接沉默结束，**必须**做一次主动询问。完整规则见 **SKILL.md 的"主动询问 Phase C 的规则"段**。要点：

1. 先告诉用户图在哪、PPTX 在哪、规划文档在哪
2. 简短说明"现在是图片版，不能在 PowerPoint 里直接改文字"
3. 询问是否要 Phase C（可编辑文字版）
4. 说明 Phase C 会参考 Phase A 定稿重新生成无字背景并叠加可编辑文字，不是从原图里精确抠字，背景可能有细微差异
5. 给出 Phase C 大致成本：每页约 2 张 imagegen（完整稿 + 擦字稿）
6. 给出"不需要"的选项——图片版本身就能直接拿去用

**不要**：
- 不询问就结束对话
- 不询问就直接进入 Phase C
- 反复追问 / 施压

---

## Phase C 执行（用户同意才跑）

按 **`references/phaseC/workflow.md`** 跑 C1–C6；如果是 Phase C-only 且没有 Phase A 图，先跑 C0 轻量预览门禁。背景反馈统一在 C5 编辑器里完成，不再插入独立 C2.5 背景审计壳子。

| 步骤 | 内容 | 关键脚本 / 资源 |
|---|---|---|
| C0（Phase C-only） | 先落地 `slide_outline.md` + `ppt大纲.md`，再出 1-2 页重新生成的无字背景 + 可编辑文字叠放预览，确认视觉基准后再批量生成 | `scripts/build_c0_preview.py` → `phaseC/c0/deck.json` + `phaseC/c0/editor.html` + `phaseC/c0/preview/` |
| C1 | 以 Phase A 定稿图作视觉参考生成无字背景；内部可先尝试直编，不干净再回退到完整稿 → view_image → 擦字稿 | imagegen + view_image |
| C2 | 校验擦字稿的预留区是否真留白 | `scripts/detect_reserved_zones.py` |
| C3 | 写 `phaseC/deck.json`（每页 background + text_boxes） | 模板见 `references/phaseC/workflow.md` Step C3 |
| C4 | 把 deck.json 注入编辑器壳子 | `scripts/inject_editor_deck.py` + `assets/editor_shell/index.html` |
| C5 | 用户在浏览器编辑器调文字，也可用背景反馈模式标注背景问题 → 导出新 deck.json / 背景反馈 | HTML 编辑器界面 |
| C6 | 先校验 deck.json，再渲染可编辑 PPTX | `scripts/validate_deck_json.py` + `scripts/json_to_pptx.py` |

### 逐页校验清单（Phase C）
- [ ] Phase C-only 没有 Phase A 图时，已先过页大纲确认：`slide_outline.md` 和 `ppt大纲.md` 已落地且用户确认
- [ ] Phase C-only 没有 Phase A 图时，已先过 C0：`phaseC/c0/deck.json`、`phaseC/c0/editor.html`、`phaseC/c0/preview/slide_*.png` 已生成，用户在 HTML 中确认 1-2 页重新生成的无字背景 + 可编辑文字叠放效果
- [ ] 直编后的成品图存在并通过校验；若失败则回退到 `phaseC/backgrounds/NN-full.png`
- [ ] 回退时第 2 稿（擦字稿）存在：`phaseC/backgrounds/NN.png`
- [ ] `detect_reserved_zones.py` 校验通过（或不合规处已 IOPaint 修补）
- [ ] `deck.json` 里该页的 `background` 路径可访问
- [ ] `deck.json` 里该页的 `text_boxes` 坐标在 0-1 范围
- [ ] `deck.json` 里所有 `font_family` 都在 SAFE_FONT_SET（见 `scripts/json_to_pptx.py` 顶部）
- [ ] `scripts/validate_deck_json.py phaseC/deck.json` 通过；有 error 时先修 deck.json，不猜补
- [ ] 如用户在 C5 提交背景反馈，已先修背景并重出 `phaseC/editor.html`，没有跳过反馈直接渲染

### Phase C 完成后落盘的产物
```
phaseC/
├── backgrounds/
│   ├── NN-full.png              # 回退时的完整稿（备查）
│   └── NN.png                   # 回退时的擦字稿（实际背景）
├── NN-zones.json                # 预留区声明
├── NN-zones.report.json         # 校验报告
├── deck.json                    # 单一真相源
├── editor.html                  # 注入后的编辑器
├── preview/slide_NN.png         # PIL 近似预览（可选）
└── <topic>-editable.pptx        # 文字可编辑 PPTX
```

---

## 一次跑通的最小命令清单

```bash
pip3 install python-pptx pillow numpy opencv-python

# Phase A 由对话驱动，没有"一条命令"；遵循 references/phaseA/workflow.md。

# Phase A 内每个壳子用之前都要注入
python3 scripts/inject_shell_images.py preview \
    --shell assets/preview_shell/index.html \
    --data  phaseA/previews/preview_data.json \
    --out   phaseA/previews/preview_filled.html

# Stage 5.5 retouch（用户驱动）
python3 scripts/remove_corner_watermark.py phaseA/slides/ -o phaseA/slides_clean/ --batch
python3 scripts/launch_iopaint.py --slides-dir phaseA/slides

# ── Phase A 交付，主动询问用户是否进 Phase C ──

# Phase C（用户同意才跑）
python3 scripts/detect_reserved_zones.py \
    phaseC/backgrounds/01.png \
    phaseC/01-zones.json \
    --report phaseC/01-zones.report.json

python3 scripts/inject_editor_deck.py \
    --shell assets/editor_shell/index.html \
    --deck  phaseC/deck.json \
    --out   phaseC/editor.html

python3 scripts/validate_deck_json.py phaseC/deck.json

python3 scripts/json_to_pptx.py \
    phaseC/deck.json \
    -o phaseC/<topic>.pptx \
    --preview-dir phaseC/preview
```

---

## 失败排错矩阵

| 现象 | 大概率原因 | 处理 |
|---|---|---|
| Phase A 风格预览没出真图 | imagegen 不可用 / 被降级到文字 mockup | 停在 Stage 2，明确告知阻塞原因，**不允许**进 Stage 3 |
| Phase A 出的图带工具水印（如 "Qoder AI生成"） | 出图通道叠加的水印 | 跑 Stage 5.5 retouch：`remove_corner_watermark.py` 批量擦；或换不带水印的出图通道 |
| 想用 IOPaint 修瑕疵但还没装 | 首次使用 | `launch_iopaint.py` 会自动调 `setup_iopaint.py`，等 5–10 分钟即可 |
| IOPaint 装失败：pip 网络断 | 网络不稳 / 没走镜像 | 重跑 `setup_iopaint.py` 自动续传；脚本默认走清华 PyPI 镜像 |
| IOPaint 装失败：LaMa 模型拉不下来 | HuggingFace 国内被墙 | 脚本默认走 `HF_ENDPOINT=https://hf-mirror.com`；仍失败可手动 `HF_ENDPOINT=https://hf-mirror.com iopaint download --model lama` |
| IOPaint 完全装不上 | 各种环境问题 | 兜底链：`remove_corner_watermark.py` 角落水印 → `magick -draw "rectangle ..."` 简单遮罩 → 用 Phase A 原图交付 |
| `slide_blueprint.md` 在风格反演确认之前写出来了 | Stage 顺序错乱 | 删除该文件，回 Stage 2.75 重做 |
| Phase A 完成后 agent 沉默结束 / 直接进入 Phase C | 违反"主动询问"规则 | **必须问一次**用户是否要 Phase C，再根据回答决定 |
| 用户对 "是否进 Phase C" 没正面回答 | 用户聊别的去了 | 不要打断，等用户自己提；下次再用本 skill 时也不强追 |
| Phase C 直编后没真擦掉文字 | 直接去字能力不足 / edit target 不对 | 重出，prompt 加强"擦除所有可编辑文字"；确认 view_image 指当前页定稿图 |
| Phase C 回退后的第 2 稿没真擦掉文字 | prompt 太弱 / view_image 没指对图 | 重出，prompt 加强"擦除所有可编辑文字"；确认 view_image 指当前页第 1 稿 |
| Phase C 第 2 稿擦掉过头，连装饰也没了 | prompt 没强调"保留装饰元素" | 重出，prompt 列出要保留的元素清单 |
| `detect_reserved_zones.py` 不合规 | 留白区颜色不一致 / 仍有残留 | IOPaint 局部擦 → 再校验 |
| 背景图整体需要复查 | 想先看背景层本身的问题 | 仍打开 C5 编辑器，切到 `🖊 背景反馈` 模式逐页标注；如用户提交背景反馈，先修背景再重出 `editor.html` |
| 文字在编辑器里好看但 PPTX 里偏 | 字体不在 SAFE_FONT_SET，跨平台 fallback | 改用安全字体集里的同类字体 |
| PPTX 里文字溢出框 | 字号太大 / 框太小 | 编辑器里调；或开 `auto_fit: true` |
| 行距异常 | line_spacing 单位用错（应该是倍数，1.0~3.0） | 改回倍数（默认 1.2） |
| 背景图在编辑器里不显示 | 浏览器跨目录禁访问 | 用 `inject_editor_deck.py --inline` 重新注入，或保证 file:// 路径正确 |
| 渲染前校验失败 | `deck.json` 缺字段、坐标越界、背景路径不可访问或颜色格式错误 | 按 `validate_deck_json.py` 的 `[error]` 路径修 deck.json，再重跑渲染 |
| 用户点了 "导出 deck.json" 但忘记保存 | 编辑器是单文件 HTML，刷新就丢 | 必须先让用户保存导出的 JSON 再关浏览器 |

---

## 断点续跑

**Phase A 内**：
- `phaseA/imagegen-manifest.json` 记录每页源图位置
- 中断后看哪些页已生成、哪些缺，补出缺的页 → review

**Phase C 内**：
- 直编后的成品图优先复用；回退时才看 `backgrounds/NN.png`
- `deck.json` 是单一真相源，编辑器里改完没导出就丢——用户必须主动导出 JSON
- 渲染失败不影响 deck.json，改完再跑 `json_to_pptx.py`

---

## 交付清单（最终给用户）

### Phase A 交付（默认）
1. ✅ 规划文档（可选 `content_report.md` + `design_spec.md` + `slide_blueprint.md` + `spec_lock.md`）
2. ✅ Phase A 图片型 PPTX —— 用于展示 / 汇报 / 演示
3. ✅ 每页定稿图 PNG —— 备份与对照

**+ 必跨动作：主动询问用户是否进 Phase C**

### Phase C 追加交付（用户同意才有）
4. ✅ 每页背景图（直编成品或回退背景，含完整稿备查）
5. ✅ `deck.json`（单一真相源，未来想再改文字可以再注入编辑器）
6. ✅ 校验报告（zones.report.json）
7. ✅ 文字可编辑 PPTX —— 在 PowerPoint / Keynote 里能直接改文字
