---
name: ppt-craft-editable
description: >-
  端到端 PPT 全流程，单技能自包含。用户首次触发本 skill 时，agent 必须默默跑 scripts/preflight.py 做环境自检 + 自动安装缺失的 Python 包；FAIL 才打断用户。
  环境通过后走 conversation-first + image-first 工作流：多阶段对话、内容补强、风格预览、规划锁定、出每页定稿图，并在用户驱动下做图像级 retouch（去水印 / 去瑕疵，内置 IOPaint 自动安装）。最终交付高完成度图片型 PPTX。
  Phase A 结束后必须主动询问用户是否要可编辑文字版（Phase C）；若同意，进入 Phase C：以 Phase A 定稿图作为视觉参考，重新生成"带装饰、留白文字区"的无字背景图 + HTML 编辑器调文字 → 一键渲染原生可编辑 PPTX。
  用户明确要求"只做可编辑版 / 只跑 Phase C / 跳过图片版"时，直接进入 Phase C-only 模式，不执行 Phase A 的任何生成、预览、review、retouch。
  ★ Phase D - PDF PPT编辑分支：用户上传 PDF 幻灯片时，自动判断每页是矢量文本还是图片型，用多模态模型抽取文案结构，在 HTML 预览页让用户确认后，生成无字背景 + 可编辑文字框，最终输出原生可编辑 PPTX。
  ★ 当对话中出现 ===PPT-CRAFT-EDITABLE / DECK FROM EDITOR===、===PHASE-D / CONTENT EXTRACTION CONFIRMED===、旧标记 ===PPT-IMAGE-FIRST-EDITABLE / DECK FROM EDITOR=== 或 ===DECK JSON BEGIN/END=== 标记时，agent 必须立刻把标记之间的 JSON 原样写入对应文件并跑相应脚本，不解读不修改不追问。
  当用户需要做汇报 / 答辩 / 路演 / 提案 PPT，或只丢一个主题想要完整成品，或上传 PDF 想转可编辑版时使用。
---

# ppt-craft-editable — 一条龙 PPT 技能（自包含）

---

## ★★★ Stage 0 — 用户首次触发本 skill，agent 默认自动跑环境自检 + 自动修复 ★★★

**这是本 skill 最高优先级的规则，覆盖一切其他规则。**

用户首次说要做 PPT、首次触发本 skill 时，agent **不需要问用户**，**直接默默跑**：

```bash
python3 scripts/preflight.py
```

`preflight.py` 会：
1. 检查 Python 版本（不够则停，让用户处理）
2. 检查 4 个必备 Python 包，**缺的自动 pip install**（含 --user fallback；首次可能 2-5 分钟，OpenCV 较大）
3. 装完后自动调 `doctor.py` 做完整体检（字体 / 磁盘 / 网络 / IOPaint 状态 / skill 完整性）
4. 全部通过 → 退码 0 → agent 进入 Stage 1
5. 仍有阻塞 → 退码 1 → agent 把缺什么和怎么修念给用户听，等用户处理

### preflight 自动会做的事 vs 不会做的事

| 类别 | preflight 会自动做 | 不会做（请求用户处理） |
|---|---|---|
| Python 包 | ✅ `pip install python-pptx pillow numpy opencv-python` | — |
| Python 版本 | — | ❌ 不替用户装新 Python（动用户系统太危险） |
| 系统字体 | — | ❌ 跨平台不一致 + 需要 sudo |
| IOPaint | — | ❌ 那是 ~3GB / 5-10 分钟的活，只在 Stage 5.5 真正用到时再装 |
| 磁盘空间 | ✅ **早期就查并按三档处理**（见下） | ❌ 不会自动清磁盘 |
| imagegen 通道 | — | ❌ 那是 agent harness 的事，preflight 探不到 |

### 磁盘空间的三档处理

preflight 在装任何东西**之前**就先查磁盘。这一项很重要——磁盘满会导致 pip 装包到一半失败、生成图片时写盘失败、IOPaint 模型下载失败，错误信息往往很难懂。

| 磁盘剩余 | preflight 行为 | agent 该怎么说 |
|---|---|---|
| **< 0.5 GB** | 直接 ❌ 退码 1 阻塞 | 念给用户："您的磁盘只剩 X GB，连基础依赖都装不下。请清理出至少 4 GB 后再用本 skill。可以删的常见目录：下载目录、回收站、~/.cache、不用的 Docker 镜像。" |
| **0.5 – 2 GB** | ⚠️ 警告但继续 | 装包前告诉用户："您的磁盘只剩 X GB，能装但很紧张。如果后面要修瑕疵（用 IOPaint），还要再 3GB。建议现在清出更多空间。" |
| **2 – 4 GB** | ✅ 通过 + 提示 IOPaint 需要 3GB | 一笔带过 |
| **≥ 4 GB** | ✅ 通过 | 不用特别提 |

如果 agent 在 Phase A / Phase C 跑到一半看到 `No space left on device`、`OSError: [Errno 28]`、`Could not write file` 这类错误，**立刻停下告诉用户磁盘满了**，别重试浪费 imagegen 调用。

### agent 的行为对照表

| preflight 退出码 | 屏幕上看到 | agent 怎么办 |
|---|---|---|
| **0** | 末尾"✅ 环境就绪" | 简短报告"环境就绪"，进入 Stage 1（**不要再问用户**） |
| **0** + 中间有⚠️ | 末尾"✅ 环境就绪"但 doctor 段有 WARN | 同上 + 顺带提一句"有 N 个可选项缺失，影响 XXX，要不要现在修？" |
| **1** | 末尾"❌ 自检仍有阻塞项" | **必须停**，把 FAIL 项和修复命令念给用户听 |

### 跑 preflight 的反模式（不要做）

- ❌ 不跑 preflight 直接进 Stage 1
- ❌ 跑 preflight 之前先问用户"要不要装 Python 包"——用户不一定知道答案；自动装是默认行为
- ❌ preflight 报 FAIL 还硬着头皮走下去（迟早卡在 Stage 2 或 Phase C 渲染）
- ❌ 把 preflight 当成"每轮都要跑一次"（只在用户首次触发或环境变更后跑）

### 何时算"首次触发"

