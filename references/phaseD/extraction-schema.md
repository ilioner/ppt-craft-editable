# Phase D Extraction JSON Schema

## 用途

`phaseD/extraction.json` 是 PDF 内容提取的中间产物，记录每页识别出的文本框、角色、位置、置信度。

用户在 `extraction_review.html` 里确认/修改后，导出粘贴回对话，agent 直接转成 `phaseC/deck.json`。

---

## Schema

```json
{
  "source_pdf": "path/to/uploaded.pdf",
  "total_pages": 12,
  "aspect_ratio": "16:9",
  "extraction_method": "multimodal",
  "pages": [
    {
      "page_index": 1,
      "page_type": "cover | toc | content | divider | image_only | extractable_text | mixed",
      "page_image": "work/page_images/01.png",
      "background_strategy": "clean | rebuild",
      "background_complexity": "simple | moderate | complex",
      "text_boxes": [
        {
          "id": "p1_t1",
          "role": "title | subtitle | body | footer | caption | label | annotation",
          "text": "2026 市场扩张计划",
          "bbox_norm": [0.08, 0.10, 0.84, 0.14],
          "font_size_est": 28,
          "style_hint": {
            "align": "left | center | right",
            "weight": "regular | bold",
            "color": "#FFFFFF",
            "italic": false
          },
          "confidence": 0.94,
          "needs_review": false
        }
      ],
      "issues": [
        {
          "type": "low_confidence | overlapping_boxes | missing_text | unclear_role",
          "description": "footer 文字过小，置信度仅 0.72",
          "box_ids": ["p1_t3"]
        }
      ]
    }
  ]
}
```

---

## 字段说明

### 顶层

- `source_pdf`: 原 PDF 路径
- `total_pages`: 总页数
- `aspect_ratio`: 默认 16:9，也可能是 4:3
- `extraction_method`: `multimodal` / `pdf_parse` / `ocr`
- `pages[]`: 每页的提取结果

### 每页

- `page_index`: 从 1 开始编号
- `page_type`: 页面类型
  - `cover`: 封面
  - `toc`: 目录
  - `content`: 常规内容页
  - `divider`: 分隔页
  - `image_only`: 图片型页面（几乎没有可提取文本）
  - `extractable_text`: 有真实 PDF 文本对象
  - `mixed`: 混合型
- `page_image`: 该页渲染成的图片路径
- `background_strategy`: 背景处理策略
  - `clean`: 擦字保留原背景
  - `rebuild`: 仿照原页重建背景
- `background_complexity`: 背景复杂度（影响策略推荐）
- `text_boxes[]`: 文本框列表
- `issues[]`: 可选，提示用户需要注意的问题

### text_boxes

- `id`: 唯一标识，格式 `p{page}_t{seq}`
- `role`: 文本框角色
- `text`: 文本内容
- `bbox_norm`: 归一化坐标 `[x, y, width, height]`，范围 0-1
- `font_size_est`: 估计字号（pt）
- `style_hint`: 样式提示
  - `align`: 对齐方式
  - `weight`: 字重
  - `color`: 十六进制颜色
  - `italic`: 是否斜体
- `confidence`: 置信度 0-1
- `needs_review`: 是否需要人工复核（低置信度、重叠框等）

---

## 与 deck.json 的映射

extraction.json 确认后，每个 `text_box` 转成 `deck.json.slides[].text_boxes[]` 的一个条目：

| extraction.json | deck.json |
|---|---|
| `page_index` | `slide_number` |
| `page_image` | `background` (如果 strategy = rebuild，会重新生成) |
| `text_boxes[].text` | `text_boxes[].text` |
| `text_boxes[].bbox_norm` | `text_boxes[].x, y, width, height` |
| `text_boxes[].font_size_est` | `text_boxes[].font_size` |
| `text_boxes[].style_hint.align` | `text_boxes[].alignment` |
| `text_boxes[].style_hint.weight` | `text_boxes[].bold` |
| `text_boxes[].style_hint.color` | `text_boxes[].color` |

---

## Sentinel 标记

用户在 extraction_review.html 确认后，导出格式：

```
===PHASE-D / CONTENT EXTRACTION CONFIRMED===

本次从 PDF 提取了 12 页内容，已在预览页确认。

===EXTRACTION JSON BEGIN===
{
  "source_pdf": "...",
  "pages": [...]
}
===EXTRACTION JSON END===
```

agent 看到这个标记，直接进入 D3 背景处理 + D4 生成 deck.json。
