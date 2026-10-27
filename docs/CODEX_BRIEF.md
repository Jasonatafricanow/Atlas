# CODEX_BRIEF：ATLAS 底座 v0.3 —— 用户画像 + 知识图谱（2026-10-27 修订）

> 由 codex CLI 执行，工作目录 `<repo-root>`（底座仓库，将来开源）。一次只做一个里程碑。
> 调用方式：`codex exec -C <repo-root> -s workspace-write "<本文件 + 'implement milestone Mx'>"`（codex-cli 0.155.1 已核实参数）。

## 0. 核心概念（v0.3 方向调整）
ATLAS 是一个**个人知识图谱 + 可纠正用户画像**的空壳底座。
- **图谱**：实体（person / concept / place / event / instrument(标的) / topic(观点主题)）、关系（有类型、有方向）、时间属性（`valid_from` / `valid_to` / `observed_at`）、证据指针。
- **证据指针**：`{doc_id, span:[start,end], quote_hash: sha256(text[start:end])[:12]}`，**不拷贝原文**；校验时回 Store 重算 hash，抓住编造的引用（promnesia 思路）。
- **画像** = 命题清单：每条命题 `{prop_id, text, subject_node_ids[], evidence[], counter_evidence[], confidence 0..1, valid_from, valid_to, status: proposed|confirmed|rejected|superseded, superseded_by?}`，挂在图谱节点上，用户可纠正（对 / 不对 / 补充）。
- **不删除，只取代**（graphiti / mem0 / hindsight）：新事实与旧事实矛盾时旧的置 `superseded` 并设 `valid_to`；合并操作 = ADD / UPDATE / SUPERSEDE / NOOP，全部记入 `ops_log`，可审计。事实（fact）与观点（opinion）分开标记，观点的 confidence 随新证据变化。
- **视角（lens）**：时间线、判断线（一条主题一张卡，时间轴挂每次表态 + shift: none|refine|reverse）等都只是图谱之上的查询视图，不再是主线。
- **用户纠正优先**：`corrections.jsonl` 优先级高于任何 agent 输出；被标“不对”的命题记 `suppressed_by`，以后不会被再次生成覆盖。
- **空壳**：底座不含任何个人内容；私人适配器、私人 lens、提示词、词表都在私人仓库 / `ATLAS_DATA_DIR`。数据路径**没有默认值**，未配置即报错。

## 1. 现有骨架
`atlas/{schema,config,store,registry,cli}.py`、`adapters/jsonl_notes.py`、`lenses/{timeline,judgment_lines}.py`、`llm/__init__.py`、`web/index.html`、`examples/`、`tools/leak_scan.py`、`.githooks/pre-commit`。只用标准库（`C:\Python314\python.exe`）；唯一允许的可选依赖 `jsonschema`（缺失时退化到内置最小校验器）。

## 2. 目录结构（新增）
```
atlas/
  graph/   models.py  store.py(SQLite: nodes, edges, aliases, evidence, propositions, ops_log, corrections, task_runs)  query.py
  tasks/   kinds.py  packer.py  queue.py  validate.py  merge.py  runners.py  guard.py(凭据拦截)
  schemas/ task_envelope + {extract_entities, resolve_entities, gen_propositions, cluster_lens, verify}.{input,output}.schema.json
  prompts/ 各任务通用指令模板（无个人内容）
  lenses/  timeline.py  judgment_lines.py（改为读图谱）
  mcp/     （M6，可选只读）
docs/AGENT_TASKS.md   AGENTS.md   examples/tasks_demo/   tests/
```
运行时工作区只在 `$ATLAS_DATA_DIR/work/{pending,claimed,submitted,accepted,rejected}/<task_id>/`（task.json, input.json, output.schema.json, INSTRUCTIONS.md, lease.json, output.json, errors.json）。仓库 `.gitignore` 排除 `work/ *.sqlite _demo_out/`。

## 3. 任务契约（对 codex / agy / grok build / 任意 CLI 开放）
`task_id = kind + ":" + sha256(kind+schema_version+sorted(doc_ids)+prompt_version)[:16]`，内容不变不重复派发。
| kind | 输入 | 输出 | 关键验收 |
|---|---|---|---|
| extract_entities | ≤50 条 Document（含上下文窗口） | `entities[]{tmp_id,type,name,aliases[],evidence[]}`, `relations[]{src,dst,type,valid_from?,valid_to?,evidence[]}`, `statements[]{tmp_id,kind:fact|opinion|plan|preference,about[],text,stance?,confidence,evidence[]}` | 证据全可回查；type 在枚举内；text ≤120 字；禁绝对化词表（可配置） |
| resolve_entities | 候选实体 + 已有节点摘要 | `ops[]{op:ADD|MERGE_INTO|NOOP, tmp_id, node_id?, reason}` | 每个候选恰好一个 op；MERGE_INTO 的目标必须存在 |
| gen_propositions | 某节点子图 + 已有命题 + corrections | `ops[]{op:ADD|UPDATE|SUPERSEDE|NOOP, prop}` | 每条 ≥2 support；有 counter 必须体现；不得复活 suppressed 命题 |
| cluster_lens | 主题节点下的 statements | `lines[]{line_id,title,topic_node_id,timeline[]{ts,statement_id,shift}}` | 不新增输入外事实；新旧 line_id 映射显式 |
| verify | 市场类 statement + 私人 lens 提供的本地行情文件 | `{statement_id,outcome:confirmed|refuted|mixed|unknown,basis,data_ref}` | 无数据必须 unknown |

