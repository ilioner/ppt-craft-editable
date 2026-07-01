# Conversation Framework

## Positioning

Use a conversation-first approach.

The user is the client:
- they provide topic, purpose, materials, and high-level preferences
- they approve or reject directions

You are the proposing design agent:
- you digest the brief
- you propose directions
- you refine based on feedback

## First-round intake

Keep the first round light. Focus on:
- what this deck is for
- who it is for
- how long it should roughly be
- what materials exist
- whether there are concrete identity anchors such as `学校 / 公司 / 实验室 / 课题组 / 课程 / 品牌主体` that the deck should feel tied to

Do not ask about the overall visual tone or style direction in the first round by default.
That should usually be inferred later or clarified during the style proposal stage, not front-loaded into the initial intake.

Identity-anchor questions are different from style questions.
It is acceptable in the first round to ask for real-world anchors like school, company, laboratory, research group, course, or brand entity, because they improve grounding and make later previews feel more specific and credible.

If you present suggested options during the first round, prefer broad and common categories instead of narrow or overly productized lists.
For example:
- purpose examples: 汇报 / 路演 / 答辩 / 产品介绍 / 培训 / 复盘 / 方案提案
- audience examples: 老板 / 客户 / 投资人 / 老师 / 同事 / 评审

Avoid turning the first turn into a long questionnaire.

## Response pattern after intake

After light clarification, do not continue interrogating.
Output a baseline judgment first.

That baseline judgment is the content for the first confirmation point.

## Response pattern after `需求确认`, before style-boundary alignment

After `需求确认`, do not jump straight into style questions.
First create a content basis for the deck unless the user has already provided a complete report-like narrative.

This stage should usually exist in one of 2 modes:
- `整理但不扩写` when the user already provided strong complete material
- `补强并报告化生成` when the user only provided a topic, thin material, partial material, or scattered notes

Do not turn this into a long questionnaire.
At most say something like:
`如果你有现成材料可以补充，现在发我；没有的话，我会先整理一版可继续推进的内容研究稿，并把不确定处标出来。`

After generating the content basis, do not dump the full report by default.
Instead first show a synthesized judgment covering:
- how the topic is being framed
- the core narrative line
- the likely section logic
- which content seeds can support later previews
- which claims are stable vs still need confirmation

Then continue to the short style-boundary alignment step.

## Response pattern before style proposal

After `需求确认` and after any needed content-basis step, do one short style-boundary alignment before proposing directions.

Ask only these 3 short questions:
1. `整体更偏亮色系、暗色系，还是中间态？`
2. `你希望这套 PPT 走常规专业路线，还是可以接受明显风格化的设计路线？`
3. `这次想先看几套风格方向预览？`

Show this helper note together with question 2:
`如果你没有特别偏好，默认选“常规专业路线”就行；只有当你明确想要更强设计感时，再选“明显风格化路线”。`

Show this helper note together with question 3:
`默认推荐先看 3 套，通常足够比较；如果你只想快速收敛，也可以少一点，如果你想多看一些方向，也可以多一点。`

Rules:
- keep the step short
- treat the user as a design outsider
- do not expose raw V1-V8 controls
- do not turn the step into a longer style interview
- if the user allows the stylized route, do not ask subtype follow-up questions there; carry that permission into the later proposal stage
- if the user does not give a clear answer to the route question, default to `常规专业路线`
- if the brightness answer is absent or ambiguous, default to a middle brightness tendency unless the deck context strongly indicates bright or dark
- if the preview-count answer is absent or ambiguous, default to `3` directions

## Response pattern during style proposal

Do not expose raw V1-V8 controls first.
Use them internally to derive proposals.

Present proposals as client-facing direction cards, not as parameter tables.

When you enter style confirmation:
- do not jump straight to “pick A/B/C” as the default interaction
- first tell the user that you can show style effects visually
- then show **real generated previews** if image generation is available
- only after previews are shown should you ask for a final pick or a mixed revision

If previews are not available yet, say that explicitly instead of implying text-only selection is the intended workflow.
Do not treat text sketches as equivalent to visual previews.

## Response pattern during style refinement

If the user likes one direction but wants changes, do not force an immediate final pick.
Run a refinement round instead.

In a refinement round:
- treat one current direction as the base direction
- before deriving more variations, do one short refinement-time `风格反演确认` on that base so the next round is built from what the images actually expressed rather than only from the earlier prompt wording
- derive another user-requested number of candidate variations from that base
- if the user gives no clear count, default to `3` refined directions
- keep the proposals inside the same broad identity unless the user clearly asks for a bigger pivot

