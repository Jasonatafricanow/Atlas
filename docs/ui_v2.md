# UI v2 · 本地只读界面

从仓库根目录运行（Python 标准库，无运行时 npm 或构建步骤）：

```powershell
python -m atlas serve --data-dir <explicit-data-directory> --host 127.0.0.1 --port 8765
```

浏览器打开 `http://127.0.0.1:8765`。必须显式指定已有 `graph.sqlite` 的目录。
默认仅绑定 127.0.0.1；拒绝非回环主机参数。可选 `corpus.sqlite` 用于打开证据。
原有 `atlas build/all` 静态导出不变；它继续使用 `web/index.html`。
新服务使用 `web/app.html`、`theme.css` 和 `js/`，不提供数据目录文件浏览。

## 阅读与操作

- 首页四个问题展示已有变化、后续结果、已确认画像与待确认命题。
- 判断线按相同主题 ID 合并批次，按来源时间排序，提供横轴定位与纵向事件。
  同一表态的重复标注保留各自批次，不默默挑选“正确”的标签。
- 实体页有 Cytoscape / fCoSE 一跳图、方向与历史关系、真实别名及已关联反链。
- 侧栏搜索实体名称、别名、判断线标题、线内表态和画像命题；最多返回 100 项。
  `Ctrl+K`、`⌘K` 或 `/` 聚焦搜索。输入框内 `/` 正常输入。
- 证据仅在点击时请求；关闭、切换页面、切换敏感设置或隐藏窗口时清除抽屉。
  Escape 关闭并恢复焦点。请求取消与版本检查防止迟到响应重新填充已关闭抽屉。
- 浅色纸墨与深色主题共享 CSS 变量。只有 `atlas-theme` 写入 localStorage。
  API 和静态资源均 `Cache-Control: no-store`；没有 service worker 或内容缓存。

字段缺口与语义限制见 [ui_v2_data_gaps.md](ui_v2_data_gaps.md)。
服务不会自动生成摘要、立场或判断结果，不运行抽取任务，也不调用外部 API。

## API

所有路由为 GET、JSON、只读；`sensitive=1` 是显式的本地显示选择。

| 路由 | 参数与内容 |
| --- | --- |
| `/api/toc` | 主题目录、实体名称与类型 |
| `/api/home` | 已存线、实体与命题，供四问卡片使用 |
| `/api/lines` | 按准确主题 ID 合并的判断线 |
| `/api/line` | `id=topic_node_id` |
| `/api/entities` | 可见实体 |
| `/api/entity` | `id=node_id`，一跳关系、别名、关联表态与命题 |
| `/api/search` | `q`，不搜索或返回文档原文 |
| `/api/evidence` | `kind=nodes|edges|statements|propositions`、`id`、`field=evidence|counter_evidence`、零基 `index` |

没有任意 doc_id / span 读取接口；证据必须存在于可见记录并通过原文哈希校验。
404 表示路由或可见记录不存在；409 表示记录 / 证据校验失败；503 表示数据暂不可读。
错误响应和请求日志不含源内容、搜索词或私有路径。拒绝写方法、跨源请求与非本地主机头。
这是本地阅读工具，不是面向公网的认证服务。

## 完全虚构的演示与检查

```powershell
$env:ATLAS_DATA_DIR = "$PWD/_demo_out/ui-v2-data"
$env:ATLAS_OUT_DIR = "$PWD/_demo_out/ui-v2-site"
python -m examples.tasks_demo.seed_ui_v2 --data-dir $env:ATLAS_DATA_DIR
python -m atlas serve --data-dir $env:ATLAS_DATA_DIR --port 8792
```

演示只包含虚构花圃、园丁、雨水与试种记录。不要以真实数据替换测试夹具。
测试使用 Python 3.14；pytest 是仅用于验收的测试工具，不是应用依赖。

```powershell
python -m pytest -q
node --test tests/ui_v2.test.mjs
python tools/leak_scan.py
```

前端依赖固定版本、许可证与唯一的格式修订见
[vendor/README.md](../web/js/vendor/README.md)。离线运行无需 npm。

## Round 2 · 派生字段与显示

判断线及首页的新统计均标注“派生”，只读取当前可见、纠正投影后的记录。
当前立场取末个有日期的点；末点缺失、失效或同刻冲突时仍未知。结果按点去重：
支持、反驳、未知（包含部分支持或冲突），不称为准确率。转变仅计已有变化标注。
线页展示已知日期跨度；首页统计判断线、变化、确认与待确认数量。

