# 阅读界面动效

本轮采用 [Impeccable 4.8 animate 工作流](https://github.com/pbakaus/impeccable/blob/main/.agents/skills/impeccable/reference/animate.md)，
保留原有纸墨配色与阅读布局。上下文引擎无法安装缓存时，按其规定使用直接读取项目上下文的降级流程。

- 主要空间动效是证据抽屉：进入 240ms，退出 120ms；关闭仍立即清空原文。
- 页面和搜索结果用 140ms 淡入反馈完成，不对每张卡片做延迟入场。
- MR-Mem 的 SB 详情用 180ms、6px 横向过渡表达从结果进入详情。
- 展开依据用 140ms 透明度过渡；不动画布局尺寸、不增加依赖。
- 新选择取消旧动画，页面隐藏停止动画；系统减少动态效果时移除位移，详情仅保留 70ms 淡入。
- 无 Web Animations API 或脚本增强失败时，内容仍正常可见。

浏览器测试只使用虚构夹具，不连接真实数据或服务：

```powershell
$env:ATLAS_TEST_BROWSER = '1'
node --test tests/*.test.mjs
```

覆盖桌面/手机/中间尺寸、原有深浅主题、键盘关闭、证据清空和减少动态效果。
旧浏览器不支持 CSS starting-style / allow-discrete 时，抽屉原生开关仍可用，过渡可能简化。
