# Phase C — 背景图 + 外挂可编辑文字

> **核心思想**：对用户来说，Phase C 是以 Phase A 定稿图为视觉参考，重新生成不含可编辑文字的背景层，再把文字作为**外挂图层**用 HTML 编辑器实时调整，最终按已知坐标 + 已知样式渲染到 PPTX。内部可以先尝试直接编辑 Phase A 成品图；只有当直接编辑不干净时，才回退到"重新生成背景图 + 擦字稿"。不要把对外描述写成从 Phase A 图片里像素级抠掉文字，背景可能与 Phase A 定稿有细微差异。
>
> 这条路径的特点：
> - 文字**始终是真 TextBox**，PowerPoint / Keynote 里直接可改
> - 不需要任何 OCR / bbox 反推 / 字号反推
> - 不需要"贴框文字漂移"的多道 QA 闸门
> - 默认先直编 Phase A 成品图，成功时每页成本更低；复杂页回退到重生成背景时，才接近每页 2 张 imagegen

---

## 何时用 Phase C

| 场景 | 路径 |
|---|---|
| 只要好看视觉稿，做完汇报就结束 | **Phase A**（默认） |
| Phase A 完成后用户在主动询问中说要可编辑 | **Phase C** |
| 用户从一开始就明确说只做可编辑、只跑 Phase C、跳过图片版、直接给文字可编辑 PPTX | **Phase C-only**，不跑 Phase A |
| 用户只说后期可能要改字，但没有要求跳过图片版 | 默认仍先跑 **Phase A**，交付后再主动询问是否追加 Phase C |

---

## 总流程

```
Phase A 后追加 Phase C：沿用 Phase A Stage 1 / 1.25 / 1.5 / 2 / 2.5 / 2.75 / 3
Phase C-only：只补最小输入，建立 design_spec / slide_blueprint / deck 初稿，并先过 C0 轻量预览门禁
                       │
                       ▼
            ┌─ Phase C 替代 Phase A Stage 4-5，或作为 Phase C-only 主路径 ─┐
            │                                  │
            ▼                                  │
    Step C0  Phase C-only 先出 1-2 页预览并确认       │
                       │                       │
                       ▼                       │
    Step C1  有 Phase A 成品图时先直编：             │
             (1) 以 Phase A 定稿图作为 edit target  │
                 内部优先尝试生成无字留白背景        │
             (2) 若没有 Phase A 图或直编不干净       │
                 → 重生成背景再擦字                 │
                       │                       │
                       ▼                       │
   Step C2  detect_reserved_zones.py 校验：    │
            擦字稿的预留区是否真的留白了        │
            → 不合规：重出 / IOPaint 局部擦    │
                       │                       │
                       ▼                       │
   Step C3  写 deck.json：                     │
            每页 background + 一组 text_boxes  │
            (text_boxes 内容来自 content_report │
             和 slide_blueprint)                │
                       │                       │
                       ▼                       │
   Step C4  inject_editor_deck.py 注入：       │
            assets/editor_shell/index.html     │
            + deck.json → editor.html          │
            → 浏览器打开                        │
                       │                       │
                       ▼                       │
   Step C5 ★ 统一编辑 + 背景反馈门禁（必跑）：│
            用户在同一个编辑器里完成：          │
            ┌── 文字编辑模式 ─────────┐         │
            │ 改文字 / 拖框 / 调样式  │         │
            └─────────────────────────┘         │
            ┌── 背景反馈模式（按需）──┐         │
            │ 矩形 / 画笔 / 注释点   │         │
            │ 写 requested_action +   │         │
            │ page_comment            │         │
            └─────────────────────────┘         │
            → 点 "导出 / 继续生成"              │
              → 拿到 DECK JSON [+ BG REVIEW]    │
            → 有 BG REVIEW                      │
              ⇒ agent 修 phaseC/backgrounds     │
              ⇒ 重出 editor.html → 用户再确认   │
            → 只有 DECK JSON                    │
              ⇒ 进 C6 渲染 PPTX                 │
                       │                       │
                       ▼                       │
   Step C6  json_to_pptx.py：                  │
            deck.json → <topic>.pptx           │
            可选 --preview-dir 出每页对照图     │
            └──────────────────────────────────┘
                       │
                       ▼
            交付：<topic>.pptx + deck.json + backgrounds/
```