CLI（保持）：`atlas tasks make|list|claim|submit|validate|merge|run|reap`；新增 `atlas graph stats|show <node>|export`、`atlas profile list|correct <prop_id> --verdict wrong|right|amend --note ...`。

## 4. 隐私（放宽后的最低限度）
- 不做占位符脱敏、不做复杂敏感分类拦截。
- `guard.py` 只做**机械凭据拦截**：API key / token（sk-、ghp_、xox*、AKIA…、JWT、长 hex/base64 密钥样式）、`password=`/`密码：` 后的值、身份证号（18 位含校验位）、银行卡号（Luhn 13–19 位）、私钥块。命中则该文档段替换为 `[CREDENTIAL]` 并记日志（只报行号不报值），**不阻断任务**。
- 健康 / 丧亲类：Document `meta.sensitive=true`（由私人适配器标记）→ 照常处理，但图谱节点 / 命题继承 `sensitive`，前端**默认隐藏**，可手动切换显示。
- 开源仓库仍不得含真实个人内容：`tools/leak_scan.py` + pre-commit 保留且不得放宽。

## 5. 里程碑与验收（每个结束：全部验收通过 → 一个本地 commit）
**M1 图谱 schema + 存储 + 任务队列**：graph/models.py、graph/store.py（含 supersede 语义、ops_log）、schemas/、tasks/queue.py、validate.py（schema + 证据 hash 回查）、`tasks make/list/claim/submit/validate/reap`、`graph stats`。
```
C:\Python314\python.exe -m unittest discover -s tests -v
C:\Python314\python.exe -m atlas tasks make --kind extract_entities --config examples\atlas.config.example.toml
C:\Python314\python.exe -m atlas tasks list --json
C:\Python314\python.exe -m atlas tasks submit <id> --file examples\tasks_demo\extract_entities.good.json      # → accepted
C:\Python314\python.exe -m atlas tasks submit <id> --file examples\tasks_demo\extract_entities.bad_evidence.json # → rejected，errors.json 指出 quote_hash 不符
C:\Python314\python.exe tools\leak_scan.py
```
**M2 实体关系抽取 + 合并消歧入库**：merge.py 把 accepted 的 extract_entities / resolve_entities 写入图谱（幂等，按 task_id+input_hash）；别名表；矛盾关系 → 旧的 superseded。验收：单测；两次 `tasks merge` 后行数不变；`graph stats` 显示示例节点/边数；构造矛盾样例验证 superseded + valid_to。
**M3 画像命题生成 + 纠正回写**：gen_propositions 任务、`profile list/correct`、corrections.jsonl 优先、suppressed 不复活、confidence 更新。验收：单测；对示例命题执行 `profile correct --verdict wrong` 后重跑 merge，该命题保持 rejected。
**M4 轻量凭据拦截 + agent runners**：guard.py；`tasks run --runner codex|agy|grok|cmd --parallel 4`；runner 模板在用户配置 `[runners.<name>] cmd=[...]`，`--print-cmd` 打印。已在本机核实的无交互参数：
- codex 0.155.1：`codex exec -C {task_dir} -s workspace-write --skip-git-repo-check --ephemeral --output-schema {task_dir}/output.schema.json -o {task_dir}/output.json "<prompt>"`
- agy：`agy -p "<prompt>" --output-format json --json-schema {task_dir}/output.schema.json --mode accept-edits --add-dir {task_dir} --print-timeout 600s`（结果从 stdout 取 JSON 写 output.json）
- grok build：`grok -p "<prompt>" --cwd {task_dir} --output-format json --json-schema <schema字符串> --always-approve`（stdout 取 JSON）
测试只用 `examples/tasks_demo/fake_agent.py` 回放，不真正调用外部 agent。验收：单测（含凭据样例被替换、Luhn/身份证校验）；`tasks run --runner cmd --parallel 4` 跑通；三个模板 `--print-cmd` 输出正确。
**M5 前端**：web/index.html：图谱浏览（节点列表 + 类型筛选 + 节点详情：关系、时间属性、证据指针、命题）、画像卡片（命题、置信度、有效期、状态、“对/不对/补充”按钮导出 corrections 片段）、判断线作为一个视角页签、sensitive 默认隐藏开关；写 docs/AGENT_TASKS.md、AGENTS.md。验收：`atlas all` 用虚构语料出页（atlas.json 含 nodes/edges/propositions/lenses）；leak_scan 0 命中。
**M6（可选）MCP 只读**：stdio MCP server 暴露 `search_nodes / get_node / list_propositions`，只读。

## 6. 禁止事项
1. 不得读取 `任何真实聊天导出目录`、`旧版 ATLAS 目录`、任何真实 `ATLAS_DATA_DIR`；只用 `examples/` 虚构语料（演示数据目录放 `%TEMP%` 或 `_demo_out`）。
2. 仓库内不得出现真实人名、群名、私人路径、手机号、账号。
3. 不调用付费 API，不放凭据。
4. 不修改 `.githooks/`、`tools/leak_scan.py` 使其变宽松；不 `git push`。
5. 不新增除 `jsonschema` 外的依赖。
