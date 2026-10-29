# MR-Mem 原生能力需求（UI v2 Round 4）

本文仅描述用户界面所需的语义与读取接口，不决定 MR-Mem 的数据库、索引、
算法、任务或写入架构。本轮未读取 MR-Mem 文件，未导入模块、建立连接或执行
任何模型任务。下面的设计文档行号及引文均由本轮规格提供，未作现场核实。
接口形状是待双方确认的需求示例，不宣称后端已经支持。

## 1. 判断线名称、主题与层级

- UI 使用：左侧目录、主题列表、线页标题和层级导航。
- 当前替代：ATLAS 按精确 topic_node_id 汇总批次；保留批次原始标题。没有层级，
  不把 related_to 等一般关系解释为父子关系，也不因名字相似合并判断线。
- 所需读取形状：`{line_id, display_name, topic_id, topic_name,
  parent_topic_ids:[], organization_version, source_refs:[]}`，缺失名称或归属可空。
  需要明确多父节点是否允许，拒绝自环和任意长度的环；修改后的整张组织视图
  仍须无环。名称变更与主题迁移需要稳定 ID 和历史引用，不能破坏旧证据。
- 边界冲突：用户提供的 `LCE_DESIGN.md:164-176` 强调“去中心化、无根、Line 不界定”。
  UI 的主题导航不能据此要求 Line 有唯一根、固定边界或唯一父节点。
  一个待研究的兼容方式是把命名与主题层级作为 Lines 之上的可选视图层，
  允许同一 Line 出现在多个视图中，保留无归属状态。这只是兼容需求，不是后端设计决定。

## 2. 立场维度

- UI 使用：时间轴点、当前立场展示、同一维度内的变化比较。
- 当前替代：原样展示自由文本 stance；派生当前立场取最后有日期的有效点。
  末点缺失、被纠正或同刻冲突时未知，不回退旧立场，不强行映射固定词表。
- 所需读取形状：`{source_id, dimension_id, vocabulary_version,
  value_id:null, raw_text, evidence_refs:[], status}`。词表需给出稳定项 ID、定义、
  显示名及版本；必须同时保留原始文本。歧义、缺失或跨维度不可比时允许 null。
  词表升级后旧记录仍可追溯当时版本，用户否定的映射不得被新任务复活。

## 3. 对错关系与结果证据

- UI 使用：首页“后来怎样”、线页后续支持/反驳、结果统计与依据跳转。
- 当前替代：已有 outcome 标注按点去重，部分支持、缺失、冲突及被纠正依据
  计 unknown。派生准确率只是 supported / (supported + contradicted)，
  已知结果不足 3 条时仅显示“已知 n / 共 m”，不是独立真实性认证。
- 所需读取形状：`{judgment_id, result_id, relation: supported|contradicted|mixed|unknown,
  criterion_id, criterion_version, evaluation_window, basis_refs:[], counter_refs:[],
  assessed_at, provenance, status}`。需要明确“什么算真”：采用的可观察结果、
  可核对命题、时间窗口、评价标准与权威来源，区别事实验证与他人后续意见。
  没有足够结果证据必须 unknown；评估时间不冒充事实时间。
  结果或依据被更正时，读取接口应显式返回失效/未知，不能继续计入已知分母。

## 4. Line 级演化摘要

- UI 使用：线页的演化摘要区域。
- 当前替代：明确空状态；不拼接表态生成摘要，不创建 ATLAS 摘要表。
- 所需读取形状：`{line_id, summary:null, clauses:[{text, source_refs:[],
  counter_refs:[]}], coverage, version, provenance, status, unresolved:[]}`。
  每项概括都应有来源，保留未知时间、并行观点、纠正和未评估的批次边界；
  必须能说明覆盖到哪些点，来源变化时识别旧摘要失效。
- 范围冲突：用户提供的 `LCE_DESIGN.md:183` 明确“Line 级的概括先不做”。
  这是需要 MR-Mem 研发重新讨论的范围决定，当前 UI 空状态应保留到后端
  正式支持；本轮需求文档不视为对该决定的自动修改。

## 5. 待确认事项优先级

- UI 使用：首页待确认卡片的顺序、影响范围和确认问题。
- 当前替代：派生排序依次采用较低已知 confidence、较多关联主题线、较近
  ts（缺失时仅用 observed_at 作为明确的排序元数据）；缺失值在对应层级置后。
  问题来自 `atlas/templates/pending_question.txt`，不是模型生成或用户原话。
- 所需读取形状：`{item_id, target_id, priority:null, priority_basis,
  affected_line_ids:[], source_ts:null, question:null, question_provenance,
  policy_version, status}`。希望原生提供优先级字段及可解释依据，区分人工
  指定和派生排序，缺失时允许 UI 回退。纠正与 suppressed 状态始终优先。