时间统一为 `2024-11-08 16:27`，当前年省略年份，未知显示“时间未知”；
日期精度的来源只显示日期。保留来源墙钟，不隐式换时区。
横轴可内部滚动，位置提示随滚动 / 尺寸变化更新，点击点定位纵向正文。
小图最大缩放为 1×，节点尺寸固定，居中与窗口变化保持留白。
深色主题使用暖黑、米色与琥珀色，保留关系图与转变点光晕。

证据抽屉的会话名按安全 channel、明确显示元数据、“未命名会话”回退，
不展示文件路径。完整口径及独立未来模块设计见
[ui_v2_gap_plan.md](ui_v2_gap_plan.md)，未执行的任务模板见
[ui_v2_task_templates.md](ui_v2_task_templates.md)。


## Round 4 · 适配器与独立实体索引

服务器通过 `atlas/backends/base.py` 的八方法 Backend 协议读取。
ATLAS 包装器保留原路由和错误码；证据对象新增 `ref`（char_span），旧指针仍保留。
MR-Mem 仅有未连接的只读骨架，不可选用为运行后端。
完整原生能力需求见 [for_mrmem_requirements.md](for_mrmem_requirements.md)。

判断线准确率为派生支持数 / 已知结果数，已知至少 3 条才展示百分比，
否则显示“已知 n / 共 m”。稳定性为派生 `1 − reversals/(points−1)`，至少 3 点；
转向计非首点中任一已有 reverse 标注，每点最多一次，失效来源不计。
没有转向标注不证明已评估过转换。上述指标不替代事实核验或画像稳定性排序。

待确认命题依次按置信度升序、关联主题线数降序、时间降序排列；未知置信度最后，
同层级未知时间最后，最终以 ID 稳定排序。关联包含命题本身或主体关联的可见线。
时间取有效 ts，缺失时 observed_at 只作排序元数据，不充当事实时间。
确认问题来自 `atlas/templates/pending_question.txt`，两者均标“派生”。

独立实体命令必须显式指定数据目录，只打印 JSON 数量：

```powershell
$env:ATLAS_DATA_DIR = "$PWD/_demo_out/ui-v2-r4-data"
$env:ATLAS_OUT_DIR = "$PWD/_demo_out/ui-v2-r4-site"
C:/Python314/python.exe -m examples.tasks_demo.seed_ui_v2 --data-dir $env:ATLAS_DATA_DIR
C:/Python314/python.exe -m atlas index-mentions --data-dir $env:ATLAS_DATA_DIR
C:/Python314/python.exe -m atlas suggest-merges --data-dir $env:ATLAS_DATA_DIR
```

仅写 `entities.sqlite`，graph/corpus 始终只读。mentions_index 保存节点/文档 ID、
字符偏移/长度、匹配的已有别名及索引建立时间，不复制文档正文或上下文。
匹配名称与别名的原始拼写；ASCII 至少 3 个字母数字字符并检查单词边界，
其他名称至少 2 个字母数字字符；敏感节点、依赖敏感文档的节点与敏感文档跳过。
索引建立时间仅表示执行时间，反链时间读取文档 ts。重建会替换派生提及，
源文本改变后应重建；未重建的切片如失配，抽屉拒绝显示。

合并建议只比较同类型节点：NFKC/casefold/去空白标点后名称相同；规范化名称
至少 4 字的包含关系；至少共同出现于 3 个文档且文档集合 Jaccard ≥ 0.5。
分数为规则相似度，不是实体相同概率。同文共现尤其可能只是两个相关实体。
建议始终标“建议合并（未执行）”，不会调用 graph merge，也不会生成别名。
重跑更新 suggested 候选，保留可能已有的其他审核状态。

实体页保留 Round 2 关联表态、命题及一跳图，增加提及数量/文档/时间及建议。
未建索引、无可见提及、无建议各有空状态。提及按钮仍请求 `/api/evidence`，
`kind=mentions,id=node_id,index=列表位置,field=该行token`；服务重新验证当前
节点/别名/文档可见性及 token，再走同一个 offset/hash 校验切片路径。
没有任意 doc_id/span 读取入口。开启敏感显示也不会扩展实体索引的来源范围。