- 用户在当前对话里第一次说要做 PPT
- 或者用户明说"换了机器 / 重装了环境 / 重跑一次自检"
- 或者上次跑 preflight 后已经过了很长时间（agent 自行判断）

后续轮次只要环境没变，**不需要重跑**——浪费时间。

### 给用户的"我在装东西"提示

如果 preflight 真的在装包（首次场景，可能 2-5 分钟），agent 在等待之前应当告诉用户：

> 第一次使用，正在自动安装 4 个 Python 依赖包（python-pptx / Pillow / numpy / opencv-python）。
> 首次安装可能需要 2-5 分钟，OpenCV 单独就 ~100MB，期间终端会看起来在卡，请稍等。
> 装完会自动继续，您不用做任何操作。

这样用户不会以为卡死了去 Ctrl+C。

### imagegen 通道的额外验证

preflight 和 doctor 都无法直接探测 agent harness 的 imagegen 通道。所以**在 Stage 2 出第一张真实预览之前**，agent 还要再做一次"出图通道可用性测试"：用最小 prompt 出一张极小尺寸的图，确认通道通。这一步失败不算 preflight 失败，但必须**停在 Stage 2 之前**，告诉用户出图通道不可用、不能继续。

---

## ★★★ Phase A HTML 硬门禁（agent 必须自检，不可跳过）★★★

Phase A 流程中**必须有两次让用户在浏览器里看 HTML**——这是这条 skill 区别于"只在对话里贴图说说"的根本动作。
agent 在长对话里很容易忘记打开壳子，所以下面这两个动作是**硬门禁**，跑漏了视同 Phase A 没做完：

| 门禁 | 时机 | 必须打开的文件 | 注入命令 |
|---|---|---|---|
| **G-Preview** | Stage 2 风格预览出图后、用户做"风格确认"前 | `phaseA/previews/preview_filled.html` | `python3 scripts/inject_shell_images.py preview --shell assets/preview_shell/index.html --data phaseA/previews/preview_data.json --out phaseA/previews/preview_filled.html` |
| **G-Review** | Stage 5 全页定稿图出来后、用户做"终图批准"前 | `phaseA/review/review_filled.html` | `python3 scripts/inject_shell_images.py review --shell assets/review_shell/index.html --data phaseA/review/review_data.json --out phaseA/review/review_filled.html` |
| **G-Candidate**（条件触发） | Stage 4 用户选了"多候选 picker"模式时 | `phaseA/candidates/picker_filled.html` | `python3 scripts/inject_shell_images.py candidate --shell assets/candidate_picker_shell/index.html --data phaseA/candidates/candidate_data.json --out phaseA/candidates/picker_filled.html` |

### 每个门禁的最小自检（agent 跑完必须勾选）

- [ ] `*_filled.html` 已生成在上表列的精确路径
- [ ] 已经尝试用 `open` / `xdg-open` / `start` 主动为用户打开它（失败再退路径）
- [ ] 在对话里**显式告诉用户**"已在浏览器打开 `<filename>`，请在里面确认 / 选图 / 给反馈"
- [ ] 等用户反馈（确认 / 复制粘贴回 JSON / 选图编号）后才进入下一 Stage

### 反模式（一旦发生立刻自我纠正）

- ❌ 出完图直接在对话里贴几张缩略图、问"喜欢哪套？" —— 跳过了 G-Preview，**不算过门禁**
- ❌ "我已经生成了 9 张预览图在 phaseA/previews/，请查看" —— 用户不会打开原图；必须开壳子
- ❌ 出完终图直接说"以下是 N 页定稿，您看看？" —— 跳过了 G-Review
- ❌ 打开了 `assets/preview_shell/index.html` 或 `assets/review_shell/index.html`（裸壳，里面是占位 SVG / 示例数据）—— **必须打开 `*_filled.html`**
- ❌ 跑了 `build_*.py` 当成"已经注入" —— `build_*.py` 只还原模板不注入数据，跑完图还是占位
- ❌ G-Preview 还没过就跳到 Stage 3 写 `design_spec.md` —— 风格没经过浏览器确认，规划文件作废
- ❌ G-Review 还没过就导出图片型 PPTX 或主动询问 Phase C —— 终图没经过浏览器评审，交付作废

### 如果环境真的打不开浏览器

只在三件事都成立时才允许跳过"自动打开"动作：
1. agent 真的试过 `open` / `xdg-open` / `start` 都报错
2. 已经在对话里**明确说明**为什么打不开
3. 已经把 `*_filled.html` 的**绝对路径**给到用户，提示他自己双击打开

即使浏览器打不开，**注入步骤本身不能跳**（`*_filled.html` 仍然必须生成）。

---

## Phase C-only 入口

当用户明确说出以下任一意图时，默认进入 **Phase C-only**：

- 只做可编辑版
- 只跑 Phase C
- 跳过图片版
- 直接给我文字可编辑 PPTX

### Phase C-only 必守
- **不执行 Phase A**：不跑 Stage 1-5，不做风格预览，不做图片型 PPTX
- **优先复用现有成果**：如果用户已经给了 Phase A 产物，直接拿来用
- **必须先过页大纲确认门禁**：不管有无 Phase A 产物，C-only 路径也必须先写 `slide_outline.md`，并同步写一份同内容的 `ppt大纲.md` 方便用户查找；等用户确认后才进 C0/C1。若用户已有完整内容稿且页面结构清晰，可由 agent 直接梳理给用户确认，不需要反复追问细节
- **缺输入先补最小集**：如果缺 `design_spec.md` / `slide_blueprint.md` / `deck.json`，先收齐再进 C1-C6
- **必须先过 C0 轻量预览门禁**：没有 Phase A 图作为视觉证据时，先做 1-2 页”重新生成的无字背景 + 可编辑文字预览”，并落地 `phaseC/c0/deck.json`、`phaseC/c0/editor.html`、`phaseC/c0/preview/slide_*.png`；让用户确认视觉基准后再批量生成全套背景
- **不再主动询问 Phase C**：因为当前会话已经在 Phase C 路径里
- **Phase C 完成即终态**：拿到可编辑 PPTX 后结束，不折返到其他路径

