# Phase D - PDF PPT 编辑分支 - 实现设计文档

## 概述

Phase D 是 ppt-craft-editable skill 的第三条主路径，专门处理 PDF 幻灯片转可编辑 PPTX 的场景。

**核心能力**：
- 自动判断 PDF 页面类型（矢量文本 vs 图片型）
- 用多模态模型理解图片型页面的文案和版面
- HTML 交互式预览让用户确认/修改提取内容
- 生成无字背景（擦字或重建）
- 输出原生可编辑 PPTX

---

## 架构设计

### 数据流

```
PDF 上传
  ↓
[D1] 页面分类 + 内容抽取
  ├─ extractable_text → PyMuPDF 直接提取
  └─ image_only → 多模态模型理解
  ↓
phaseD/extraction.json (初版)
  ↓
[D2] 注入 HTML 预览页
  ↓
phaseD/extraction_review.html
  ↓
[G-D-ContentConfirm] 用户在浏览器确认/编辑
  ↓
用户导出 → 复制粘贴回对话
  ↓
===PHASE-D / CONTENT EXTRACTION CONFIRMED===
  ↓
[D3] 背景策略选择 + 生成
  ├─ clean → IOPaint 擦字
  └─ rebuild → 仿照重建
  ↓
phaseC/backgrounds/*.png
  ↓
[D4] 转换为 deck.json
  ↓
phaseC/deck.json
  ↓
[接入 Phase C] C4 → C5 → C6
  ↓
phaseC/<topic>-editable.pptx
```

### 文件产物

```
phaseD/
├── work/
│   ├── page_images/
│   │   ├── 01.png
│   │   ├── 02.png
│   │   └── ...
│   └── page_*_prompt.txt (多模态提示词，供参考)
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

## 核心组件

### 1. HTML 预览页 (extraction_review.html)

**位置**：`assets/phaseD_extraction_review_shell/index.html`

**功能**：
- 左侧：原 PDF 页面图片 + 文本框 overlay
- 右侧：可编辑的文本框列表
  - 修改文案内容
  - 调整角色标签（title/body/footer）
  - 调整对齐方式
  - 删除误识别的框
- 翻页导航
- 导出确认 → 复制带 sentinel 的 JSON

**技术栈**：单文件 HTML + 内联 JS/CSS，无外部依赖

### 2. 注入脚本 (inject_extraction_review.py)

**位置**：`scripts/inject_extraction_review.py`

**功能**：
- 读取 `extraction.json`
- 替换 HTML shell 中的占位数据
- 输出 `extraction_review.html`

**用法**：
```bash
python3 scripts/inject_extraction_review.py \
  --shell assets/phaseD_extraction_review_shell/index.html \
  --data phaseD/extraction.json \
  --out phaseD/extraction_review.html
