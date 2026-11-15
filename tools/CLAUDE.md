# tools/
> L2 | 父级: ../CLAUDE.md

采集器只读取源站。导出器只读取已保存数据。
两者通过题库清单和原始响应连接。
凭据不进入文件，题目来源可追溯。

成员清单
collect_bank.mjs: Ego Lite 会话读题，按 30 题存档，校验 ID 并续采。
build_bank.py: 标准库离线导出器。按内容去重，保留源文，禁用冲突与非唯一答案。
prepare_runtime.py: 校验 mobile 模型摘要，生成仅含匹配字段的运行题库。
build_mac.spec: ARM64 Mac 打包声明，收集共用 OCR 与离线资源，固定版本与应用标识。
build_portable.py: 打包两平台同一识别代码，附答案时长说明，Mac 保持指定签名要求。
launcher_windows.c: Win32 无终端启动器，提供主应用、设置和退出入口。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