### Phase C-only 的最小输入
- 主题或已有报告稿
- 页数 / 受众 / 目的
- 可复用的内容稿或页面结构
- 如已存在，优先直接使用 `design_spec.md`、`slide_blueprint.md`、`spec_lock.md`

### Phase C-only 的视觉基准
- `design_spec.md` 是视觉基准，不依赖 Phase A 成品图；它必须锁定明暗、色彩角色、字体气质、背景材质、装饰语言、留白规则和页面类型语法
- `slide_blueprint.md` 决定每页哪些元素进入背景、哪些内容必须保持为可编辑 TextBox
- `spec_lock.md` 必须写清：背景只承载氛围、结构、装饰和非编辑性视觉元素；标题、正文、数字、日期、署名等后期可能改的内容必须进入 `deck.json.text_boxes`
- C0 预览只用于确认视觉基准，不产出图片型 PPTX，也不折返 Phase A；用户确认 C0 前，`slide_outline.md` / `ppt大纲.md` 以及 `phaseC/c0/` 三类预览产物必须真实存在

---

把三套互补能力融成一个 skill：

- **Phase A — 对话式定稿 + retouch（默认主路径）**
  Conversation-first + image-first 工作流：多阶段对话 → 内容基底 → 风格预览 → 风格反演确认 → 规划文件 → 每页定稿图 → 用户驱动的图像级 retouch（去水印 / 去瑕疵）。
- **Phase C — 分层生成 + HTML 文字编辑（可编辑路径）**
  Phase A 完成后**主动询问用户是否要可编辑文字版**。若用户同意，Phase C 会以 Phase A 定稿图作为视觉参考，重新生成不含可编辑文字的背景层，再把文字作为外挂图层在 HTML 编辑器里调整 → 一键渲染成原生可编辑 PPTX。注意这不是从 Phase A 图片中精确抠掉文字，背景可能与 Phase A 定稿有细微差异；若直接编辑不干净，再回退到重生成背景 + 擦字稿。文字始终是真 TextBox（PPT 里可改）。
  如果用户一开始就明确要求只做可编辑版，则直接走 **Phase C-only**，不进入 Phase A。
- **Phase D — PDF PPT 编辑分支（PDF 导入路径）**
  用户上传 PDF 幻灯片时，自动判断每页是矢量文本（可直接提取）还是图片型（需多模态理解）。用多模态模型抽取文案结构、角色、位置，生成 extraction.json 并在 HTML 预览页让用户确认。确认后按背景策略（clean 擦字 / rebuild 重建）生成无字背景，写入 phaseC/deck.json，接入 Phase C 编辑器（C4-C6）最终输出可编辑 PPTX。

```
[用户的模糊需求]
        │
        ▼
┌── Phase A（默认主路径）─────────────────┐
│  Stage 1     Intake + 需求确认           │
│  Stage 1.25  content_report.md          │
│  Stage 1.4   ★ 页大纲确认门禁           │
│              slide_outline.md → 用户确认 │
│  Stage 1.5   风格边界（3 个短问题）       │
│  Stage 2     多套风格预览（首/目/正）     │
│  Stage 2.5   风格 refinement             │
│  Stage 2.75  风格反演 + 风格确认          │
│  Stage 3     design_spec /              │
│              slide_blueprint /          │
│              spec_lock + 生成前确认       │
│  Stage 4     全页定稿图                  │
│  Stage 5     review + 用户批准           │
│  Stage 5.5   ★ retouch（可选，用户驱动）  │
└──────────────┬──────────────────────────┘
               │
               ▼   交付：图片型 PPTX + 全页定稿图 + 规划文档
               │
   ┌───────────┴───────────┐
   │ ★ 必须主动询问用户 ★    │
   │ "PPT 已交付。是否需要   │
   │  可编辑文字版（Phase C）│
   │  ——文字能在 PPT 里直接   │
   │  改？这会参考定稿图重生  │
   │  成无字背景，可能有细微 │
   │  差异；                 │
   │  每页约 2 张 imagegen。" │
   └─────────┬─────────────┘
             │
        用户同意 → 进 Phase C
             │
             ▼
┌── Phase C（可编辑文字版）─────────────────┐
│  C0  Phase C-only 轻量预览门禁（条件触发）│
│  C1  双轨生成背景                         │
│      (完整稿 → imagegen 擦字稿)           │
│  C2  detect_reserved_zones 校验           │
│  C3  写 deck.json                         │
│  C4  inject_editor_deck.py 注入编辑器     │
│  C5 ★ 统一编辑 + 背景反馈门禁（必跑）     │
│      文字模式 改字 / 拖框 / 调样式         │
│      背景反馈模式 矩形/画笔/注释点 + 意见  │
│      → 导出包贴回（含可选 BG REVIEW 段）   │
│      → 有 BG REVIEW: 修背景 → 重出编辑器   │
│      → 无 BG REVIEW: 进 C6                 │
│  C6  校验 deck.json → 渲染 PPTX           │
└──────────────┬──────────────────────────┘
               ▼
[追加交付：文字可编辑 PPTX + deck.json + backgrounds/]
```

---

## I/O Contract

### Phase A 必交付（默认）
- `content_report.md`（用户没给完整内容稿时）
- `slide_outline.md`（Stage 1.4 页大纲确认，用户已批准）
- `design_spec.md` / `slide_blueprint.md` / `spec_lock.md`
- 每页定稿图 `phaseA/slides/NN-*.png`
- **图片型 `.pptx`**（高完成度视觉稿，用于汇报/展示——这是默认终交付物）
- `phaseA/imagegen-manifest.json`

### Phase C 追加交付（用户同意走可编辑路径时）
- 每页背景图 `phaseC/backgrounds/NN.png`（+ 第 1 稿 `NN-full.png` 备查）
- `phaseC/deck.json`（单一真相源，编辑器 / 渲染器共同消费）
- 每页 `phaseC/NN-zones.json` + `phaseC/NN-zones.report.json`
- **文字可编辑 `.pptx`**（背景 = Picture，文字 = 真 TextBox，跨平台稳定）
- 可选 `phaseC/preview/slide_NN.png` 近似对照图