---

## Step C0 - Phase C-only 轻量预览门禁

Phase C-only 没有 Phase A 的真实预览图作为视觉证据，所以必须先建立一个轻量视觉确认点。这个门禁只用于确认“重新生成的无字背景 + 文字可编辑”的视觉基准，不生成图片型 PPTX，也不进入 Phase A。

### 输入
- 主题、受众、用途、页数
- 已有材料或内容提纲
- 明暗偏好、品牌/学校/产品锚点、参考图（如有）

### 操作
1. 先生成或整理 `content_report.md`，避免背景和文字层变成空泛模板。
2. 按 `templates/slide_outline_reference.md` 写 `slide_outline.md`，并同步写一份同内容的 `ppt大纲.md`；用户确认页大纲后才继续。
3. 写 `design_spec.md`，明确明暗、色彩角色、字体气质、背景材质、装饰语言、留白规则和页面类型语法。
4. 写 `slide_blueprint.md`，标明每页哪些内容进背景、哪些内容必须保留为 TextBox。
5. 写 `spec_lock.md`，锁死“背景不烤入可编辑文字”的规则。
6. 选 1-2 页代表页（通常封面 + 信息量最高的正文页），按已确认的设计方向重新生成无可编辑文字的背景图。若有 Phase A 结果或参考图，只把它作为视觉参考，不承诺像素级抠字或完全一致。
7. 为这 1-2 页写临时 C0 deck，例如 `phaseC/c0-source-deck.json`。这个 deck 必须使用正式 Phase C schema：`slides[].background` 指向无文字背景，`slides[].text_boxes` 放标题、正文、署名等可编辑文字。
8. 运行 C0 预览构建命令，固定落地可检查产物：

   ```bash
   python3 scripts/build_c0_preview.py \
       --deck phaseC/c0-source-deck.json \
       --shell assets/editor_shell/index.html \
       --out-dir phaseC/c0
   ```

   必须生成：
   - `phaseC/c0/deck.json` — 仅含 1-2 页代表页的临时 deck
   - `phaseC/c0/editor.html` — 用户要打开的无字背景 + 可编辑文字叠放预览
   - `phaseC/c0/preview/slide_*.png` — 同一 deck 渲染出的静态叠字对照图

9. 主动尝试打开 `phaseC/c0/editor.html`。如果环境打不开浏览器，给用户绝对路径，并明确说明要打开此 HTML 查看“重新生成的无字背景 + 可编辑文字框”；PNG 只作静态对照。
10. 停在 `Phase C-only 视觉确认`，用户确认后再批量生成全套背景。

### 通过标准
- 用户确认视觉方向、信息密度和文字可读性可以继续。
- 预览页的可编辑文字没有被烤进背景。
- `slide_outline.md` 和 `ppt大纲.md` 已存在且内容一致；用户已确认页大纲。
- `phaseC/c0/deck.json`、`phaseC/c0/editor.html`、`phaseC/c0/preview/slide_*.png` 已存在。缺任意一类文件时，C0 确认无效，不能进入批量生成。
- C0 deck 通过 `scripts/validate_deck_json.py` 校验，并且与后续正式 `phaseC/deck.json` 使用同一 `text_boxes` schema。
- 背景留白区能通过 `detect_reserved_zones.py` 或人工检查。
- 若用户要求调整风格，只改 `design_spec.md` / `spec_lock.md` 后重出预览页，不直接批量生成。

---

## Step C1 - 参考 Phase A 生成无字背景；Phase C-only 直接重生成背景