```

### 3. PDF 抽取脚本 (pdf_extract_multimodal.py)

**位置**：`scripts/pdf_extract_multimodal.py`

**功能**：
- 渲染 PDF 每页为图片
- 判断页面类型（extractable_text / image_only）
- 生成多模态提示词模板
- 输出初版 `extraction.json`

**依赖**：PyMuPDF (fitz)

**注意**：这是工程参考脚本。实际使用时，agent 会直接在对话中调用多模态能力，不依赖本脚本。

---

## 数据格式

### extraction.json Schema

见 `references/phaseD/extraction-schema.md`

核心字段：
```json
{
  "source_pdf": "path/to/file.pdf",
  "total_pages": 12,
  "aspect_ratio": "16:9",
  "extraction_method": "multimodal",
  "pages": [
    {
      "page_index": 1,
      "page_type": "cover | toc | content | divider | image_only | extractable_text",
      "page_image": "work/page_images/01.png",
      "background_strategy": "clean | rebuild",
      "background_complexity": "simple | moderate | complex",
      "text_boxes": [
        {
          "id": "p1_t1",
          "role": "title | subtitle | body | footer | caption | label",
          "text": "文案内容",
          "bbox_norm": [0.1, 0.35, 0.8, 0.15],
          "font_size_est": 32,
          "style_hint": {
            "align": "left | center | right",
            "weight": "regular | bold",
            "color": "#FFFFFF"
          },
          "confidence": 0.95,
          "needs_review": false
        }
      ],
      "issues": []
    }
  ]
}
```

### extraction.json → deck.json 映射

| extraction.json | deck.json |
|---|---|
| `pages[].page_index` | `slides[].slide_number` |
| `pages[].page_image` | `slides[].background` (如果 rebuild 会重新生成) |
| `pages[].text_boxes[].text` | `slides[].text_boxes[].text` |
| `pages[].text_boxes[].bbox_norm` | `slides[].text_boxes[].x, y, width, height` |
| `pages[].text_boxes[].font_size_est` | `slides[].text_boxes[].font_size` |
| `pages[].text_boxes[].style_hint.align` | `slides[].text_boxes[].alignment` |
| `pages[].text_boxes[].style_hint.weight` | `slides[].text_boxes[].bold` |
| `pages[].text_boxes[].style_hint.color` | `slides[].text_boxes[].color` |

---

## 多模态抽取协议

### 提示词模板

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
      "bbox_norm": [x, y, width, height],
      "font_size_est": 28,
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

### 输入

- 页面图片（PNG，150 DPI）
- 页码信息

### 输出

- 结构化 JSON（直接对接 extraction.json 格式）
- 不需要二次解析或聚类

---

## 背景策略

### Clean 策略

**适用场景**：
- 纯色/渐变背景
- 简单插图
- 文本与背景对比强

**实现**：
1. 根据 `text_boxes[].bbox_norm` 生成 mask
2. 用 IOPaint 局部擦字
3. 保留原页其他视觉元素

**优点**：像素级保真，无风格漂移

### Rebuild 策略

**适用场景**：
- 海报图
- 文字压在复杂照片/图案上
- 擦字后容易破相

**实现**：
1. 把当前页作为视觉参考（view_image）
2. 通过 imagegen 生成"同布局、同氛围、完全无字符"的背景
3. 类似 Phase C 的背景重建流程

**优点**：适合图片型 PPT，背景干净

> imagegen 的完整 prompt 模板见 `references/phaseD/workflow.md` 的 “Rebuild imagegen 提示词模板” 段。该模板把"不允许出现任何字符"作为负面清单逐条明写（标题/正文/页码/页脚/水印/logo 里的字/装饰艺术字/假字块），是 Phase D 里防止背景残字的核心防线，不要压缩或口头改写。

---

## 门禁与确认

### G-D-ContentConfirm（硬门禁）

**触发时机**：D2 生成预览页后，进入 D3 背景处理前

**门禁内容**：
1. 必须打开 `phaseD/extraction_review.html`
2. 用户在浏览器里确认/修改内容
3. 用户点"导出确认"
4. 复制带 sentinel 的 JSON 粘贴回对话

**Sentinel 标记**：
```
===PHASE-D / CONTENT EXTRACTION CONFIRMED===

本次从 PDF 提取了 N 页内容，已在预览页确认。