### Phase D 交付（PDF 导入路径）
- `phaseD/extraction.json`（初版抽取结果）
- `phaseD/extraction_review.html`（HTML 预览页）
- `phaseD/extraction_confirmed.json`（用户确认后的版本）
- 每页背景图 `phaseC/backgrounds/NN.png`（clean 擦字或 rebuild 重建）
- `phaseC/deck.json`（从 extraction 转换而来）
- **文字可编辑 `.pptx`**（最终产物，接入 Phase C 渲染管道）

### 输入
PPT 主题 / 粗略目标 / 零散材料 / 已有报告稿 / PDF 幻灯片；可选锚点（受众、页数、身份锚点、用途场景、参考图、风格倾向）。

### 确认门禁
- **5 个必有门禁**（Phase A）：需求确认 → **页大纲确认** → 风格确认 → 生成前确认 → 终图评审
- **第 4 个门禁（强制主动询问）**：Phase A 终图交付后**必须主动问**用户是否需要 Phase C 可编辑文字版
- **Phase C 内的门禁**：用户在 HTML 编辑器里点 "导出 deck.json" 表示满意
- **Phase D 内的门禁（G-D-ContentConfirm）**：用户在 extraction_review.html 里确认/修改文案后点"导出确认"

### 比例
默认 `16:9`。**Phase A/C/D 全程必须同一比例**，禁止中途切换。

---

## ★ 主动询问 Phase C 的规则（最关键的行为）

**Phase A 全部交付完成后，必须主动询问一次**用户是否要走 Phase C。这是这条 skill 的硬约束。

### 询问时机
- Phase A Stage 5（review）通过 + Stage 5.5 retouch 处理完（如果跑了）
- 已经把图片型 PPTX 和所有定稿图给到用户
- **在结束对话前**

### 询问话术（参考，可调措辞）

> 图片版 PPT 已经做好了：
> - 图片型 PPTX：`<path>`
> - 全 N 页定稿图：`<path>`
> - 规划文档：`<paths>`
>
> 现在的成品是**图片版**，每页是一整张图——好处是视觉密度最高、跨平台不会跑版；缺点是文字不能在 PowerPoint 里直接改。
>
> 如果您后续可能要**改文字**（比如换日期、换名字、换关键数字、改标题措辞），我可以继续走 **Phase C** 给您出一份**文字可编辑版**：
> - 参考当前定稿图重新生成无字背景（保留整体风格和装饰，预留文字区；不是从原图里精确抠字，可能有细微差异）
> - 文字作为独立图层，在浏览器编辑器里调
> - 一键渲染成原生可编辑 PPTX
> - 大致成本：每页约 2 张 imagegen（背景完整稿 + 擦字稿），N 页约 X 次调用
>
> 要不要进 Phase C？（不需要也可以，图片版本身就能直接拿去汇报）

### 询问后的分支
- 用户说**要 / 好 / 进 Phase C / 我后期还要改字** → 按 `references/phaseC/workflow.md` 跑 C1-C6
- 用户说**不用 / 这样就够了 / 先这样** → 结束对话，不要再追问
- 用户**没正面回答**（比如继续聊别的） → 不要打断，等用户自己提

### 反模式（不要这样做）
- ❌ 不询问就直接进入 Phase C
- ❌ 不询问就直接结束对话（用户可能不知道有可编辑选项）
- ❌ 反复追问、施压让用户走 Phase C
- ❌ 把"是否进 Phase C"作为 confirmation gate 强卡用户（它是一个开放问题，不是必跨门禁）

---

## ★ 用户从编辑器贴回内容时的处理规则（极重要）

Phase C editor.html 里用户点”导出 / 继续生成”后会得到一段带 sentinel 的”指令包”，现在有两种格式：

**格式 A（只有文字改动，没有背景反馈）**

```
===PPT-CRAFT-EDITABLE / DECK FROM EDITOR===
...
===DECK JSON BEGIN===
{ ... 完整 deck.json ... }
===DECK JSON END===
```

**格式 B（文字改动 + 背景反馈，同一次导出）**

```
===PPT-CRAFT-EDITABLE / DECK FROM EDITOR===
...
===DECK JSON BEGIN===
{ ... 完整 deck.json ... }
===DECK JSON END===

===PHASEC BACKGROUND REVIEW BEGIN===
{ ... phasec-background-review-v1 ... }
===PHASEC BACKGROUND REVIEW END===
```

### 当 agent 在对话里看到这两种标记时，**必须**：

**格式 A（只有 DECK JSON）→ 直接渲染**
1. 把 `===DECK JSON BEGIN/END===` 之间内容**原样**写入 `phaseC/deck.json`（覆盖旧版）
2. 跑 `python3 scripts/json_to_pptx.py phaseC/deck.json -o phaseC/edited.pptx --preview-dir phaseC/preview`
3. 把 `phaseC/edited.pptx` 路径告诉用户，结束

**格式 B（还有 PHASEC BACKGROUND REVIEW）→ 先修背景，再重开编辑器**
1. 同样先把 `===DECK JSON BEGIN/END===` 之间内容写入 `phaseC/deck.json`（保留文字改动）
2. 读取 `===PHASEC BACKGROUND REVIEW BEGIN/END===` 里的 `pages[]`，按 `requested_action` + `page_comment` / `markup` 修 `phaseC/backgrounds/*.png`：
   - `retouch-local` → IOPaint 局部修补当前背景
   - `regenerate-background` → 以反馈为依据重生成该页背景
   - `adjust-text-zones` → 调整背景留白区，必要时同步 `phaseC/*-zones.json`；文字框位置等后续在编辑器里调
   - `approved` → 该页背景通过，不修
3. 背景修完后，重新注入编辑器：`scripts/inject_editor_deck.py`（用刚保存的 deck.json + 新背景）
4. 打开新的 `editor.html` 让用户再确认一次，**不要**直接渲染 PPTX

**不变的规则（格式 A / B 共同遵守）**
- **不要”解读” / “总结” / “评论” JSON 内容**——数据已定稿，只搬运
- **不要修改 deck.json 任何字段**——不改字号字色不重排版
- **以这一份 deck.json 为最新真相源**——不用旧版本

### 反模式（不要做）