对外说明时必须讲清楚：进入 Phase C 后，背景层是以 Phase A 定稿图为视觉参考重新生成的无字背景，并叠加可编辑文字框；这不是把 Phase A 图片中的文字逐像素抠掉，生成结果可能与 Phase A 定稿有细微差异。下面的“直编优先”是内部执行策略，不是对用户承诺的像素级去字方式。

### 为什么先直编 Phase A 图

Phase A 的图已经是最终视觉稿，直接拿它做 edit target 有两个好处：
- 视觉连续性更强，不会像重新做了一版
- 少一次重画，成本更低，速度更快

但它也有硬问题：
- 文字已经和背景压成一张图，复杂底纹上容易擦坏装饰
- 某些页直接去字后不一定能得到足够干净的留白区

所以 Phase C 改成混合策略：
- 先直编 Phase A 成品图
- 不干净再回退到重生成背景 + 擦字稿
- 最后仍然以 deck.json 和真文本框为准

### 操作

**优先路径：直接编辑 Phase A 成品图**

仅当当前任务是 `Phase A → Phase C` 且已有 Phase A 定稿图时使用这条路径。若用户一开始明确要求 Phase C-only，不要为了直编而补跑 Phase A。

把 Phase A 的定稿图直接作为 edit target：

```
[先 view_image Phase A 的定稿图]

以刚刚显示的这张图片作为唯一编辑目标 / edit target。

请：
1. 保留所有装饰元素、图表、底纹和非正文装饰字
2. 擦除所有可编辑文字（标题、副标、正文、说明、章节号等普通字体文字）
3. 被擦除区域用与周围背景一致的纯色或渐变填充
4. 不要新增任何文字
5. 不要改变构图、配色、装饰元素的位置和大小
```

**Phase C-only / 回退路径：重生成背景 + 擦字稿**

如果没有 Phase A 成品图，或 Phase A 成品图直接编辑后仍有残影、留白区不合规，再进入：

1. 基于 `design_spec.md` / `slide_blueprint.md` 重生成一张完整稿
2. 以完整稿为 edit target 生成擦字稿
3. 不合规则重出或 IOPaint 局部擦

回退到这里时，再按原来的两稿逻辑继续。

### 落盘

```
phaseC/
├── backgrounds/
│   ├── 01-full.png       # 回退时的完整稿（视觉参考）
│   ├── 01.png            # 回退时的擦字稿（实际用作背景）
│   ├── 02-full.png
│   ├── 02.png
│   └── ...
```

---

## Step C2 — 校验预留区是否留白

为每页写一个 zones.json，对应"应当被擦干净"的矩形：

```json
{
  "zones": [
    {
      "id": "title",
      "x": 0.08, "y": 0.15, "w": 0.55, "h": 0.18,
      "expected_color": "#f5f1ea",
      "tolerance": 25
    },
    {
      "id": "subtitle",
      "x": 0.08, "y": 0.36, "w": 0.55, "h": 0.10
    }
  ]
}
```

跑：

```bash
python3 scripts/detect_reserved_zones.py \
    phaseC/backgrounds/01.png \
    phaseC/01-zones.json \
    --report phaseC/01-zones.report.json
```

输出会逐个 zone 打 ✅/❌，不合规的指明原因（颜色方差太高 / 边缘密度太高 / 平均色偏离）。

**不合规时怎么办**：
- 回 Step C1 重出第 2 稿（调 prompt 强调"必须擦干净 X 区域"）
- 局部用 IOPaint 涂抹擦干净（`launch_iopaint.py --slides-dir phaseC/backgrounds`）
- 实在改不动 → 把该 zone 的位置移到合规区域，调整 deck.json

阈值预设：
- 默认：`std≤12, edge_ratio≤0.02`
- `--strict`：`std≤6, edge_ratio≤0.008`（要求几乎纯净的背景）
- `--loose`：`std≤20, edge_ratio≤0.05`（背景本来就有渐变 / 纹理时）

---

## 背景反馈入口

背景图观感确认和框选反馈统一收敛到 C5 编辑器的 `🖊 背景反馈` 模式。主流程不要再插入独立的 C2.5 / C3.5 背景审计步骤，避免用户先审一遍背景、再在编辑器里审一遍背景。

