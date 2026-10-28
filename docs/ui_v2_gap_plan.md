# UI v2 Round 2 · 数据缺口实施计划

本文件逐项对应 `ui_v2_data_gaps.md`。本轮只计算只读展示字段，不运行
agy/grok，不新增或迁移表，不改 GraphStore。所有聚合在敏感过滤与纠正投影后执行。
`derived` 容器明确区分派生值和原始记录；UI 标注“派生”。空图只返回零计数，
不会获得主题、立场、摘要或虚构记录。

## 逐项决策

| 原缺口 / 页面需要 | 能否从现有表得到 | 本轮行为 / 未来表或字段 | 生产者 | 尚需用户决定 |
| --- | --- | --- | --- | --- |
| 主题与判断线 | 能，nodes + lines 的准确 topic_node_id | 保持按 ID 合并；无新表 | 规则分组 | 否；跨 ID 合并另行决定 |
| 演化摘要 | 不能直接推导语义摘要 | 保留缺口；拟议 ui_enrichment.summaries，kind=line_evolution | agy/grok 候选 + 人工审核 | 是，长度、范围、审核方式 |
| 当前立场 | 能作有界展示推导，statements.stance + ts | derived.current_stance、stance_source_ids；末个有日期点，未知不回退 | 规则聚合 | 本轮否；不能视作用户正式当前立场 |
| 时间与说话人 | 仅已有 ts / speaker | 统一时间格式；derived.time_span 为首末已知时间；不补说话人或日期 | 格式化 / 规则聚合 | 时区不明仍未知；跨时区解释需未来决定 |
| 固定立场词表 | 不能从自由文本可靠规范化 | 保留原 stance；拟议 stance_vocab / stance_mappings | 人工词表 + agy/grok 候选映射 | 是，领域词表、版本、含混处理 |
| 转变标注 | 能读取 shift / reason，不能补评缺失转换 | derived.shift_count 只计明确变化标签；批次 first / unclear 不计；原标注保留 | 规则聚合；补评需独立 agy/grok 任务 | 本轮否；跨批次补评需批准 |
| 标注来源 | 新点有 shift_source，旧点可能缺失 | 缺失仍“标注来源未记录”；未来 annotations 增 provenance | 生产任务直接写入真实来源 | 是，旧来源未知不可追认 |
| 后续支持 / 反驳 | 能读取 outcome 和已存依据 ID | 沿用纠正 / 可见性过滤；缺失或失效依据降为 unknown | 规则投影 | 否；重新验证需新任务 |
| 对错计数、准确率 | 能统计已有结果；不能证明准确率 | derived.outcome_counts：supported / contradicted / unknown；准确率仍不生产 | 规则聚合 | 准确率需先决定金标准、分母与评价窗口 |
| 最稳定画像 | 无稳定性定义；已有 status / confidence | 首页 derived.confirmed_count；不以置信度排名稳定性；未来 profile_metrics | 经批准的规则指标，不以模型编造分数 | 是，稳定性定义与时间窗口 |
| 待确认事项 | 能按 proposed 且未 suppressed 计数 | 首页 derived.pending_count；没有优先级 / 影响程度 / 问题描述 | 规则聚合；问题文本需单独生产 | 排序与优先级需用户决定 |
| 实体摘要 | 无 nodes.summary | 保留缺口；拟议 summaries，kind=entity | agy/grok 候选 + 人工审核 | 是，范围、冲突与否定如何陈述 |
| 实体别名 | aliases 已存记录可读；缺失不能凭名称补全 | 保留真实别名，无新派生；未来候选仍走现有消歧审核 | 现有 resolve_entities 任务（本轮不执行） | 新别名 / 合并需核准 |
| 主题层级 | 无专用父主题，普通关系不证明层级 | 保留缺口；拟议 topic_links(parent_id, child_id, relation, refs) | 人工组织或 agy/grok 候选 | 是，树或 DAG、多父节点、环约束 |
| 证据原文 | corpus.text + graph 指针可校验切片 | 保持按需加载、hash 校验、关闭清除；缺失不补写 | 规则切片 | 缺失 corpus 的导入需另行授权 |
| 相邻上下文 | corpus.text 可切片 | 保持前后各 240 字；不宣称完整会话 | 规则切片 | 否 |
| 来源会话名 | channel 或明确 doc.meta 显示字段 | derived.session_display_name；安全 channel → 元数据 → 未命名会话 | 规则回退 | 本轮否；未来可定义适配器正式 display_name |
| 文档作者与时间 | corpus.author / ts | 统一格式，明确为文档元数据；不归属到引文 | 原样投影 | 缺失归属需来源证据，不能猜测 |
| 未关联原文反链 | 只可读 about / subject_node_ids | 保持现有关联；未来 mentions_index 独立索引 | 规则精确提及候选 / agy/grok 消歧 | 是，全文索引范围与提及判定 |
| 实体关系 | 已有 edges 方向、状态、有效期 | 一跳展示和小图缩放修正；无新增边 | 原样投影 | 多跳交互可另期授权 |