- ❌ 格式 B 有背景反馈却直接渲染 PPTX —— 用户的修背景意见会被丢掉
- ❌ 格式 A 收到又去问”要不要渲染” —— sentinel 已写明，直接渲染
- ❌ 用之前生成的 deck.json 老版本渲染 —— 必须用贴回来的这一份
- ❌ 把 `phasec-background-review-v1` 段当成 Phase A review 去跑 `render_review_markup.py`
- ❌ 用背景反馈的意见直接改 `deck.json.text_boxes`（绕过背景问题）

### 用户行为提示（agent 该告诉用户的）

当 Phase C 编辑器打开时，agent 应明确告诉用户：

> 编辑器已打开。
> - **改完文字后**：点右上角 **”导出 / 继续生成”** → 复制整段（带 `===` 标记）→ 粘贴回对话框，我会直接渲染 PPTX
> - **发现背景要改**：点 **”🖊 背景反馈”** 切换到标注模式，对背景框选/画笔/写意见，然后同样导出整段贴回来，我会先修背景再重新打开编辑器给你确认
>
> 两件事可以同时做：先在文字模式调好字，再切到背景反馈模式标注，最后统一导出一次即可。

### 失败兜底

- 用户只粘了裸 JSON（无 sentinel）→ 仍保存为 `phaseC/deck.json` 并渲染，但提醒下次复制整段
- 用户粘了 sentinel 但 JSON 有错（缺 slides 等）→ 报错，让用户回编辑器修后重新导出，不自动猜补

---

## 何时使用本技能 / 何时只走 Phase A / 何时上 Phase C / 何时走 Phase D

| 用户场景 | 路径 |
|---|---|
| 只要好看的视觉稿、做完汇报就结束 | **Phase A**（默认） |
| 没明确点名，只丢主题、要完整成品 | **Phase A**（默认） |
| Phase A 出图有水印 / 小瑕疵想擦掉 | Phase A + Stage 5.5 retouch |
| Phase A 完成后用户说要可编辑 | **Phase A → Phase C**（按上面"主动询问"规则） |
| 用户一开始就说"要可编辑 / 后期改字" | **Phase C-only**（先补最小输入，再跑 C1-C6） |
| 用户明确说"只做可编辑版 / 跳过图片版" | **Phase C-only** |
| 用户上传 PDF 幻灯片想转可编辑版 | **Phase D**（PDF 导入路径） |
| 用户说"把这个 PDF PPT 转成可以改字的" | **Phase D** |
| 用户提供 PDF + 明确说要编辑文字 | **Phase D** |

---

## ★ Phase D 入口与 Sentinel 处理规则

### 触发条件

当用户满足以下任一条件时，进入 Phase D：
- 上传或提供 PDF 文件路径，并提到"转成可编辑" / "想改文字" / "PPT 编辑"
- 明确说"把 PDF 转成 PPTX" / "PDF 转可编辑 PPT"
- 提供 PDF 并询问能否编辑其中内容

### Phase D Sentinel 标记

当对话中出现以下标记时：

```
===PHASE-D / CONTENT EXTRACTION CONFIRMED===

本次从 PDF 提取了 N 页内容，已在预览页确认。

===EXTRACTION JSON BEGIN===
{ ... }
===EXTRACTION JSON END===
```

agent 必须：
1. 把 `===EXTRACTION JSON BEGIN/END===` 之间的内容**原样**写入 `phaseD/extraction_confirmed.json`
2. 不解读、不修改、不追问 JSON 内容
3. 直接进入 D3 背景处理：
   - 简单页（strategy: "clean"）→ 擦字保留原背景
   - 复杂页（strategy: "rebuild"）→ 仿照重建背景
4. 生成 `phaseC/backgrounds/*.png`
5. 把 extraction.json 转成 `phaseC/deck.json`
6. 接入 Phase C 编辑器（C4-C6）

### Phase D 不做的事

- ❌ 不主动询问是否进入 Phase C（Phase D 本身就是为可编辑而生）
- ❌ 不跑 Phase A 的任何阶段（风格预览、规划文件、定稿图）
- ❌ 不生成图片型 PPTX（Phase D 直接输出可编辑版）

---

## Progressive Loading

按需读，不要一上来全读：

| 何时读 | 文件 |
|---|---|
| **★ 用户首次触发本 skill（agent 默默跑）** | `scripts/preflight.py`（自动装 pip 包 + 调 doctor；不需要问用户） |
| 单纯环境检查（不动用户系统） | `scripts/doctor.py`（不会自动装东西，纯报告） |
| 路由 / 决定本技能怎么跑（必读） | 本 `SKILL.md` |
| 跑 Phase A 总流程 | `references/phaseA/workflow.md` |
| Phase A intake / 对话框架 | `references/phaseA/conversation_framework.md` |
| Phase A 出风格预览、候选选图、review 页面 | `references/phaseA/preview-flow.md` |
| Phase A 三个壳子的图片/数据**注入**（必读） | `references/phaseA/shell-injection.md` |
| Phase A 风格提案卡 / V1-V8 内部 | `references/phaseA/style-system.md` |
| Stage 5.5 retouch（去水印 / IOPaint / ImageMagick 兜底） | `references/phaseA/retouch.md` |
| 写 `content_report.md` | `templates/content_report_reference.md` |
| 写 `slide_outline.md`（Stage 1.4 页大纲） | `templates/slide_outline_reference.md` |
| 写 `design_spec.md` | `templates/design_spec_reference.md` |
| 写 `slide_blueprint.md` | `templates/slide_blueprint_reference.md` |
| 写 `spec_lock.md` | `templates/spec_lock_reference.md` |
| **Phase C 总流程**（用户同意进 Phase C 时） | `references/phaseC/workflow.md` |
| **Phase D 总流程**（用户上传 PDF 时） | `references/phaseD/workflow.md` |
| Phase D extraction.json schema | `references/phaseD/extraction-schema.md` |
| 端到端运行手册 + 失败排错 | `references/pipeline.md` |

---

## 内置工作流壳子（assets/）

Phase A 必须使用以下 3 个本技能自带的 HTML 壳子，不要替换或自造同类页面：

- `assets/preview_shell/index.html` — 风格预览比较（Stage 2）
- `assets/candidate_picker_shell/index.html` — 多候选选图（Stage 4 多候选模式）
- `assets/review_shell/index.html` — 评审与返修（Stage 5）

