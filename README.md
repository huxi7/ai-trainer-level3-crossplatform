# 人工智能训练师三级解题助手

源码：[公开 GitHub 仓库](https://github.com/huxi7/ai-trainer-level3-crossplatform)。
下载：[v0.3.1 Release](https://github.com/huxi7/ai-trainer-level3-crossplatform/releases/tag/v0.3.1)。

离线截图题库助手。共用 Python 代码，分别提供 Windows 与 M 系列 Mac 免安装运行包。
运行环境、2,164 道题与约 21 MB 的 mobile OCR 模型均随包提供。
使用者不需要安装 Python，不需要联网。
0.3.1 在设置中新增答案显示时长：0.2–5.0 秒，每次调整 0.1 秒，默认 2.5 秒。
0.3.0 修复实际浏览器整窗缩放漏字、按钮字母漏读、侧栏干扰与选项错行。
两平台使用同一识别、版面和匹配流程，不使用 Mac 原生 OCR。

## 直接运行

| 平台 | 运行包 | 解压后启动 |
| --- | --- | --- |
| Windows x64 | dist/三级助手-Windows-x64.zip | 双击 三级助手.exe |
| M 系列 Mac | dist/三级助手-M系列Mac.zip | 双击 三级助手.app |

完整解压整个压缩包。保留文件夹内的 runtime、app 与模型文件。
Windows 目标为 64 位 Win10 1809 及以上、Win11。
Mac 目标为 macOS 11 及以上的 M 系列芯片。**不提供 Intel Mac 版本。**
当前已在本机 M 系列 Mac 验证构建、启动、窗口截图与 OCR。
Windows 已生成实际 EXE 与内置运行环境，完成架构、DLL 与压缩包检查。Windows 实机验收尚未完成。

## 日常行为

启动时短暂显示“应用启动”。应用不显示主窗口、菜单栏、Dock 或托盘图标。
在题目位置右键，鼠标旁显示当前页面答案，按设置的时长消失；默认 2.5 秒。
启动提示仍显示 4 秒。普通右键菜单交给原应用。
单选、多选显示当前选项字母；判断题显示“正确”或“错误”。
浮字默认 9 pt、超细、85% 透明度，没有背景、描边或阴影。
截图、OCR 与匹配全部在本机完成，不上传截图，也不操作页面选项。
只在右键时截图，首次识别时加载 OCR，连续点击不会排队创建识别任务。

另有“设置”和“退出”入口。它们是同文件夹中的独立 EXE 或 APP。
双击设置可调整字号、透明度、答案显示时长、截图范围与右键开关，修改自动保存到本机。
设置还提供最低匹配度、显示匹配度开关与最近拒答原因。
最低匹配度默认 60%，它表示文字相似度，不表示答对概率。
设置关闭后日常界面保持隐藏。双击退出结束后台进程。
再双击主应用只显示“应用已启动”，不会重复创建监听进程。

## 首次权限

**Mac：**每台电脑须给主应用授予屏幕录制、输入监听权限。
首次权限未就绪时，主应用显示配置对话框。按按钮打开系统设置并允许“三级助手”，随后退出并重新启动。
授权绑定本机账户与应用身份，无法随 ZIP 复制给别人。运行包当前采用本地签名；转发下载后，Gatekeeper 仍会要求确认打开。
0.3.0 作为已授权“三级解题助手”的升级版，沿用 net.local.trainerlevel3 的固定身份。
macos_identity.json 记录标识与指定签名要求。后续构建校验它，不清除系统授权。
本机从 .app 实际启动确认屏幕录制与输入监听均已允许，无需重新授予。
该产品身份与原生旧版一致；它们应只运行一份，原项目文件没有改动。
新电脑或系统主动撤销授权时，仍须按系统规则确认。

**Windows：**普通桌面的截图与右键监听通常不需要单独申请权限，也不需要管理员身份。
包内包含 Python 与 VC++ 运行库，不要求安装这些环境。
企业策略、安全软件、UAC 安全桌面或受保护窗口仍能限制运行；应用不绕过系统限制。
运行文件未附商业代码签名，首次下载的 SmartScreen 提示与截图权限是两回事。

窗口截图默认避开独立弹出的右键菜单。如果目标窗口返回空白图像，在设置中切换“截取鼠标所在屏幕”。

## 答案规则

截图 → OCR → 核对题干与全部选项 → 取得正确答案内容 → 映射当前字母。
题库原来的字母仅用于保留来源，不参与当前答案输出。
数字、运算符、否定词不一致时拒答。缺项、答案冲突或字母映射不唯一时显示“无”。
先定位题目列，再分别识别正文和增强后的实际按钮图像条。
图像条字符数必须与槽位数相等，读到 E、C、A、D、B 就按这些实际字母映射。
居中字母归到右侧段落首行，长题干在第一选项之前完整拼接。
页面的答案、解析和提交按钮不进入选项匹配。

## 验证

修复前，五张真实 Chrome 窗口截图全部显示“无”；修复后五题结果均与题库一致。
十个共同回归图像覆盖已选按钮、乱序字母、长选项、长判断题干、单选和缺项。
检查禁用联网，并在最低 40% 阈值复查数字、否定词和缺项拒答。
直接截取本机当前浏览器窗口得到第一题 A、B、E。
这不代表整体识别准确率，也不代表 Windows 实机右键已验证。
Windows 包内“本机检查.exe”执行同一组图并生成本机结果。
0.3.1 轻量检查了 0.2 秒后自动隐藏、显示时长保存以及启动提示时长。
完整结果见 [验证报告.md](验证报告.md) 和 [回归数据](tests/crossplatform_regression.json)。

## 题库

重新采集六套题库共 2,165 条，去重后 2,164 题。
合并 1 组完全重复题，无缺题、跨来源答案冲突或缺失图片。
保留近似题、源站错字与一道重复干扰选项题，不擅改原文。

| 文件 | 用途 |
| --- | --- |
| [题库.md](question_bank/题库.md) | 题干、原选项、答案内容、解析 |
| [questions.sqlite3](question_bank/questions.sqlite3) | 完整来源与去重题目 |
| [检查报告.md](question_bank/检查报告.md) | 全库对账与源文提醒 |
| question_bank/raw/ | 六套完整 ID 清单、76 批原始题目字段 |
| question_bank/assets/ | 源站公式图片 |
| bank.sqlite3 | 应用使用的精简只读题库 |

来源：[腾讯教育人工智能训练师三级题库](https://tx.jiexunkeji.net/app/index.php?i=36&c=entry&classes_id=0&do=practice_list&m=online_testapp&typeid=95&secondid=109&thirdid=112)。
采集复用已登录的 Ego Lite 会话，不保存凭据，不调用作答和交卷接口。
参考项目：[Mac 原生版本](https://github.com/huxi7/ai-trainer-level3-mac)，吸收版面识别与匹配经验，跨平台识别代码保持统一。

## 开发与构建

使用 Python 3.10，安装 requirements.txt 中的固定版本。
构建时还需 PyInstaller 6.11.1、pip 24.3.1；跨平台生成 Windows 启动器时使用 ziglang 0.13.0。

```bash
python tools/prepare_runtime.py
python tools/build_portable.py mac
python tools/build_portable.py windows
python tests/smoke.py
```

Mac 构建仅接受 ARM64 主机。Windows 包包含官方 CPython 3.10.11 x64 嵌入式运行库与 Windows 专用 wheel。
Qt 只保留 Core、Gui、Widgets、Network 与必要插件，未引入 WebEngine、GPU、PyTorch 或 Paddle 运行框架。

源码启动：`python main.py`；独立设置：`python main.py --configure`；退出：`python main.py --quit`。
本机配置位于 macOS 的 `~/Library/Application Support/TrainerLevel3` 或 Windows 的 `%LOCALAPPDATA%/TrainerLevel3`。
日志只保留启动、失败和耗时，滚动限制大小，不保存截图或 OCR 文本。
日志还记录具体拒答原因、题目列尺寸与按钮读取结果。
加 `--diagnostics` 启动时，只在本机保留最近一次诊断截图与文字。
`python main.py --self-check` 在本机执行共同离线回归。
