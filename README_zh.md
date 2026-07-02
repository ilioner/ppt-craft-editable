# PPT Craft Editable

[English](README.md) | 简体中文

---

这是一个用来制作 PPT 的 AI 技能。你只需要给出主题、材料和偏好，它会先帮你做出高完成度的图片版 PPT；如果你需要后期改字，也可以继续生成文字可编辑版 PPTX。

适合这些场景：

- 汇报、答辩、路演、培训、课程、提案等正式 PPT
- 只有一个主题，想让 AI 帮你补全结构和内容
- 已经有报告、论文、讲稿或提纲，想转成视觉完成度更高的 PPT
- 希望最终文字能在 PowerPoint / Keynote 里继续修改
- 已经有 PDF 幻灯片，想转成可继续改字的 PPTX

---

## 你会得到什么

默认情况下，你会先得到一套图片版 PPT：

- 每页定稿图
- 图片型 PPTX
- 内容和视觉规划文档

如果你选择继续做可编辑文字版，还会得到：

- 文字可编辑 PPTX
- 每页无文字背景图
- `deck.json`，记录每个文字框的位置、字体、字号和颜色
- 可选预览图，方便核对最终排版

文字可编辑版里，背景是一张图片，标题、正文、数字、日期、署名等是 PPT 里的真实文字框，可以直接改。

---

## 三种使用方式

### 方式一：先做图片版，再决定是否要可编辑文字版

这是默认方式。

你可以直接说：

```text
帮我做一个关于“新员工培训流程”的 PPT，10 页以内，面向刚入职的同事。
```

技能会先完成图片版 PPT。交付后，它会主动问你是否还需要文字可编辑版。你同意后，才会进入可编辑文字版流程。可编辑版会以图片版定稿作为视觉参考，重新生成无字背景并叠加可编辑文字框；它不是把原图里的文字精确抠掉，所以背景可能和图片版有细微差异。

### 方式二：一开始就只做文字可编辑版

如果你明确不想先做图片版，可以直接说：

```text
只做文字可编辑 PPTX，不要先做图片版。主题是“年度经营复盘”，12 页以内。
```

这时会直接进入可编辑版流程。它会先确认每页大纲，再做 1-2 页轻量预览，确认后才批量生成整套。

### 方式三：把现有 PDF 幻灯片转成可编辑 PPTX

如果你已经有一份 PDF 幻灯片，想把它变成后期可改字的版本，可以直接说：

```text
把这个 PDF PPT 转成可编辑 PPTX，我后面还要改里面的文字。
```

技能会：

1. 先从 PDF 每页提取可编辑文字框
2. 生成浏览器预览页让你确认 / 修改提取结果
3. 生成无字背景图
4. 接入可编辑文字编辑器并最终输出 PPTX

如果你是在仓库里本地执行当前 MVP 版 Phase D，命令顺序如下：

```bash
# 1) 从 PDF 提取 review 初稿
python3 scripts/pdf_extract_multimodal.py input.pdf -o phaseD/extraction.json

# 2) 生成 review HTML
python3 scripts/inject_extraction_review.py \
    --shell assets/phaseD_extraction_review_shell/index.html \
    --data phaseD/extraction.json \
    --out phaseD/extraction_review.html

# 约定：phaseD/extraction.json 里的 page_image 必须相对 phaseD 目录本身，
# 例如 work/page_images/01.png，不要写成 phaseD/work/page_images/01.png

# 3) 打开 phaseD/extraction_review.html，确认/修改文字框，
#    然后把导出的内容保存成 phaseD/extraction_confirmed.json

# 4) 生成 Phase C 背景图
python3 scripts/generate_backgrounds_from_pdf.py \
    --input phaseD/extraction_confirmed.json \
    --output-dir phaseC/backgrounds

# 5) 转成 Phase C deck，并顺手生成 editor.html
python3 scripts/extraction_to_deck.py \
    --input phaseD/extraction_confirmed.json \
    --output phaseC/deck.json \
    --editor-out phaseC/editor.html

# 6) 在 phaseC/editor.html 里确认最终 deck 后，渲染 PPTX
python3 scripts/json_to_pptx.py phaseC/deck.json \
    -o phaseC/<主题>-editable.pptx \
    --preview-dir phaseC/preview
```

说明：

- `scripts/generate_backgrounds_from_pdf.py` 和 `scripts/extraction_to_deck.py` 都支持两种输入：纯 JSON，或 review 页导出的整段 sentinel 文本。
- 当前 `image_only` / `rebuild` 页走的是可运行 MVP：本地脚本会先用确定性的 inpaint 擦掉文字区域；如果复杂背景还有瑕疵，再走现有 Phase C 的编辑器 / review / retouch 继续修。

---

## 使用过程

### 1. 需求确认

你先提供主题、用途、受众、页数范围和已有材料。材料可以很粗糙，例如几段文字、一个目录、会议纪要、论文摘要或报告内容。

技能会先整理理解，并让你确认方向是否正确。

### 2. 页大纲确认

在正式设计前，会先确认“每页放什么文字”。这一步会生成：

- `slide_outline.md`
- `ppt大纲.md`

你可以在文件里改标题、删页、加页、调整顺序或补充真实数据。确认后，后续预览和生成都会以这份大纲为准。

### 3. 风格预览

技能会生成多套风格方向，并把真实预览图放进 HTML 预览页。你在浏览器里看效果，选择喜欢的方向，或者要求混合、修改。

### 4. 图片版 PPT 生成

