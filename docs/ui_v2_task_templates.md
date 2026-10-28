# UI enrichment · 未执行的任务模板

以下为未来 agy/grok 或人工离线任务的文本合同提案，不是已注册的任务类型。
本轮只交付模板，未创建任务、调用模型或更改数据库。执行前先决定
`ui_v2_gap_plan.md` 中对应的用户决策，并另行授权生产。

## 公共信封与验证要求

输入：task_kind、schema_version、target_id、input_hash、prompt_version、
records（既有 ID、原始 text/stance/ts、状态、敏感性、evidence、counter_evidence）、
corrections、existing_candidates。来源未知字段保持 null，不复制完整聊天导出。
输出：task_kind、target_id、input_hash、status=candidate|insufficient_evidence、
result、source_refs、counter_refs、limitations。每个 source_ref 包含输入中已有
source_id 和原封不动的 evidence 指针，不接受任务自己编造 doc_id/span/hash。

所有任务指令：只依据输入，保留否定与反证。用户纠正优先；rejected / suppressed
材料只可作为明确标注的历史，不能变成现行结论。不得创建人物、主题 ID、事实时间、
标签来源或原文证据。无可用证据返回 insufficient_evidence 和 null result。
空输入必须如此返回。不得把本次执行时间当成事实时间。

未来验证器必须验证输入哈希、ID/指针归属、原文 hash、纠正优先、敏感依赖、
每项结论的来源引用、长度/枚举约束；通过机械校验仍需语义审核。结果只进入
独立候选存储，经批准后才可展示。不运行现有任务 merge 来写 graph。

## 1. line_evolution_summary

输入特有字段：topic_node_id、按来源时间排序的 points、原始批次标注、
unknown_time_points、经用户批准的 max_chars。

指令：用来源语言概括这一主题已记录的演化，逐项标出支持的 source_id 和
counter_refs；不得把 first/unclear 或跨批次未评估位置解释成转向。
保留同刻冲突和未知时间，不能将最后一句扩大为永久立场。

输出 result：`{text, clauses:[{text, source_refs, counter_refs}], unresolved:[]}`。
验收：每一分句有输入支持；不能只把所有观点串成确定的因果故事；超出来源则拒绝。

## 2. entity_summary

输入特有字段：node、真实 aliases、一跳 edges、已关联 statements / propositions。

指令：只总结这一实体已有的可归属信息，不把实体提及等同作者身份；区别
历史和现行命题，不把关系方向反转。不得从置信度推断人物性格或稳定特征。

输出 result：`{text, clauses:[{text, source_refs, counter_refs}], unresolved:[]}`。
验收：实体 ID、边方向、时间有效期一致；无支持的简介返回不足；别名只引用已存别名。

## 3. topic_hierarchy_proposal

输入特有字段：已存在 topic nodes、lines、被批准的 organization_mode=tree|dag。

指令：提出用于浏览的主题组织候选，不能创造新主题、把一般相关边当成上下位
事实或修改 topic_node_id。对证据不足的组合保留 unassigned。

输出 result：`{links:[{parent_id, child_id, relation:"browse_under", source_refs,
reason}], unassigned_ids:[]}`。
验收：所有 ID 来自输入；拒绝自环/环；tree 模式拒绝多父节点；每个候选保留解释。
这是浏览组织提案，批准前不作为事实关系或正式主题树。

## 4. stance_vocabulary_mapping

输入特有字段：人工批准的 vocabulary(version, term_id, label, definition)、
records 中的 raw_stance 和必要上下文。

指令：仅映射至提供的 term_id，不生成新术语；自由文本歧义或语境不足时 term_id=null。
不得根据时间、结果或其他人的表态来补出原记录未存的立场。

输出 result：`{mappings:[{source_id, raw_stance, term_id, vocab_version,
source_refs, reason}], unresolved_ids:[]}`。
验收：raw_stance 与输入逐字一致；枚举、版本、引用均有效；空 stance 只能 null。
原始 stance 永远保留；用户否定的映射不得被后续候选自动恢复。

## 合成验收样例

只用虚构花圃主题和试种记录。测试应包括：空输入、缺失时间、同刻冲突、
跨批次 first、被纠正的结论、支持与反证并存、未知词表项、循环主题候选、
失效 input_hash 与篡改 evidence 指针。模板不包含任何真实来源内容。


## Round 4 决定（优先于上文历史提案）

本轮已实现独立 entities.sqlite 的提及索引和未执行的合并建议，并补齐标注
“派生”的结果准确率、判断线稳定性、待确认排序与模板问题；具体口径见
[ui_v2.md](ui_v2.md)。原有功能与模板保留。
主题/层级、固定立场维度、对错关系及 Line 概括改为 MR-Mem 原生能力需求，
不在 ATLAS 创建这些表、不运行任何生成任务。对应接口、空状态与设计冲突见
[for_mrmem_requirements.md](for_mrmem_requirements.md)。实体摘要仍为空状态。