## 6. 转变标注来源

- UI 使用：每个时间点的 shift、来源标签和理由；转变数、稳定性统计。
- 当前替代：仅展示已有 shift_source；旧来源缺失仍未知。派生稳定性按
  `1 − 非首点转向数 / (点数 − 1)`，至少 3 点，每个点最多计一次。
  first/unclear 不补评，也不从自由文本推断 reverse。
- 所需读取形状：`{point_id, previous_point_id:null, shift, reason,
  provenance:{kind, producer_id:null, version:null, assessed_at:null},
  evidence_refs:[], status}`。需要区分人工、模型、规则修复与回退，记录具体
  比较对象和版本，允许来源未知。后来的修复不能追认历史标注为模型或人工。

## 7. 会话显示名

- UI 使用：证据抽屉来源信息，以及未来会话级导航。
- 当前替代：派生安全 channel → 明确的显示元数据 → “未命名会话”；
  过滤路径、文件名及控制字符，不以文件时间或路径推导会话名。
- 所需读取形状：`{session_id, display_name:null, display_name_source,
  source_ts:null, author:null}`。需要区分真实来源名称与系统回退名；ID 不作为
  名称代用品，未知作者/时间保持 null。显示名不得隐式暴露私人文件路径。

## 8. 统一证据指针

- UI 使用：所有证据按钮、实体提及反链、来源与结果依据抽屉。
- 当前替代：ATLAS 原有 doc_id/span/quote_hash 保留，增加 `ref` 联合类型：
  `{kind:"char_span", doc_id, start, end, quote_hash}`；字符范围为零基、末端不含。
  quote_hash 为 UTF-8 切片的 SHA-256 前 12 位；仅打开抽屉后读取并校验原文。
- 所需另一形状：`{kind:"message_paragraphs", record_id, paragraphs:[0,2]}`，
  段落索引暂定义为零基、唯一且升序，需要后端保证 record_id 稳定、段落定位
  的版本语义以及来源校验方法。若消息可变，需要明确可复现的源版本/摘要合同，
  不能靠现时段落号默默指向不同文本。类型校验不等于内容真实性校验。
- 统一响应需求：`{ref, quote?, before?, after?, source_metadata?, verification}`；
  无权读取、敏感依赖、缺失源或校验失败必须明确区分，不回退到任意全文读取。
  列表端点只返回指针/元数据，抽屉关闭清除内容，不持久化浏览器源文本。

## 本轮交付边界

ATLAS 的 `Backend` 仅规定 toc/home/lines/line/entities/entity/search/evidence。
`AtlasSqliteBackend` 包装现有只读投影；`MrMemBackend` 的八个方法仅有读取意图
说明并抛出 NotImplementedError。message_paragraphs 只用假后端测试。
实体规则索引与合并建议存在独立 entities.sqlite，建议不执行合并；实体摘要保持空。
本轮未创建主题层级、立场词表、对错关系或 Line 摘要的 ATLAS 表。
Round 2 文档和任务模板保留为历史设计材料，上述用户决定优先于其中的未来表提案。

## 9. 判断线归并与线级综述字段（小样本实验 2026-10-29 验证）
背景：分批聚类导致同一主题被拆成多条线（样本中 1 个主题 9 条线）；页面只能平铺单句。ATLAS 小样本实验（`experiments/digest/`）证明"先归并、再综述、每句挂引用"可行，结果目前只存为任务输出文件，需要后端原生字段承接。
- `lines.merged_into`（string，可空）：被归并到的目标 line_id；`lines.member_line_ids`（array）：归并线的成员。归并须保留原线与原时间线，可撤销。
- `lines.digest`（object，可空），结构：
  - `sentences[]`：`{section: what|view|evolution|record, text(≤120字), stance?: 看多|看空|中性|计划|观察, ts?: YYYY-MM-DD, outcome?: confirmed|refuted|mixed|unknown, evidence[]: {doc_id, quote}|统一证据指针}`
  - `generated_by`（runner/model）、`generated_at`、`input_hash`（成员点集合变化即失效）、`validation`（通过的句数/总句数）。
- 约束：每句 ≥1 条可回读证据；句内数字必须出现在其证据中；`view` 句必须带 stance；立场五档枚举固定。

## 10. 实体/主题级综述字段
- `nodes.digest`（object，可空），结构同第 9 节 `sentences[]`，四段：它是什么 / 用户核心看法(含 stance) / 如何演变 / 对错记录。
- `nodes.digest_sources`：参与生成的 statement_id、line_id、去重后的提及指针列表（提及同文档 300 字内合并）。
- 失效规则：关联表态、关联线或别名变化时标记 `stale=true`，前端显示"综述可能过期"并仍可展开依据。
- 前端只读这些字段；缺失时显示"尚无综述"与派生统计，不自行持久化。