# Phase D - PDF PPT 编辑分支

## 定位

把用户上传的 PDF 幻灯片转换成**内容可编辑、背景可保真或可重建**的 PPTX。

Phase D 是独立入口，最终接入 Phase C 的编辑器和渲染管道。

---

## 两类 PDF 页面

### D1. 可抽取文本页 (extractable_text)

**特征**：PDF 中存在真实文本对象（从 PPT、Keynote、LaTeX beamer 等导出）

**处理路径**：
- 用 PyMuPDF (fitz) 直接提取文字、坐标、字体、颜色
- 渲染整页为 PNG
- 根据文本框位置生成 mask，用 IOPaint 擦字得到背景
- 输出 `extraction.json`

**优点**：高保真，文本位置精确，背景像素级保留

### D2. 图片型页 (image_only)

**特征**：页面本质是一整张图，几乎没有结构化文本（图片型 PPT 导出的 PDF、扫描件、截图）

**处理路径**：
- 用**多模态模型**做"页面文案与版面理解"
- 模型输出接近 `deck.json` 的结构化文本框（角色、文案、归一化坐标、字体提示）
- 先让用户在 HTML 预览页确认/修改文案
- 再按两种策略之一产出背景：
  - **clean 策略**：擦字保留原背景
  - **rebuild 策略**：仿照原页重建无字背景
- 输出 `extraction.json`

**优点**：适配图片型 PPT，语义理解优于传统 OCR，文本框分组更合理

---

## Phase D 完整流程

```
PDF 上传
  ↓
D1. 页面分类 + 内容抽取
    - 判断每页是 extractable_text / image_only / mixed
    - extractable_text: PyMuPDF 解析
    - image_only: 多模态模型理解
    - 输出初版 phaseD/extraction.json
  ↓
D2. 生成预览页
    - 注入 extraction.json 到 HTML shell
    - python3 scripts/inject_extraction_review.py
    - 输出 phaseD/extraction_review.html
  ↓
G-D-ContentConfirm 门禁（硬门禁）
    - 打开 extraction_review.html
    - 用户逐页查看原图 + 文本框 overlay
    - 修改文案、调整角色、删除误识别框
    - 点"导出确认"
    - 复制带 sentinel 的 JSON 粘贴回对话
  ↓
D3. 背景策略选择 + 背景生成
    - 简单页（纯色/渐变）→ clean 策略：擦字
    - 复杂页（海报/照片底）→ rebuild 策略：仿照重建
    - 输出 phaseC/backgrounds/*.png
  ↓
D4. 生成 deck.json
    - 把 extraction.json 转成 phaseC/deck.json 格式
    - 每页 background + text_boxes
  ↓
接入 Phase C 编辑器（C4-C6）
    - C4: inject_editor_deck.py
    - C5: 用户在编辑器微调
    - C6: json_to_pptx.py 渲染
```

---

## 硬门禁

### G-D-ContentConfirm

**何时触发**：D2 生成预览页后，进入 D3 背景处理前

**门禁内容**：
- 必须打开 `phaseD/extraction_review.html`
- 用户必须在浏览器里确认/修改内容
- 用户点"导出确认"后复制 sentinel 包粘贴回对话
- agent 看到 `===PHASE-D / CONTENT EXTRACTION CONFIRMED===` 标记才继续

**反模式**：
- ❌ 直接用模型输出的 extraction.json，不让用户确认
- ❌ 在对话里贴文本让用户"口头确认"
- ❌ 跳过 HTML 预览，直接进背景生成

---

## 多模态抽取提示词协议

对图片型页面，调用多模态模型时的提示词模板：