本 skill 不再维护独立背景审计壳子；即使用户只想反馈背景，也打开 C5 的 `phaseC/editor.html`，切到背景反馈模式完成标注。

---

## Step C3 — 写 deck.json

完整 schema 见 `scripts/json_to_pptx.py` 顶部 docstring。最小例子：

```json
{
  "deck": {
    "ratio": "16:9",
    "default_font": "PingFang SC",
    "default_font_size_pt": 18,
    "default_color": "#1a1a1a"
  },
  "slides": [
    {
      "id": "01-cover",
      "background": "backgrounds/01.png",
      "text_boxes": [
        {
          "id": "tb-title",
          "text": "演示稿主标题",
          "x": 0.08, "y": 0.18, "w": 0.55, "h": 0.18,
          "font_size_pt": 56,
          "bold": true,
          "color": "#1a1610"
        },
        {
          "id": "tb-subtitle",
          "text": "副标题或简短说明",
          "x": 0.08, "y": 0.38, "w": 0.55, "h": 0.08,
          "font_size_pt": 22,
          "color": "#5b5247"
        }
      ]
    }
  ]
}
```

**关键约束**：
- 所有 `x / y / w / h` 都是 **fraction (0-1)**，跟 PPTX 渲染器、HTML 编辑器同语义。
- `font_family` 必须从 SAFE_FONT_SET 里选（见 `json_to_pptx.py` 顶部），不在集合里会有警告。
- 默认值放 `deck.default_*`，每页/每框可单独覆盖。
- 背景路径相对 deck.json 解析；绝对路径也支持。

---

## Step C4 — 把 deck.json 注入编辑器

```bash
python3 scripts/inject_editor_deck.py \
    --shell assets/editor_shell/index.html \
    --deck  phaseC/deck.json \
    --out   phaseC/editor.html

# 用浏览器打开
open phaseC/editor.html              # macOS
xdg-open phaseC/editor.html          # Linux
```

模式：
- 默认：背景图重写成 `file://` 绝对路径（适合本地）
- `--inline`：背景图 base64 嵌入 HTML（适合邮件 / 离线分发，文件会大）
- `--keep-paths`：保留原路径（适合背景已经是 HTTPS URL）

> 注意：`editor.html` 导出的最终 deck 里，`background` 可能是 `file://...` 或 `data:...`。
> `scripts/json_to_pptx.py` 必须直接支持这两种形式，不能只认裸本地路径。

---

## Step C5 — 统一编辑 + 背景反馈门禁（必跑）

> ★ **硬门禁**：editor.html 是 Phase C 的最终交付前确认窗口。用户必须**亲自打开**并点击 `📋 复制整段` 把内容贴回对话框，agent 才能进 C6。在用户给出导出包之前，不要直接渲染 PPTX。

### 界面布局

```
┌──────── topbar (🖊背景反馈 / +文字框 / 导入 / 导出 / ?) ────────┐
├──────┬─────────────────────────────────────┬─────────────────┤
│ 页面 │   画布 (1: 背景图)                  │ 属性面板         │
│ 列表 │   + 文字框（可选/可拖/可改）        │ 文字模式 → 字体  │
│ (有🖊│   + 标注画布（背景反馈模式时激活）  │   字号/颜色/对齐 │
│ 标记 │   + 注释点                          │ 反馈模式 → 动作  │
│ 反馈)│                                     │   + 意见 + 注释  │
└──────┴─────────────────────────────────────┴─────────────────┘
```

### 两种模式

**文字编辑模式（默认）**
- **单击文字框** → 选中（出现 resize handle）
- **拖动** → 改位置（fraction 实时更新）
- **拖 resize handle** → 改尺寸
- **双击** → 进入文字编辑（contenteditable），Esc 退出
- **Delete**（非编辑态）→ 删除选中文字框；**Backspace** → 进入编辑并删最后一个字
- **+ 添加文字框** → 画布中央插入新框
- **属性面板** → 字体 / 字号 / 颜色 / 对齐 / 行距