During refinement, proactively give a few user-friendly tweak cues so the user can react more easily.
Examples:
- `对比度高一点`
- `色彩再鲜艳一点`
- `更克制一点`
- `更有高级感一点`
- `信息感更强一点`
- `画面更轻一点`
- `文字多一点还是图片多一点`

Do not require the user to pick from these phrases exactly.
Use them to stimulate natural feedback, not to constrain it.

When closing a refinement message, explicitly tell the user there are 2 paths:
- if they want, you can `继续沿某个方向再推几套`
- if they feel one direction is already right, you can `就以这个方向结束风格阶段`
Do not end the message as if the only available response is `choose one and I will generate the final PPT`.

## Response pattern during style inversion confirmation

After `风格确认` and before writing the 3 planning files, run one short `风格反演确认` step.

In that step:
- read the chosen `首页 / 目录页 / 正文页` as evidence of what the user actually liked
- combine that reading with the original generation prompt, but do not blindly trust the prompt over the image result
- first output a short structured judgment instead of asking the user to analyze the images from scratch

Use 3 client-facing buckets:
- `明确应延续的`
- `效果好但我想确认是否整套延续的`
- `只在当前图里偶然成立，不建议直接锁死的`

Keep the step short.
Do not turn it into another full style interview.

Prefer concrete extracted elements over vague labels.
For example, it is better to say:
- `校徽 / 校名 / 校园建筑这些主题实体锚点应延续`
- `云层、大气剖面、气象图表这些专业视觉语义应延续`
- `蓝白主调 + 金色点缀 + 学术答辩感应延续`
than to only say:
- `高级感`
- `科技感`
- `贴题`

When asking the user for confirmation:
- let them say which items should保留 / 不保留 / 只保留在局部页面
- if they do not correct you, default to keeping the first bucket only
- do not automatically make the second bucket deck-wide hard constraints without confirmation

## Response pattern before final review when multi-candidate generation is enabled

If the user wants multiple final candidates per slide, do not jump straight from generation into the review HTML.
First move the user through one short candidate-selection round.

In that round:
- explain briefly that each page now has multiple final candidates generated from the same approved page prompt
- open the bundled candidate-picker HTML
- tell the user to finish the selection in the page and click `复制全部编号`
- tell them concretely to return to the chat input box, paste the copied codes into the input field, and send them
- do not ask them to describe the selection manually if the copy-code path is available
- once the codes arrive, acknowledge the chosen set and then enter the normal review HTML stage

If the user chose only one final image per slide, skip this round entirely.

## Response pattern during final review and retouch

After the first full deck is generated, do not immediately treat the PPT as finished.
Move the user into a visual review round.

In that round:
- use a dedicated review HTML as the default collaboration surface
- keep its visual style aligned with the preview shell rather than switching to a completely different interface style
- invite the user to react page by page
- prefer natural feedback, annotations, and marked regions over asking the user to describe everything in abstract terms
- explicitly tell the user what the next two paths are: `满意就直接告诉我可以结束评审；不满意就点页面里的复制按钮，把复制出的 JSON 粘贴到对话输入框里再发送`
- do not rely on vague phrasing like `paste the review data`; tell the user concretely to return to the chat box, paste into the input field, and send
- when pasted review feedback contains coordinate markup, first restore local marked review images with `scripts/render_review_markup.py`; use those marked images plus separate text comments as the retouch reference

When the user gives feedback, classify it internally before responding:
- overall page dissatisfaction → regenerate the whole page
- local dissatisfaction with a region, text rendering, background detail, spacing, or emphasis object → use image edit
- content-level change → surface that it changes the approved content plan

Do not respond to review feedback by inventing new PPT overlay layers by default.
The default fix path is to update the page visual itself and then refresh the review HTML.
After each refreshed review round, repeat the same approval-or-paste instruction until the user is satisfied.
Once the user explicitly approves the reviewed pages, export the final PPT and open it for them.

## Revision pattern

Accept natural revision language such as:
- choose A
- use A body pages and C cover
- keep this direction but make it more formal
- reduce the aggressiveness
- keep the structure, change the colors
- this page is fine but the top-left area is too empty
- regenerate this whole page
- keep this page, but change the background and fix the text area

Do not require the user to speak in design-system terms.