## 本轮派生契约

- `line.derived.current_stance`：按既有 `time_key` 比较 ts，取最后已知时间的
  source.stance，保留原自由文本。无日期、末点无 stance、末点 rejected /
  superseded / suppressed 或同刻立场冲突时为 null，不回退旧立场。
  `stance_source_ids` 保留末点来源 ID。同刻一致的立场可展示。
- `time_span`：已知日期的 first / last 原值；无已知日期为 null。
  不使用 observed_at、文件时间或 valid_from 替代 ts。
- `outcome_counts`：每条线内同一 statement_id 计一次。confirmed / supported
  归 supported，refuted / contradicted 归 contradicted；mixed、空标签、
  未识别值、冲突标注或失效来源归 unknown。三个计数之和等于可见点数。
  原始批次标注仍可检查，派生结果不是事实核验或准确率。
- `shift_count`：每个有效点最多计一次，已有 strengthen / weaken / reverse /
  new_angle / refine 算变化。first / same / none / unclear 不计。不比较文本来
  创造新变化，也不跨批次补评。
- 首页跨主题按 statement_id 去重再聚合；不同主题的同点结果冲突仍 unknown。
  首页附 line_count、point_count、confirmed_count、pending_count，计数基于
  当前可见和纠正后的记录，不代表隐藏记录的全库总量。
- 会话名仅在证据抽屉读取：channel → meta.session_display_name →
  meta.display_name → meta.session_name → meta.title → “未命名会话”。
  跳过空值、非字符串、路径分隔符、盘符、控制字符与常见数据文件名。
  不暴露整个 meta，也不回退 doc_id / source_path / filename。
- 时间展示：`YYYY-MM-DD HH:mm`，当前年省略年份，未知 / 无效为“时间未知”。
  显示来源墙钟时间，不隐式换时区；只有日期时保留日期精度，不编造 00:00。
  单个日期不能证明与带时分秒记录的先后语义；本轮沿用现有排序契约。

## 独立模块设计（仅设计，未实现）

未来模块建议为 `atlas/ui_enrichment/`，独立数据库 `ui_enrichment.sqlite`
位于显式配置的数据目录。独立 repository 管理表结构、版本和事务，绝不修改
现有 GraphStore / corpus 表。UI 主图查询仍只读。下列表名均为提案：

- `summaries(id, kind, target_id, text, source_refs, counter_refs, input_hash,
  producer, prompt_version, status, supersedes_id)`：演化摘要和实体摘要。
- `topic_links(id, parent_id, child_id, relation, source_refs, input_hash,
  producer, status)`：主题组织候选，不变成 graph edges。
- `stance_vocab(version, term_id, label, definition)` 与
  `stance_mappings(id, source_id, raw_stance, term_id, vocab_version,
  source_refs, producer, status)`：保留原文，允许 term_id=null。
- `annotations(id, source_id, field, value, source_refs, producer, input_hash,
  status)`：明确批准后才能用于跨批次补评，不反向覆盖旧标注。
- `profile_metrics(id, prop_id, metric_version, window, value, source_refs)`
  和 `mentions_index(id, node_id, doc_id, span, quote_hash, producer, status)`
  仅在指标和索引范围另行批准后实现。

`source_refs` 必须引用现有 source ID 和原始 doc_id/span/quote_hash；输入哈希
绑定准确来源快照（包含纠正状态）。输入变化、来源缺失或被纠正后使候选失效。
查询须重新套用敏感过滤，候选不得绕过用户纠正，也不能产生新的事实时间。
生产时间若未来记录，必须与事实时间分列，不能回填历史。历史版本保留，
人工拒绝不被后续任务覆盖。任务模板见 `ui_v2_task_templates.md`；本轮没有
注册新任务类型、运行 producer 或创建上述数据库。


## Round 4 决定（优先于上文历史提案）

本轮已实现独立 entities.sqlite 的提及索引和未执行的合并建议，并补齐标注
“派生”的结果准确率、判断线稳定性、待确认排序与模板问题；具体口径见
[ui_v2.md](ui_v2.md)。原有功能与模板保留。
主题/层级、固定立场维度、对错关系及 Line 概括改为 MR-Mem 原生能力需求，
不在 ATLAS 创建这些表、不运行任何生成任务。对应接口、空状态与设计冲突见
[for_mrmem_requirements.md](for_mrmem_requirements.md)。实体摘要仍为空状态。