**背景反馈模式**（点 topbar 的 `🖊 背景反馈` 按钮切换）
- 文字框变成半透明背景层，不能编辑（避免误触）
- **矩形框选 / 画笔 / 注释点** → 标注背景图要改的位置
- **撤销 / 清空本页** → 工具栏右侧
- **属性面板** → 选 `requested_action`（局部修补 / 重生成 / 调留白区 / 本页通过）+ 写 `page_comment`
- 左侧页面列表上有标注内容的页会出现 🖊 角标

### 导出（核心动作）

点右上角 **`导出 / 继续生成`**：

- 没做背景反馈 → 弹窗里只有 `===DECK JSON===` 段，agent 直接渲染 PPTX
- 做了背景反馈 → 弹窗里多一段 `===PHASEC BACKGROUND REVIEW===`，agent 会先修背景再重出 editor.html，**不会**直接渲染 PPTX

无论哪种情况，都点 `📋 复制整段（推荐）`，把完整内容**整段**粘贴回对话框。

### 通过标准

- 用户把导出包贴回对话框（含 sentinel 标记）
- agent 解析后：
  - 只有 DECK JSON → 进 C6 渲染
  - 还有 BG REVIEW → 修背景 + 重出 editor.html，让用户再确认一次

### 反模式

- ❌ agent 没拿到用户导出包就直接 `json_to_pptx.py` 渲染 —— 跳过门禁
- ❌ agent 看到 BG REVIEW 段还硬着头皮渲染 PPTX —— 用户的修背景意见会被丢
- ❌ 用户只复制了中间 JSON 而漏了 sentinel —— agent 应当救场：仍当作 DECK 保存渲染，但提醒下次完整复制

**重要**：编辑器是单文件 HTML，关闭浏览器不会自动保存——**改完一定要先点导出**。标注数据另存于浏览器 localStorage，刷新不丢，但跨设备/跨浏览器不可见。

---

## Step C6 — 渲染 PPTX

```bash
# 拿编辑器导出的 deck.json
python3 scripts/validate_deck_json.py phaseC/deck.json
python3 scripts/json_to_pptx.py phaseC/deck.json -o phaseC/<topic>.pptx

# 同时出每页预览图（PIL 渲染的近似图，方便和编辑器对照）
python3 scripts/json_to_pptx.py phaseC/deck.json \
    -o phaseC/<topic>.pptx \
    --preview-dir phaseC/preview
```

`json_to_pptx.py` 的实现要点：
- 渲染前自动调用 `validate_deck_json.py`，缺字段、坐标越界、背景不可访问或颜色格式错误会直接阻塞
- 每页 = 空白版式 + 背景 Picture (占满整页) + 若干 TextBox
- TextBox 的 `font.name` / `font.size` / `font.color` / `bold` / `italic` 严格按 deck.json 写
- 字体不在 SAFE_FONT_SET 会 stderr 警告（仍写入，跨平台可能掉 fallback）
- 颜色支持 `#RRGGBB` / `#RGB`
- 对齐：`left` / `center` / `right`，垂直对齐：`top` / `middle` / `bottom`
- 背景支持相对路径、绝对路径、`file://...`、`data:...`

预览图是 PIL 直接画的（不是真从 PPTX 导出），用于和编辑器视觉对照。要 100% 精确的预览，请用 LibreOffice/Keynote/PowerPoint 转 PNG。

---

## Phase A 与 Phase C 对比

| 模块 | Phase A | Phase C |
|---|---|---|
| Stage 1-3 (对话/内容/规划) | ✅ 跑 | ✅ 复用 Phase A 已生成的 |
| Stage 4-5 出图/评审 | ✅ 整页直出 | **替换**为分层生成 + HTML 编辑器 |
| Stage 5.5 retouch | ✅ 用户驱动 | 也可以用（擦字稿不合规时局部擦） |
| PPTX 渲染 | python-pptx 简单 picture（背景占满整页） | `json_to_pptx.py`（背景 Picture + 文字 TextBox） |
| 用户可编辑性 | 仅整图替换 | **文字真可编辑，背景固化** |
| 每页 imagegen 成本 | 1 张 | 2 张（完整稿 + 擦字稿） |
| QA 闸门数量 | 1 (review) | 2 (detect_reserved_zones + 编辑器统一确认) |