Phase C 增加一个：

- `assets/editor_shell/index.html` — 文字编辑器（C4-C5）

> ⚠️ **四个壳子的 `index.html` 默认是空架子 / 示例数据**：preview_shell 的 9 张图是写死的 SVG 占位图；candidate / review / editor 都带示例数据。**真正使用之前必须显式注入真实数据**，否则用户打开页面看到的会是占位。
>
> **统一注入命令**（强制）：
>
> ```bash
> # Stage 2 风格预览
> python3 scripts/inject_shell_images.py preview \
>   --shell assets/preview_shell/index.html \
>   --data  preview_data.json \
>   --out   phaseA/previews/preview_filled.html
>
> # Stage 4 多候选选图
> python3 scripts/inject_shell_images.py candidate \
>   --shell assets/candidate_picker_shell/index.html \
>   --data  candidate_data.json \
>   --out   phaseA/candidates/picker_filled.html
>
> # Stage 5 评审
> python3 scripts/inject_shell_images.py review \
>   --shell assets/review_shell/index.html \
>   --data  review_data.json \
>   --out   phaseA/review/review_filled.html
>
> # Phase C 文字编辑器
> python3 scripts/inject_editor_deck.py \
>   --shell assets/editor_shell/index.html \
>   --deck  phaseC/deck.json \
>   --out   phaseC/editor.html
> ```
>
> - 各 data JSON 的 schema 见对应脚本顶部 docstring。
> - **打开时必须打开 `*_filled.html` / `editor.html`**，不要打开 `assets/.../index.html` 原模板。
> - 默认保留相对路径，配合 HTML 与背景图同目录使用；要打包分发再加 `--inline` 把图片 base64 嵌入 HTML，或加 `--file-url` 改成绝对 `file://`。
> - `editor.html` 默认应与 `phaseC/backgrounds/` 旁置，避免把背景内嵌成 7MB+ 的单文件。
> - `build_*.py` 三个脚本只是把壳子从内嵌 base64 还原成 `index.html`，**它们不注入真实数据**，不要把 build 和 inject 搞混。

---

## Phase A 规则（Conversation-first + Image-first）

**按 `references/phaseA/workflow.md` 跑完所有 Stage**。这里只列死规则。

### Working Principles
- 把用户当成甲方，本技能当作提出方向的设计侧。
- 不强迫用户填一堆设计参数；把自然语言意图翻译成设计决策。
- 默认展示 baseline judgment / proposal cards / 预览 / review 界面；规划文件原文按需出示。
- 标注 `user_provided` / `inferred` / `needs_confirmation`；不擅自编造未授权事实、数据、引用、机构结论。

### Hard Rules（Phase A 必守）
- **Preview-first**：最终风格确认必须基于真实生成的「首页 + 目录页 + 正文页」预览，不能用文字 mockup / ASCII 草图 / 占位壳代替。
- **Shells are mandatory**：必须使用 `assets/preview_shell/index.html`、`assets/candidate_picker_shell/index.html`、`assets/review_shell/index.html`。**打开前必须先用 `scripts/inject_shell_images.py` 把真实图注入到 `*_filled.html`，不要直接打开壳子原模板**。
- **Image-first 不退化**：定稿出图必须 image-first，不允许悄悄退化到"用 PPT shape 拼页面"或"代码画图"兜底。
- 用户要"加字 / 改字 / 补字"也仍然属于图像生成/编辑任务；不要默认用 PIL / Canvas / SVG / HTML 截图 / PPT 原生文本框去后期补字（除非用户明确要求这种 workaround）。
- **生成 ID 不入 prompt**：slide id / candidate code / 文件名 / 批次标签等可以出现在规划文件、文件名、映射表、review UI、对话里，但**不要拼进发给图像模型的 prompt 文本**。
- **不要在第一轮就导出最终 PPT**；只有 review 通过后才导出。
- **`slide_blueprint.md` 不能在风格反演确认之前写**。
- **生成前必须问**：单图直出 / 多候选 picker。
- **Phase A 交付后必须主动询问 Phase C**（见上面"主动询问"段）。

### 内置工作流的 5+ 个 Stage（极简版索引）
1. **Stage 1** — Intake + baseline judgment → `需求确认`
2. **Stage 1.25** — 风格前内容研究 → `content_report.md`（除非用户已给完整稿）
3. **Stage 1.4 ★** — 页大纲确认门禁：写 `slide_outline.md`，逐页列出将要出现在 PPT 上的可见文字 + claim_status，贴摘要给用户，等用户确认后才进 Stage 1.5
4. **Stage 1.5** — 风格边界对齐（3 个短问题）
5. **Stage 2** — 风格提案与真实预览（首页 / 目录页 / 正文页），打开 `preview_shell`；可选 **Stage 2.5** refinement；必跑 **Stage 2.75** 风格反演确认 → `风格确认`
6. **Stage 3** — 顺序写 `design_spec.md` → `slide_blueprint.md` → `spec_lock.md` → `生成前确认`
7. **Stage 4** — 单图直出 / 多候选 picker（若多候选先打开 `candidate_picker_shell`）出齐全页定稿图
8. **Stage 5** — 打开 `review_shell` 做评审；不通过则用 `scripts/render_review_markup.py` 渲染标注图 + 文本反馈再喂回去返修
9. **Stage 5.5** — ★ **图像级 retouch（用户驱动，可选）**：详见 `references/phaseA/retouch.md`
10. **交付 + 主动询问 Phase C** — 把图片型 PPTX + 定稿图 + 规划文档交给用户，**主动问**是否要可编辑文字版

---

## Stage 5.5 Retouch（默认提供，按需使用）

Phase A 出图被叠加了工具水印（典型如 Qoder 的 "Qoder AI生成"）、或某页角落有想擦掉的小瑕疵时，**默认提供以下两个工具**：

```bash
# 工具 1：批量去固定位置的角落水印（最省事，适合工具水印）
python3 scripts/remove_corner_watermark.py phaseA/slides/ -o phaseA/slides_clean/ --batch

# 工具 2：IOPaint 手工 inpaint（任意位置 / 复杂背景；效果最强）
# 首次自动调 setup_iopaint.py 装 IOPaint + LaMa（约 5–10 分钟、~3GB）
python3 scripts/launch_iopaint.py --slides-dir phaseA/slides
```

