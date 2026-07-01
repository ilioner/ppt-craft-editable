# Shell Injection — Phase A 工作流壳子图片注入

`assets/` 下三个 HTML 工作流壳子（preview / candidate_picker / review）出厂状态是**空架子**，图片都是占位 SVG / 示例数据。出真实图之后必须显式注入，否则用户打开页面看到的还是占位图。

注入只用一个脚本：**`scripts/inject_shell_images.py`**。

---

## 一句话规则

- 出图前不要打开壳子原模板；**只打开注入后的 `*_filled.html`**。
- 每个 Stage 出完图就跑对应的 `inject_shell_images.py`，再打开。
- 想离线分发（邮件 / 客户）就加 `--inline`，所有图片会变成 base64 嵌入 HTML。

---

## Stage 2 — 风格预览

### Data JSON 格式

```json
{
  "A": {
    "scheme_title": "方案 A｜稳妥商务科技",
    "scheme_subtitle": "适合正式汇报与等辩场景，稳重、有一点科技感。",
    "meta": {
      "一句话定位": "...",
      "封面页方向": "...",
      "正文页视觉语法": "...",
      "适用场景": "...",
      "风险点": "..."
    },
    "cover": "previews/A-cover.png",
    "toc":   "previews/A-toc.png",
    "body":  "previews/A-body.png",
    "captions": {
      "cover": "建立第一印象，重点看构图、主视觉和整体气质。",
      "toc":   "检查这套风格是否能支撑结构型页面，而不只是好看。",
      "body":  "检查信息进去以后是否清楚、稳、可读。"
    }
  },
  "B": { "cover": "...", "toc": "...", "body": "..." },
  "C": { "cover": "...", "toc": "...", "body": "..." }
}
```

- `meta` / `captions` / `scheme_title` / `scheme_subtitle` 都是**可选**，省略则保留壳子原文。
- 图片路径相对 data JSON 所在目录解析。
- group key（"A" / "B" / "C"）必须匹配 HTML 里已有的方案数；当前壳子默认 3 套。
- 每个方案下三个 key 固定为 `cover` / `toc` / `body`，分别对应 button 的 `data-preview-index 0/1/2`。

### 命令

```bash
python3 scripts/inject_shell_images.py preview \
  --shell assets/preview_shell/index.html \
  --data  phaseA/previews/preview_data.json \
  --out   phaseA/previews/preview_filled.html
```

打开 `phaseA/previews/preview_filled.html`，给用户对比 3 套方向。

---

## Stage 4 — 多候选选图（仅当用户选了"多候选 picker"模式）

### Data JSON 格式

```json
{
  "slides": [
    {
      "id": "01-cover",
      "title": "封面",
      "subtitle": "首页 / Hero",
      "candidates": [
        "phaseA/candidates/01/cand-01.png",
        "phaseA/candidates/01/cand-02.png",
        "phaseA/candidates/01/cand-03.png"
      ]
    },
    {
      "id": "02-toc",
      "title": "目录",
      "subtitle": "TOC",
      "candidates": [
        "phaseA/candidates/02/cand-01.png",
        "phaseA/candidates/02/cand-02.png"
      ]
    }
  ]
}
```

- 每个 slide 至少 1 张 `candidates`，可多张。
- `title` / `subtitle` 可选，省略时退化到 id。

### 命令

```bash
python3 scripts/inject_shell_images.py candidate \
  --shell assets/candidate_picker_shell/index.html \
  --data  phaseA/candidates/candidate_data.json \
  --out   phaseA/candidates/picker_filled.html
```

打开 `phaseA/candidates/picker_filled.html`，让用户给每页选一张。选完后再生成（如果该页选中的还不是终图，可在最终出图阶段以选中那张为参考再出）。

---

## Stage 5 — 评审

### Data JSON 格式

```json
{
  "slides": [
    { "id": "01-cover", "title": "封面", "subtitle": "Hero",
      "image": "phaseA/slides/01-cover.png" },
    { "id": "02-toc",   "title": "目录", "subtitle": "TOC",
      "image": "phaseA/slides/02-toc.png" },
    { "id": "03-body",  "title": "正文 1", "subtitle": "Body p1",
      "image": "phaseA/slides/03-body.png" }
  ]
}
```

- 每个 slide 必须有 `image`。
- 注入器会同时清除 review_shell 的 `localStorage` 缓存，避免上一轮评审遗留把新数据盖住。

### 命令

```bash
python3 scripts/inject_shell_images.py review \
  --shell assets/review_shell/index.html \
  --data  phaseA/review/review_data.json \
  --out   phaseA/review/review_filled.html
```

打开 `phaseA/review/review_filled.html`，让用户逐页评审。用户给出的 review JSON 仍然交给 `scripts/render_review_markup.py` 渲染标注图，用于下一轮 retouch。

---

## `--inline` 模式

默认是相对路径模式：HTML 里的 `src` 写成相对 `--out` 的路径，要求图片仍然存在于磁盘上对应位置。

加 `--inline` 后：

```bash
python3 scripts/inject_shell_images.py preview \
  --shell assets/preview_shell/index.html \
  --data  preview_data.json \
  --out   /tmp/preview_to_send.html \
  --inline
```

所有图片会被读出来 → base64 编码 → 写成 `data:image/png;base64,...` 直接嵌入 HTML。

- 优点：单文件，发邮件、离线打开都没问题。
- 缺点：文件会大几倍。9 张 1MP 的预览图嵌进来大约 ~10–20 MB。

---

## 反模式（不要这样做）

- ❌ 不要直接打开 `assets/preview_shell/index.html` 给用户看——里面是写着 "Cover preview placeholder" 的占位 SVG。
- ❌ 不要在出图后跑 `build_preview_html.py`——`build_*.py` 只是从 base64 还原模板，**不注入任何真实数据**，跑完图片还是占位。
- ❌ 不要复制壳子原文件然后手工替换 `src=`——既容易漏改也容易破坏 button 的 `data-preview-group/index`；用 `inject_shell_images.py` 就好。
- ❌ 不要把 inject 后的文件命名成 `index.html` 覆盖原模板——下一次出图就没法再次注入了。固定用 `*_filled.html`。

---

## 校验清单

每次注入完应该看到：

- [ ] 打开 `*_filled.html`，图片真实显示，无 "placeholder" 占位文字
- [ ] 浏览器 devtools network 面板里，对应的 PNG 请求都是 200（非 inline 模式）
- [ ] preview：lightbox 点击放大功能正常；左右切换正常
- [ ] candidate：每页可滑动浏览全部候选；选中状态保存到 localStorage 正常
- [ ] review：可以画框、写评注、导出 review JSON 正常
