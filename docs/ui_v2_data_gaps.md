# UI v2 数据边界与缺口

本轮只读检查了获授权的两个数据目录的表结构、JSON 字段名和记录计数，
未导出聊天内容、人物或主题名称。选择有持久化判断线的较完整结构作为
实现依据。其表结构与仓库 GraphStore 相符：`id` / `data`，另有独立的
`corpus.sqlite` 文档表。这里仅保留字段结论，不保留私有路径与样本内容。

| 页面需要 | 已有依据 | 本期行为 / 缺口 |
| --- | --- | --- |
| 主题与判断线 | nodes、lines.topic_node_id、title、timeline | 按相同 topic_node_id 合并批次；不按名称相似度推定主题相同 |
| 演化摘要 | 没有 line.summary | 显示“数据库暂无该字段”，不拼接表态生成摘要 |
| 当前立场 | 没有 line.current_stance | 显示缺口，不将最新一句当作当前立场 |
| 时间与说话人 | statements / propositions 的 ts、speaker（可空） | 原样展示；未知时间置前。没有 ts 时不挪用观察时间或有效期 |
| 固定立场词表 | stance 为自由文本 | 原样展示，不映射成看多、看空等新立场；未记录则明确说明 |
| 转变标注 | point.shift、reason | 展示存储标签；跨批次 first 不改成新转向，标明衔接未评估 |
| 标注来源 | 新记录可能有 shift_source，检查的旧点未记录 | 显示“标注来源未记录”，不追认成模型或修复结果 |
| 后续支持 / 反驳 | outcome、outcome_reason、outcome_statement_ids | 可定位同主题后续记录；缺失、敏感或被纠正的依据使结果显示 unknown |
| 对错计数、准确率 | 没有持久化的 accuracy / right / wrong 总数 | 首页与线页显式显示缺口；不从模型标签合成准确率 |
| 最稳定画像 | propositions 有 confidence、status，但无稳定性指标 | 显示缺口，并明确展示的是已确认命题，不以置信度代替稳定性 |
| 待确认事项 | propositions.status = proposed | 展示真实待确认命题；没有影响程度、优先级或待确认问题字段，不编造排序 |
| 实体摘要 | nodes 无 summary | 显示缺口，不把关联命题改写为实体简介 |
| 实体别名 | aliases 表有 name、node_id | 读取真实别名；无条目时显示缺口，不据名称衍生别名 |
| 主题层级 | 无专用父主题字段 | 无主题树，不以一般边推断层级 |
| 证据原文 | graph 只有 doc_id、span、quote_hash；corpus 有 text | 打开抽屉后按指针截取并校验哈希；缺失 corpus / 文档时显示缺口，哈希不符则拒绝展示 |
| 相邻上下文 | corpus.text | 原文前后各最多 240 个字符，不自动归纳或补写；不假装是完整会话 |
| 来源会话名 | corpus.channel 可空，无专用 display_name | 只展示已存 channel，缺失显示缺口；不拿文件路径充当显示名 |
| 文档作者与时间 | corpus.author / ts | 明确标注为文档元数据，不推定为引文作者与时间 |
| 未关联原文反链 | 仅 statements.about / propositions.subject_node_ids | 只展示已关联记录；不做原文全文索引或推测未关联提及 |
| 实体关系 | edges.src / dst / type / status / valid_from / valid_to | 一跳局部图与完整文字列表，保留方向、历史状态和未知日期 |

API 返回字段投影与容器、索引结果，不生成新的知识事实。空图仍为空图。
旧版参考表、任务工作区、操作日志和任意文档全文不通过本 API 暴露。
API 中的 `quote` / `before` / `after` 是既存 text 的直接切片，不是新增摘要。

纠正 journal 在内存中按原有顺序覆盖命题状态；服务不写数据库或 journal。
实体、证据文档及其依赖的敏感性在服务端过滤。敏感开关只在本页内存中，
重新加载默认关闭。它是本地显示选择，不是多用户权限系统。

## 后续阶段

本期已包含首页、判断线、实体的一跳局部图与反链；没有新增编辑或纠正 API。
完整纠正工作台、原文全文搜索、多跳关系控制、时间泳道与主题层级留待后续授权。
摘要、当前立场、准确率和稳定性需要独立定义及有证据的存储支持，不能仅靠 UI 补齐。

## Round 2 supplement

Round 2 implements labelled read-time derivations and resolves the display-only
current-stance/count/span/session-name gaps within explicit limits. The Phase 1
inventory above is historical; the authoritative per-gap status and future module
proposal are now in [ui_v2_gap_plan.md](ui_v2_gap_plan.md). Semantic summaries,
topic hierarchy, fixed stance vocabulary, accuracy and stability remain absent.
Unexecuted producer contracts are in [ui_v2_task_templates.md](ui_v2_task_templates.md).


## Round 4 决定（优先于上文历史提案）

本轮已实现独立 entities.sqlite 的提及索引和未执行的合并建议，并补齐标注
“派生”的结果准确率、判断线稳定性、待确认排序与模板问题；具体口径见
[ui_v2.md](ui_v2.md)。原有功能与模板保留。
主题/层级、固定立场维度、对错关系及 Line 概括改为 MR-Mem 原生能力需求，
不在 ATLAS 创建这些表、不运行任何生成任务。对应接口、空状态与设计冲突见
[for_mrmem_requirements.md](for_mrmem_requirements.md)。实体摘要仍为空状态。