**关键性质**（agent 必须遵守）：
- **绝不在用户没要求时强制启动 IOPaint**。Phase A 走完先告诉用户图在哪、PPTX 在哪、有没有发现水印 / 瑕疵，再问要不要进 Stage 5.5。
- **首次启动 IOPaint 会等待 5–10 分钟装环境 + 下模型**，这点必须事先告诉用户。
- **安装完全幂等**：标记文件在 `~/.cache/ppt-craft-editable/.lama-installed`，二次启动秒开。
- **装失败不阻塞 Phase A 主路径**：launch_iopaint.py / setup_iopaint.py 都内置失败兜底（重试 / `remove_corner_watermark.py` / ImageMagick 矩形遮罩）。
- **retouch 不替代 review**：实质内容 / 视觉改动应回 Stage 5 重出图；Stage 5.5 只解决"图整体没问题，那一小块要擦掉"。
- **IOPaint 在 Phase C 里也能用**——擦字稿不合规时局部涂抹擦干净比让 imagegen 重出整页省钱：`python3 scripts/launch_iopaint.py --slides-dir phaseC/backgrounds`。

完整工具说明、操作流程、何时该用 / 不该用，详见 [`references/phaseA/retouch.md`](references/phaseA/retouch.md)。

---

## Phase C 规则（可编辑文字路径）

**仅当用户在 Phase A 交付后的"主动询问"中同意进入时才执行**。完整流程在 `references/phaseC/workflow.md`，这里只列死规则。

### Hard Rules（Phase C 必守）
- **沿用 Phase A 的 Stage 1-3**：需求 / 内容 / 风格 / 规划文件全部走 Phase A 已经做好的成果，不要重做。
- **以 Phase A 定稿作视觉参考**：Phase C 的用户承诺是参考 Phase A 结果重新生成无字背景，再叠加可编辑文字；不要把对外描述写成“从 A 图里精确抠掉文字”。背景可能与 Phase A 定稿有细微差异。
- **优先直编 Phase A 成品图**：内部执行上仍默认先把 Phase A 定稿图作为 imagegen edit target 去字；如果去字后不干净或留白不合规，再回退到重生成背景 + 擦字稿。对用户说明时强调“参考定稿重新生成无字背景”，避免误解为像素级抠字。
- **回退时再走两稿**：只有在直编失败时，才先出"完整稿"再以完整稿为 edit target 出"擦字稿"。不要把两稿逻辑当成默认必走。
- **edit target 先看 Phase A 图**：默认先 `view_image` Phase A 定稿图，再调 imagegen，prompt 写"以刚刚显示的这张图片作为唯一编辑目标"。不要只写本地路径。
- **detect_reserved_zones 不可跳**：每页擦字稿必须用 `scripts/detect_reserved_zones.py` 校验。不合规 → 重出 / IOPaint 局部擦。
- **统一编辑器门禁不可跳**：deck.json 写好后，必须先注入编辑器打开给用户确认，再等用户把导出包贴回才能渲染 PPTX。不能跳过编辑器直接渲染。编辑器同时支持文字编辑和背景框选反馈，用户做了背景反馈 → agent 先修背景 → 重出编辑器，不能直接渲染。
- **不要再插入独立背景审计门禁**：背景图反馈统一在 C5 编辑器的 `🖊 背景反馈` 模式里完成；本 skill 不再提供独立背景审计壳子。
- **deck.json 是单一真相源**：编辑器 / 渲染器都消费 deck.json。**不要在 PPTX 渲染后再单独改 PPTX**——回到 deck.json 改，重出 PPTX。
- **渲染前必须校验 deck.json**：`json_to_pptx.py` 会自动调用 `scripts/validate_deck_json.py`；若缺 `background`、坐标越界、颜色格式错误或背景路径不可访问，必须先修 deck.json，不要猜补。
- **字体限定 SAFE_FONT_SET**：见 `scripts/json_to_pptx.py` 顶部。不在集合里会有警告，跨平台可能掉 fallback。可用：PingFang SC / Microsoft YaHei / Hiragino Sans GB / Arial / Helvetica 等系统字体。
- **坐标用 fraction**：所有 x/y/w/h 都是 0-1，跟 HTML 编辑器和 PPTX 渲染器同语义。
- **字号用 pt**：直接写 `font_size_pt`，不要算像素。
- **背景引用可为相对路径 / 绝对路径 / `file://` / `data:`**：编辑器导出的 deck 可能带这些形式，`json_to_pptx.py` 必须直接兼容。
- **编辑器默认走旁置文件模式**：`inject_editor_deck.py` 默认保留相对路径，`editor.html` 与 `phaseC/backgrounds/` 放同一目录；只有明确需要时才用 `--inline`。
- **背景图固化、文字外挂**：背景一旦生成就不再改（除非重出该页）；文字始终是外挂层。
- **编辑器是单文件 HTML**：关闭浏览器不会自动保存。改完一定要先点"导出 deck.json"再关。
- **Phase C 完成 = 终态**：拿到可编辑 PPTX 后不要再追问 / 折返到其他路径。

### Phase C 流程极简版（C1-C6）
1. **C1** 以 Phase A 定稿作视觉参考生成无字背景；内部先尝试直编，不干净再回退到完整稿 → imagegen 擦字稿
2. **C2** `scripts/detect_reserved_zones.py` 校验预留区
3. **C3** 写 `phaseC/deck.json`（每页 background + text_boxes 初稿）
4. **C4** `scripts/inject_editor_deck.py` 注入编辑器，生成 `editor.html`
5. **C5 ★ 必跑** 打开 editor.html，用户在统一编辑器里完成：
   - 文字编辑模式：改字 / 拖框 / 调样式
   - 背景反馈模式（按 `🖊 背景反馈` 切换）：矩形/画笔/注释点标注背景要改的位置
   - 导出完整指令包贴回对话框
   - 若有 BG REVIEW 段 → agent 修背景 → 重出 editor.html → 用户再确认
   - 无 BG REVIEW 段 → 进 C6 渲染
6. **C6** `scripts/json_to_pptx.py` 渲染 → 可编辑 PPTX

