# MR-Mem 只读阅读入口

存储合同基于 MR-Mem `feat/aml-20261013@bb0d296` 的 AML 适配器。
显式提供已有的合成数据目录及用户作用域：

```powershell
python -m atlas serve --backend mrmem --data-dir <directory> --user-id <user> --mrmem-url http://127.0.0.1:8000 --mrmem-token-env MRMEM_AML_TOKEN
```

目录须包含 `memory.sqlite` 和 `aml_source.sqlite`，无需 ATLAS graph.sqlite。
打开首页后搜索语义文本，选择 SB 查看关联成熟段版本，再点击原文证据。
此入口是独立阅读投影，不将原生 Line 转换为主题判断线。

搜索调用已有 MR-Mem 服务的 `/search`，最多 100 条，保留其原生读出与排名。
BM25、向量、融合与 Path A 策略由服务端配置决定；Atlas 不重实现排序，服务故障
不会回退为字面匹配。`--mrmem-url` 为必填的回环 HTTP 服务根地址，端口以实际服务
为准；无认证的合成服务可省略 token 参数。数据目录必须与该服务对应同一存储。
服务返回的 line/raw/thread 标识按当前用户的已有来源关联到 SB；无法关联的原生
读出仍显示，但不虚构 SB 或证据跳转。仅跳转到 active、来源仍有效的 canonical memory。
段摘要保留数据库中的版本；任一当前成员不可验证时隐藏该段。不认证摘要语义质量，
存储合同没有完整的摘要来源版本，因此不能声称检测所有摘要过期情况。

证据以 memory ID、引用序号与 fingerprint 授权；服务验证 namespace、用户、会话、
当前引用和 SHA-256 内容指纹。显示整条来源消息，明确不冒充精确段落引用。
time_given 为假时消息时间显示未知，不显示内部排序占位时间。

本地详情和证据连接仅使用 SQLite mode=ro/query_only，不实例化 MemoryRuntime，
不迁移数据库。搜索由已运行服务处理，可能按其配置触发补编、查询向量或决策模型；
需要纯读取运行时应在服务配置关闭 compile_before_search 和 decision，并按需配置
本地 embedding。Atlas 不读取服务凭据配置，仅从显式指定环境变量取服务令牌。
仅适用于本机受信任用户；一实例固定一个
用户作用域，页面不提供切换用户参数。证据关闭、页面隐藏或切换选择时清除。

实体、画像、立场、对错统计、主题归并暂不由此入口生成。

这是独立的第一阶段阅读入口，未实现旧 `MrMemBackend` 的主题判断线合同；
旧 UI v2 的骨架说明仍描述原有八方法适配器。新入口使用 search/detail/evidence
三个路由，不把缺少的实体或命题能力伪装成已完成。