```
你正在分析一页 PPT 幻灯片图片。

任务：提取页面上所有需要转成可编辑文本框的内容。

输出 JSON 格式：
{
  "page_type": "cover | toc | content | divider",
  "background_strategy": "clean | rebuild",
  "background_complexity": "simple | moderate | complex",
  "text_boxes": [
    {
      "role": "title | subtitle | body | footer | caption | label",
      "text": "实际文字内容",
      "bbox_norm": [x, y, width, height],  // 0-1 归一化坐标
      "font_size_est": 28,  // 估计字号 pt
      "style_hint": {
        "align": "left | center | right",
        "weight": "regular | bold",
        "color": "#FFFFFF"
      },
      "confidence": 0.95
    }
  ]
}

规则：
1. bbox_norm 是归一化坐标，左上角 (0,0)，右下角 (1,1)
2. 标题、副标题、正文、页脚等要分开识别
3. 不要遗漏小字（比如页脚、免责声明）
4. 阅读顺序要正确（左到右、上到下）
5. 如果背景简单（纯色/渐变），推荐 "clean"；如果背景复杂（照片/图案），推荐 "rebuild"
```

---

## 背景策略决策

### Clean 策略

**适用场景**：
- 纯色背景
- 渐变背景
- 简单插图背景
- 文本与背景对比强，容易擦除

**实现**：
- 根据 `text_boxes[].bbox_norm` 生成 mask
- 用 IOPaint 局部擦字
- 保留原页其他视觉元素

**优点**：像素级保真，不产生风格漂移

### Rebuild 策略

**适用场景**：
- 整页海报图
- 文字压在复杂照片/图案上
- 擦字后容易破相
- 原始页本来就是图片型设计稿

**实现**：
- 把当前页作为视觉参考（view_image）
- 通过 imagegen 生成"同布局、同氛围、完全无字符"的背景
- 类似 Phase C 的背景重建流程

**优点**：适合图片型 PPT，背景干净无伤痕

**★ Rebuild imagegen 提示词模板**（去除文字要求写死，不要缩水）：

```
[先 view_image 当前 PDF 页的 page_image]

以刚刚显示的这张图片作为唯一视觉参考 / reference。

任务：生成一张 **完全不含任何字符** 的背景图，用作可编辑 PPT 的底图。

【必须保留】
- 原页的整体构图、配色、明暗基调
- 装饰性图形、几何形状、渐变、纹理、光影
- 非文字的插画、照片、图标、图表底板（保留形状，去掉其中的文字标签）
- 页边距、留白比例、视觉重心

【绝对禁止 —— 不允许出现任何字符】
- 不要生成任何标题、副标题、正文、说明、引用、章节号
- 不要生成任何页码、页眉、页脚、日期、作者名、机构名、Logo 上的文字
- 不要生成任何水印、版权声明、扫描章、公司/学校/产品名的字样
- 不要生成看似文字的装饰艺术字、书法笔画、印章、徽标里的字符
- 不要用假字、乱码、模糊字块、马赛克字来"占位"或"仿字"
- 不要保留原页里任何字（包括英文、数字、中日韩字符、符号、标点）
- 如果原图里的 Logo 由"图形 + 文字"组成，只保留图形部分，文字部分必须完全清除
- 如果不确定某个笔画是装饰还是文字，按"是文字"处理，一律清除

【被清除后如何填补】
- 用与周围一致的纯色、渐变、图案或纹理无缝填补
- 不要留下擦除痕迹、模糊块、雾化区、色斑或几何拼接感
- 不要在原文字位置留任何视觉暗示（不要压深色块、不要加高光、不要留框线）

【输出】
- 与原图相同的宽高比与画幅
- 一张干净、可直接用作背景层的图片
- 交付前自检：整张图任何角落都不应出现可辨认的字符
```

**为什么要写这么死**：Rebuild 走 imagegen 时，模型默认会"忠实还原"原页 —— 包括原页上的所有文字。提示词只写一句"无任何文字"太弱，容易出现：残留 logo 字、复现的页脚/水印、仿造的装饰艺术字、看似有字的马赛克块。上述负面清单要**逐条明写**，不要压缩、不要省略。