---

## 关键命令（脚本都在 `scripts/`）

```bash
# ─── Stage 0：用户首次触发，agent 默默跑（无需问用户）──────

python3 scripts/preflight.py
# 自动安装缺失的 4 个 pip 包（首次 2-5 分钟），装完调 doctor
# 退出码 0 = 可继续；退出码 1 = 有不可自动修的项目，让用户处理

# 单纯想看环境状态（不动用户系统）
python3 scripts/doctor.py

# ─── 基础依赖（preflight 失败时手动装的兜底方案）─────────
pip3 install python-pptx pillow numpy opencv-python

# ─── Phase A ───────────────────────────────────────────────

# 把真实图注入工作流壳子（每个 Stage 出图后必跑）
python3 scripts/inject_shell_images.py preview   --shell assets/preview_shell/index.html           --data preview_data.json   --out phaseA/previews/preview_filled.html
python3 scripts/inject_shell_images.py candidate --shell assets/candidate_picker_shell/index.html  --data candidate_data.json --out phaseA/candidates/picker_filled.html
python3 scripts/inject_shell_images.py review    --shell assets/review_shell/index.html            --data review_data.json    --out phaseA/review/review_filled.html

# review markup 渲染（用户在 review_shell 给的坐标标注 → 标注图）
python3 scripts/render_review_markup.py <review.json> --out-dir <dir>

# ─── Stage 5.5 Retouch（用户驱动，可选）────────────────────

# 批量去角落水印
python3 scripts/remove_corner_watermark.py phaseA/slides/ -o phaseA/slides_clean/ --batch

# IOPaint：首次自动装环境 + 下 LaMa（5–10 分钟、~3GB），之后秒开
python3 scripts/launch_iopaint.py --slides-dir phaseA/slides
# Phase C 也可以用（擦字稿不合规时局部涂抹）
python3 scripts/launch_iopaint.py --slides-dir phaseC/backgrounds

# 单独管理 IOPaint
python3 scripts/setup_iopaint.py --check-only     # 检查
python3 scripts/setup_iopaint.py                  # 装
python3 scripts/setup_iopaint.py --reinstall      # 强制重装

# ─── Phase C（用户同意可编辑后才跑）─────────────────────────

# C2 校验擦字稿的预留区是否真的留白
python3 scripts/detect_reserved_zones.py phaseC/backgrounds/01.png phaseC/01-zones.json --report phaseC/01-zones.report.json

# C4 把 deck.json 注入编辑器壳子（C5 用户在里面调文字 + 提背景反馈）
python3 scripts/inject_editor_deck.py \
    --shell assets/editor_shell/index.html \
    --deck  phaseC/deck.json \
    --out   phaseC/editor.html

# C6 deck.json → 可编辑 PPTX（+ 可选 PIL 近似预览图）
python3 scripts/validate_deck_json.py phaseC/deck.json
python3 scripts/json_to_pptx.py phaseC/deck.json -o phaseC/<topic>.pptx --preview-dir phaseC/preview
```

---

## 输出目录结构（建议）

```
<topic-slug>/
├── content_report.md                    # 仅当 Stage 1.25 生成
├── slide_outline.md                     # Stage 1.4 页大纲确认门禁（必有）
├── design_spec.md
├── slide_blueprint.md
├── spec_lock.md
│
├── phaseA/                              # Phase A 产物（默认交付）
│   ├── previews/                        # 各阶段风格预览（保留备查）
│   ├── candidates/                      # 多候选模式时使用
│   ├── slides/NN-*.png                  # 评审通过的终图
│   ├── slides_clean/                    # Stage 5.5 retouch 后的图（可选）
│   ├── review/                          # 评审产物
│   ├── imagegen-manifest.json
│   └── <topic>-image-deck.pptx          # 图片型 PPTX
│
└── phaseC/                              # Phase C 产物（用户同意才出现）
    ├── backgrounds/
    │   ├── NN-full.png                  # 第 1 稿（完整稿，备查）
    │   └── NN.png                       # 第 2 稿（擦字稿，实际背景）
    ├── NN-zones.json                    # 每页预留区声明
    ├── NN-zones.report.json             # 校验报告
    ├── deck.json                        # 单一真相源
    ├── editor.html                      # 注入后的编辑器
    ├── preview/slide_NN.png             # PIL 近似预览图（可选）
    └── <topic>-editable.pptx            # 文字可编辑 PPTX
```

外置缓存（IOPaint 用，不在本目录里）：

```
~/.cache/ppt-craft-editable/
├── venv/                                # IOPaint 专属 venv
├── .lama-installed                      # 安装标记 + 元数据
└── setup.log                            # 安装日志
```

---

## 安装 / 依赖

把整个 `ppt-craft-editable/` 复制到 agent 的 skills 目录即可。**完全自包含**，不依赖其他外部 skill。

```bash
# Codex
cp -R ppt-craft-editable "${CODEX_HOME:-$HOME/.codex}/skills/ppt-craft-editable"
```

Python 依赖（基础）：

```bash
pip3 install python-pptx pillow numpy opencv-python
```

Stage 5.5 IOPaint 是**用户首次触发时自动安装**：

- 装到专属 venv `~/.cache/ppt-craft-editable/venv/`，不污染系统
- 自动 + 预下 LaMa 模型
- 国内默认走 hf-mirror 镜像
- 首次约 5–10 分钟、~3GB 磁盘；之后秒启
- 装失败有明确兜底（remove_corner_watermark.py / ImageMagick）

图像生成路径：依赖运行环境内可用的 imagegen 通道（Codex 用内置 `imagegen` / GPT Image 2）。如果运行时不可用，必须停在该 Stage 并向用户说明阻塞原因，不允许用 PIL/SVG/Canvas/PPT shapes 兜底。

---

## 致谢

本技能起源于：
- `ppt-image-first`（Phase A 工作流、references、templates、assets 部分原型） — Linux.do 社区

编排层、Stage 5.5 retouch 工具链、IOPaint 自动安装与启动器、Phase C 全套（双轨生成 + detect_reserved_zones + HTML 编辑器 + json_to_pptx 渲染器）—— 本 skill 自有。商用时请同时标明上述来源。
