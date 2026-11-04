# MR-Mem 只读阅读入口

存储合同基于 MR-Mem `feat/aml-20261013@bb0d296` 的 AML 适配器。
显式提供已有的合成数据目录及用户作用域：

```powershell
python -m atlas serve --backend mrmem --data-dir <directory> --user-id <user>
```

目录须包含 `memory.sqlite` 和 `aml_source.sqlite`，无需 ATLAS graph.sqlite。
打开首页后搜索语义文本，选择 SB 查看关联成熟段版本，再点击原文证据。
此入口是独立阅读投影，不将原生 Line 转换为主题判断线。

目前搜索为 Unicode casefold 后的字面子串匹配，最多 100 条；不是 MR-Mem
混合检索的排名。仅展示指定 user scope 的 active、来源仍有效的 canonical memory。
段摘要保留数据库中的版本；任一当前成员不可验证时隐藏该段。不认证摘要语义质量，
存储合同没有完整的摘要来源版本，因此不能声称检测所有摘要过期情况。

证据以 memory ID、引用序号与 fingerprint 授权；服务验证 namespace、用户、会话、
当前引用和 SHA-256 内容指纹。显示整条来源消息，明确不冒充精确段落引用。
time_given 为假时消息时间显示未知，不显示内部排序占位时间。

连接仅使用 SQLite mode=ro/query_only，不实例化 MemoryRuntime，不迁移数据库，
不触发 Search 编译、索引构建或模型调用。仅适用于本机受信任用户；一实例固定一个
用户作用域，页面不提供切换用户参数。证据关闭、页面隐藏或切换选择时清除。

实体、画像、立场、对错统计、主题归并暂不由此入口生成。

这是独立的第一阶段阅读入口，未实现旧 `MrMemBackend` 的主题判断线合同；
旧 UI v2 的骨架说明仍描述原有八方法适配器。新入口使用 search/detail/evidence
三个路由，不把缺少的实体或命题能力伪装成已完成。
