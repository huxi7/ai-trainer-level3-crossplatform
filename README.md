# 人工智能训练师三级答题助手

右键识别题目，在鼠标旁显示答案。支持 Windows 与 M 系列 Mac，离线运行，解压即用。

[下载 Mac 版](https://github.com/huxi7/ai-trainer-level3-crossplatform/releases/latest/download/trainer-level3-macos-arm64.zip) · [下载 Windows 版](https://github.com/huxi7/ai-trainer-level3-crossplatform/releases/latest/download/trainer-level3-windows-x64.zip) · [全部版本](https://github.com/huxi7/ai-trainer-level3-crossplatform/releases)

## 功能

- **右键解题**：在题目位置右键，自动截图、识别题干和全部选项，答案显示在鼠标旁。
- **三类题型**：支持单选、多选、判断题；判断题显示“正确”或“错误”。
- **选项乱序**：根据答案内容匹配当前页面选项，显示当前字母。
- **离线识别**：内置轻量 CPU OCR 模型与 2,164 道题，截图不上传，不用安装 Python。
- **后台运行**：日常没有主窗口、菜单栏、Dock 或托盘入口，通过独立文件打开设置和退出。
- **浮字可调**：字号、透明度和显示时长可调，无背景浮字自动消失，设置自动保存。
- **匹配可调**：支持窗口或屏幕截图，可调整匹配阈值、开关文字匹配度显示。

缺少完整选项、关键数字或否定词不一致、答案难以区分时显示“无”。

## 快速开始

| 系统 | 运行文件 |
| --- | --- |
| Windows 10 1809 及以上／Windows 11 · x64 | `三级助手.exe` |
| Mac · M 系列 | `三级助手.app` |

1. 下载对应系统的 ZIP，**完整解压**后打开文件夹。
2. 双击运行文件，看到短暂的“应用启动”提示后即可使用。
3. 在页面上显示完整题干与全部选项，然后在题目位置右键。答案默认在 **2.5 秒**后消失。

Mac 首次运行需按提示允许**屏幕录制**和**输入监听**，再退出并重新打开应用。每台新电脑需单独授权；本机更新保持固定签名身份。

Windows 普通桌面无需单独授予截图权限，也不需要管理员权限。

## 设置与退出

双击同文件夹的 `设置.exe`（Windows）或 `设置.app`（Mac）。修改自动保存，后续启动沿用。

| 设置 | 用途 |
| --- | --- |
| 字号、透明度 | 调整答案浮字的大小和深浅 |
| 答案显示时长 | 0.2–5.0 秒，默认 2.5 秒 |
| 截图范围 | 右键所在窗口，或鼠标所在屏幕 |
| 匹配阈值 | 40%–95%，默认 60% |
| 文字匹配度 | 可选择在答案旁显示 |

匹配度表示文字相似度。降低阈值会增加误匹配机会，缺项和关键内容检查仍会保留。

结束运行：双击 `退出.exe`（Windows）或 `退出.app`（Mac）。

## 题库

[题库来源](https://tx.jiexunkeji.net/app/index.php?i=36&c=entry&classes_id=0&do=practice_list&m=online_testapp&typeid=95&secondid=109&thirdid=112)。六套题库共 **2,165 条**，去重后 **2,164 题**，没有答案冲突。

[下载完整题库](https://github.com/huxi7/ai-trainer-level3-crossplatform/releases/latest/download/question-bank.zip)：包含原始数据、SQLite 和 Markdown，保留源题干、选项、答案内容、解析与来源题号，以及公式和图片。

运行包已内置精简题库，日常使用无需另行下载。

## 技术与验证

Python + PySide6 + RapidOCR（PP-OCRv5 Mobile）+ ONNX Runtime + SQLite。Mac 与 Windows 共用 OCR、版面分析和匹配代码。

当前版本 **0.3.1**。Mac 已通过真实截图小样本检查；Windows 已检查运行包完整性与共用代码，实机右键、截图和浮字尚未验收。小样本结果不代表全题库准确率。

源码构建见 [构建说明](tools/CLAUDE.md)，第三方依赖许可见 [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt)。
