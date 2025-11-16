## 长文分步骤大纲失效排查与修复方案

### 问题描述
- 分步骤（分级大纲）任务成功返回 `outline_id`，但前端写作历史中的大纲树始终为空。
- 后端 `save_outline_to_db` 收到的 `outline_data["sub_paragraphs"]` 是空数组，数据库没有任何段落被持久化。

### 根因
- 现有流程要求模型输出“带缩进/编号的纯文本”，再由 `_parse_outline_to_json`（`backend/app/services/langchain_service.py` `4280` 起）把文本转换成结构化数据。
- 解析器只识别以下几种行首格式：
  - `一、...`
  - `1.1 ...`
  - `1.1.1 ...`（依此类推）
- 模型在“分步骤”场景下常常按照 Markdown 语法输出（例如 `# 一、…`、`## 1.1 …`）。行首多出的 `#` 不匹配上述正则，`is_title` 为 `False`，整行被当成描述跳过，最终 `sub_paragraphs` 为空。

### 修复思路
1. **引入结构化输出**  
   - 对接豆包的 JSON-Schema / Structured Output 能力，让模型直接产出树形 JSON，而不是文本后解析。
   - 在 `OutlineGenerator` 中定义 Pydantic Schema（标题、描述、count_style、level、children、expected_word_count 等），使用 `llm.with_structured_output(Schema)` 或豆包 SDK 的 `response_format`。
   - 产出的 `outline_data` 可直接传给 `_distribute_word_outline` 与 `save_outline_to_db`，彻底绕开 `_parse_outline_to_json`。

2. **保留回退路径**  
   - 对非豆包模型或结构化输出失败的情况，仍可走“文本解析”方案，但要先 `lstrip('# ')` 并扩展正则，至少可兼容 Markdown。
   - 解析回退被触发时，记录日志/告警，便于监控。

3. **验证路线**  
   - 豆包模型：调用 `/api/v1/writing/outlines/generate`，确认任务日志中不再出现“大纲解析失败”，数据库里的 `SubParagraph` 数量符合预期，前端树组件能展示。
   - 其它模型：刻意让输出含 `#`，验证回退解析仍能正确落库。
   - 前端：在写作历史中选择“分步骤”任务，确认可以基于大纲继续生成长文。

### 预期效果
- 分步骤任务再也不会因为 Markdown 标记导致大纲为空。
- 结构化输出让大纲生成具备更强的一致性与可验证性，也便于后续统计、扩展（例如层级字数分配、模板化编辑）。