**自检与回退**：
- imagegen 出图后先 `view_image` 检查是否真的完全无字
- 如仍残留：换一张更简的 prompt 再出，或退到 clean 策略 + IOPaint 局部擦
- 连续两次 rebuild 都残留 → 走失败降级表的"保留原页 + 文字框半透明遮罩"

---

## 与现有 Phase 的关系

| Phase | 输入 | 输出 | 适用场景 |
|---|---|---|---|
| **Phase A** | 主题/粗略材料 | 图片型 PPTX | 从零开始做 PPT |
| **Phase C** | 已知结构 + 规划文件 | 可编辑 PPTX | Phase A 后追加可编辑版 |
| **Phase D** | PDF 幻灯片 | extraction.json → 接入 Phase C | 已有 PDF，想转可编辑 |

Phase D 的输出是 `phaseC/deck.json` + `phaseC/backgrounds/`，直接复用 Phase C 的 C4-C6 流程。

---

## 文件产物

```
phaseD/
├── work/
│   ├── page_images/
│   │   ├── 01.png
│   │   ├── 02.png
│   │   └── ...
│   └── page_classifications.json
├── extraction.json           # 初版抽取结果
├── extraction_review.html    # 注入后的预览页
└── extraction_confirmed.json # 用户确认后的版本

phaseC/
├── backgrounds/
│   ├── 01.png
│   ├── 02.png
│   └── ...
├── deck.json
├── editor.html
└── <topic>-editable.pptx
```

---

## extraction.json 与 deck.json 的映射

| extraction.json | deck.json |
|---|---|
| `pages[].page_index` | `slides[].slide_number` |
| `pages[].page_image` (如果 strategy=rebuild 会重新生成) | `slides[].background` |
| `pages[].text_boxes[].text` | `slides[].text_boxes[].text` |
| `pages[].text_boxes[].bbox_norm` | `slides[].text_boxes[].x, y, width, height` |
| `pages[].text_boxes[].font_size_est` | `slides[].text_boxes[].font_size` |
| `pages[].text_boxes[].style_hint.align` | `slides[].text_boxes[].alignment` |
| `pages[].text_boxes[].style_hint.weight` | `slides[].text_boxes[].bold` |
| `pages[].text_boxes[].style_hint.color` | `slides[].text_boxes[].color` |

---

## Sentinel 标记

用户确认后的导出格式：

```
===PHASE-D / CONTENT EXTRACTION CONFIRMED===

本次从 PDF 提取了 12 页内容，已在预览页确认。

===EXTRACTION JSON BEGIN===
{
  "source_pdf": "example.pdf",
  "total_pages": 12,
  "pages": [...]
}
===EXTRACTION JSON END===
```

agent 看到这个标记后：
1. 原样保存 JSON 为 `phaseD/extraction_confirmed.json`
2. 不解读、不修改、不追问
3. 直接进入 D3 背景处理

---

## 失败降级

| 失败场景 | 降级策略 |
|---|---|
| 多模态模型抽取失败 | 退回传统 OCR (paddleocr) |
| OCR 也失败 | 标记为"需人工输入"，让用户在编辑器里手动添加文本框 |
| 背景擦字不干净 | 切换到 rebuild 策略 |
| rebuild 背景残留文字 / Logo 字 / 水印字 | 用同一 prompt（含完整负面清单）+ 强化"任何字符都不允许"再出一次；仍残留则 clean + IOPaint 局部擦，或降级到"保留原页 + 文字框半透明遮罩" |
| rebuild 背景风格漂移严重 | 保留原页作为背景，文字框加半透明遮罩 |
| 字体映射不准确 | 开启 `auto_fit: true`，让 PPT 自动调整字号 |

---

## 下一步扩展

- [ ] 支持批量 PDF（一次上传多个文件）
- [ ] 支持保留 PDF 中的图表、照片为独立 Picture 对象
- [ ] 支持保留动画信息（如果 PDF 有元数据）
- [ ] 支持直接从 PPT/PPTX 导入（不经过 PDF）