===EXTRACTION JSON BEGIN===
{ ... }
===EXTRACTION JSON END===
```

**Agent 行为**：
- 看到标记后，原样保存 JSON
- 不解读、不修改、不追问
- 直接进入 D3 背景处理

---

## SKILL.md 路由规则

### 触发条件

用户满足以下任一条件时，进入 Phase D：
- 上传或提供 PDF 文件路径，并提到"转成可编辑" / "想改文字" / "PPT 编辑"
- 明确说"把 PDF 转成 PPTX" / "PDF 转可编辑 PPT"
- 提供 PDF 并询问能否编辑其中内容

### Phase D 不做的事

- ❌ 不主动询问是否进入 Phase C（Phase D 本身就是为可编辑而生）
- ❌ 不跑 Phase A 的任何阶段（风格预览、规划文件、定稿图）
- ❌ 不生成图片型 PPTX（Phase D 直接输出可编辑版）

---

## 与现有 Phase 的关系

| Phase | 输入 | 输出 | 适用场景 |
|---|---|---|---|
| **Phase A** | 主题/粗略材料 | 图片型 PPTX | 从零开始做 PPT |
| **Phase C** | 已知结构 + 规划文件 | 可编辑 PPTX | Phase A 后追加可编辑版 |
| **Phase D** | PDF 幻灯片 | 可编辑 PPTX | 已有 PDF，想转可编辑 |

Phase D 的输出是 `phaseC/deck.json` + `phaseC/backgrounds/`，直接复用 Phase C 的 C4-C6 流程。

---

## 实现清单

### 已完成

- [x] `assets/phaseD_extraction_review_shell/index.html` - HTML 预览页
- [x] `scripts/inject_extraction_review.py` - 注入脚本
- [x] `scripts/pdf_extract_multimodal.py` - PDF 抽取示例脚本
- [x] `references/phaseD/workflow.md` - 工作流文档
- [x] `references/phaseD/extraction-schema.md` - 数据格式文档
- [x] SKILL.md 路由规则更新
- [x] README.md 说明更新

### 待实现（按优先级）

1. **高优先级**
   - [ ] `scripts/extraction_to_deck.py` - extraction.json → deck.json 转换脚本
   - [ ] `scripts/generate_backgrounds_from_pdf.py` - 背景生成脚本（集成 clean/rebuild 策略）
   - [ ] 多模态抽取的实际调用示例（在 agent 对话中）

2. **中优先级**
   - [ ] PyMuPDF 文本提取实现（extractable_text 页面）
   - [ ] 字体映射表 `font_alias.json`
   - [ ] preflight.py 增加 PyMuPDF 依赖检查

3. **低优先级**
   - [ ] 批量 PDF 支持
   - [ ] 保留 PDF 中的图表、照片为独立 Picture 对象
   - [ ] 直接从 PPTX 导入（不经过 PDF）

---

## 测试场景

### 场景 1：矢量 PDF（从 PPT 导出）

**输入**：clean_export.pdf（10 页，纯文本 + 简单背景）

**预期**：
- 所有页面分类为 `extractable_text`
- 文本位置精确
- 背景策略默认 `clean`
- 擦字后背景保真

### 场景 2：图片型 PDF（图片型 PPT 导出）

**输入**：image_heavy.pdf（8 页，海报风格）

**预期**：
- 所有页面分类为 `image_only`
- 多模态模型抽取文案和版面
- 背景策略默认 `rebuild`
- 重建背景干净无文字残留

### 场景 3：混合型 PDF

**输入**：mixed.pdf（封面图片型 + 内容页文本型）

**预期**：
- 页面分类混合
- 封面走 rebuild
- 内容页走 clean
- 最终 PPTX 风格一致

---

## 性能与成本

### 多模态调用次数

- 每个图片型页面：1 次抽取调用
- 背景 rebuild：每页 1-2 次生成调用

**示例**：12 页 PDF，8 页图片型，4 页文本型
- 抽取：8 次多模态调用
- 背景：8 次 rebuild（假设都需要）
- 总计：~16 次多模态/imagegen 调用

### 处理时间

- PDF 渲染：<1s/页
- 多模态抽取：~3-5s/页
- 用户确认：人工时间
- 背景生成：~5-10s/页
- PPTX 渲染：<1s

**总计**：12 页约 2-3 分钟（不含用户确认时间）

---

## 未来扩展

1. **智能页面合并**：检测连续的分栏页面，合并为单页多列布局
2. **保留动画信息**：如果 PDF 有元数据，尝试恢复动画
3. **图表识别**：把图表区域保留为独立 Picture，不转文本框
4. **批注保留**：PDF 批注转为 PPT 备注
5. **OCR 降级**：多模态失败时，自动回退到传统 OCR

---

## 总结

Phase D 通过以下创新实现了 PDF → 可编辑 PPTX 的完整链路：

1. **多模态理解代替传统 OCR**：语义分组、版面理解、阅读顺序判断
2. **HTML 交互式确认**：用户边看原图边改文案，减少错误传播
3. **双策略背景处理**：clean 擦字保真 + rebuild 仿照重建，适配不同场景
4. **复用 Phase C 管道**：deck.json 是桥梁，无需重复造轮子

最终用户体验：上传 PDF → 浏览器预览确认 → 一键导出可编辑 PPTX，全程 2-3 分钟。