确认风格和生成前规划后，技能会生成全套页面定稿图，并用 HTML 评审页让你逐页确认。需要修图时，可以指出问题再返修。

图片版完成后，会交付：

- `phaseA/slides/`：每页定稿图
- 图片型 PPTX
- `content_report.md`、`design_spec.md`、`slide_blueprint.md`、`spec_lock.md` 等规划文件

### 5. 可编辑文字版生成

如果你需要可编辑文字版，技能会把每页拆成“背景图 + 可编辑文字框”。背景图会参考已确认的视觉稿重新生成无字版本，而不是对原图做像素级抠字；局部纹理、装饰或排版细节可能有轻微差异。

如果是一开始就只做可编辑版，会先生成 C0 轻量预览。这个预览用于确认“新生成的无字背景 + 可编辑文字框”的整体效果：

- `phaseC/c0/editor.html`：打开后可以看到无字背景和可编辑文字叠放效果
- `phaseC/c0/preview/`：静态预览图
- `phaseC/c0/deck.json`：临时预览数据

确认后，再批量生成正式背景和编辑器。

### 6. 在编辑器里调文字和反馈背景

可编辑文字版会生成：

- `phaseC/editor.html`

你打开它后可以：

- 修改文字
- 拖动文字框
- 调整文字框大小
- 改字体、字号、颜色、对齐
- 添加或删除文字框
- 切换到背景反馈模式，框选需要修改的背景区域

满意后，点击导出，把整段内容贴回对话。技能会根据导出的内容继续生成 PPTX；如果你标注了背景问题，它会先修背景，再让你重新确认。

### 7. 最终交付

最终可编辑版会生成：

- `phaseC/<主题>-editable.pptx`
- `phaseC/deck.json`
- `phaseC/backgrounds/`
- `phaseC/preview/`（可选）

---

## 你需要准备什么

越完整越好，但不完整也可以开始。

建议提供：

- PPT 主题
- 用途：汇报、答辩、培训、路演、提案等
- 受众：领导、客户、老师、同学、员工等
- 页数范围
- 已有材料：报告、讲稿、提纲、数据、论文、会议纪要等
- 风格偏好：正式、科技、温暖、极简、学术、商业等
- 是否需要文字可编辑版

如果你没有风格想法，可以不说，技能会先给你几套方向看。

---

## 常用说法

做默认图片版：

```text
帮我做一套“AI 产品运营复盘”的 PPT，面向部门周会，10 页左右。
```

直接做可编辑文字版：

```text
只做文字可编辑 PPTX，跳过图片版。主题是“新员工培训流程”，8 页左右。
```

给已有材料：

```text
我下面贴一份报告，请帮我整理成汇报 PPT，要求正式、清晰、适合给管理层看。
```

要求后期可改字：

```text
最终我要能在 PowerPoint 里改标题和正文，请走可编辑文字版。
```

---

## 文件说明

常见文件和目录如下：

```text
slide_outline.md          每页文字大纲
ppt大纲.md                同内容大纲，方便中文用户查找
content_report.md         内容基底，材料不足时会生成
design_spec.md            视觉风格规则
slide_blueprint.md        每页视觉和内容安排
spec_lock.md              生成约束，防止文字被烤进背景

phaseA/slides/            图片版每页定稿图
phaseA/review/            图片版评审页面和数据
phaseA/*-image-deck.pptx  图片型 PPTX

phaseC/c0/                可编辑版轻量预览，仅 Phase C-only 时出现
phaseC/backgrounds/       可编辑版背景图
phaseC/deck.json          可编辑版核心数据
phaseC/editor.html        可编辑文字和背景反馈编辑器
phaseC/*-editable.pptx    文字可编辑 PPTX
```

一般用户只需要关注：

- `ppt大纲.md`
- `phaseA/*-image-deck.pptx`
- `phaseC/editor.html`
- `phaseC/*-editable.pptx`

---

## 安装和环境

把这个技能目录放到你的 AI 客户端支持的 skills 目录下即可。

常见位置：

| AI 客户端       | skills 目录                                     |
| --------------- | ----------------------------------------------- |
| Codex CLI       | `~/.codex/skills/` 或 `$CODEX_HOME/skills/` |
| Claude Code CLI | `~/.claude/skills/`                           |

首次使用时，技能会自动运行环境自检并安装必要 Python 包：

```bash
python3 scripts/preflight.py
```

它会检查：

- Python 版本
- `python-pptx`、Pillow、numpy、opencv-python
- 字体、磁盘空间、网络状态
- 可选的 IOPaint 修图环境

如果你的客户端不会自动运行自检，也可以手动进入技能目录执行上面的命令。

---

## 注意事项

- 图片版 PPT 的文字是图片的一部分，不能在 PowerPoint 里直接改。
- 可编辑文字版可以改字，但背景仍然是图片。
- 可编辑版生成前，一定要在 `editor.html` 里确认并导出结果。
- 如果你在编辑器里标注了背景问题，技能会先修背景，不会直接生成最终 PPTX。
- 修图功能可能需要安装 IOPaint，首次可能需要几 GB 空间和数分钟时间。

---

## 给维护者

详细流程和内部规则见：

- `SKILL.md`
- `references/pipeline.md`
- `references/phaseA/workflow.md`
- `references/phaseC/workflow.md`

脚本入口集中在 `scripts/`。用户日常不需要手动运行这些脚本，除非你的 AI 客户端不支持自动执行。


---

## 致谢

本技能部分功能参考于：

- `ppt-image-first`

- - 致谢

本项目感谢 Linux.do 社区 对开源分享与传播的推动。