---

## 失败排错

| 现象 | 原因 | 处理 |
|---|---|---|
| 第 2 稿 imagegen 没真擦掉文字 | prompt 太弱 / view_image 没指对图 | 重出，prompt 加强"擦除所有可编辑文字"；确认 view_image 指当前页第 1 稿 |
| 第 2 稿擦掉过头，连装饰也没了 | prompt 没强调"保留装饰元素" | 重出，prompt 列出要保留的元素清单 |
| detect_reserved_zones 不合规 | 留白区颜色不一致 / 仍有残留 | IOPaint 局部擦 → 再校验 |
| 文字在编辑器里好看但 PPTX 里偏 | 字体不在 SAFE_FONT_SET，跨平台 fallback | 改用安全字体集里的同类字体 |
| PPTX 里文字溢出框 | 字号太大 / 框太小 | 编辑器里调；或开 `auto_fit: true` |
| 行距异常 | line_spacing 单位用错（应该是倍数，1.0~3.0） | 改回倍数（默认 1.2） |
| 多语言混排字体掉色 | 不同 run 字体覆盖不全 | 每行明确指定 font_family；或全局用 PingFang/Microsoft YaHei（CJK 强） |
| 背景图在编辑器里不显示 | 浏览器跨目录禁访问 | 用 `--inline` 重新注入，或保证 file:// 路径正确 |
| 渲染前校验失败 | deck.json 缺字段 / 坐标越界 / 背景路径不可访问 / 颜色格式错误 | 按 `[error]` 指向的字段修 deck.json，再重跑 C6 |
| `json_to_pptx.py` 读不出 editor 导出的 deck | 背景是 `file://` / `data:`，旧版渲染器只认本地路径 | 升级到本版渲染器，或先把背景改回相对本地路径 |

---

## 极简清单（agent checklist）

```
- [ ] 判断路径：Phase A 后追加 Phase C，或用户明确要求 Phase C-only
- [ ] Phase A 后追加时，复用 Phase A Stage 1 / 1.25 / 1.5 / 2 / 2.5 / 2.75 / 3 产物
- [ ] Phase C-only 时，只补最小输入，不跑 Phase A 的预览、review、retouch
- [ ] Phase C-only 批量生成前，先过 C0：1-2 页背景 + 可编辑文字预览得到用户确认
- [ ] 对每页：
      - [ ] 出第 1 稿（完整稿）→ phaseC/backgrounds/NN-full.png
      - [ ] view_image 第 1 稿 → 出第 2 稿（擦字稿）→ phaseC/backgrounds/NN.png
      - [ ] 写 phaseC/NN-zones.json，跑 detect_reserved_zones.py 校验
      - [ ] 不合规则重出或 IOPaint 局部擦
- [ ] 写 phaseC/deck.json（背景路径 + text_boxes 初始内容来自 slide_blueprint）
- [ ] 跑 inject_editor_deck.py → 打开 editor.html 让用户调文字 / 提背景反馈
- [ ] ★ 必拿到用户的导出包（含 ===DECK JSON=== 标记），不要自己直接渲染
      - [ ] 导出包**只有 DECK JSON** → 保存 deck.json + 跑 json_to_pptx.py 渲染
      - [ ] 导出包**还有 PHASEC BACKGROUND REVIEW** → 先按反馈修 phaseC/backgrounds，
            再重出 editor.html 让用户再确认，不要直接渲染
- [ ] 跑 validate_deck_json.py，确认 deck.json 没有 error
- [ ] 跑 json_to_pptx.py → 交付 .pptx + 每页对照预览图
```
