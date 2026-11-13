# Duckwork Office 3D

Duckwork 内置的等距办公室视图，基于 oslook 的 MIT Office 3D v1.4.4。
来源提交、原始文件校验值和适配说明见 `UPSTREAM.json`；保留原始 `LICENSE`。

桌面界面使用 `@duckwork/plugin-sdk`，不需要开发者模式。后端只读取网关
状态、个人资料显示名和 SQLite 会话统计；委派任务只在 SQLite 内提取
路由标签及计数，不将任务正文读入 Python。不读取消息正文、系统提示词
或数据库中的会话标题，不添加凭据、遥测或 shell 执行。

已有禁用、同意与审批机制不变。可选代理工具仍需显式运行
`duckwork plugins enable office-3d`。测试、权限与构建说明见 `README.md`。
