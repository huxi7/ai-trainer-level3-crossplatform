# 人工智能训练师三级助手

离线识别题目，右键显示答案。支持选项乱序，识别不完整时显示“无”。

**[下载最新版](https://github.com/huxi7/ai-trainer-level3-crossplatform/releases/latest)**

| 系统 | 下载 | 解压后双击 |
| --- | --- | --- |
| Windows 10/11 · 64 位 | `trainer-level3-windows-x64.zip` | `三级助手.exe` |
| Mac · M 系列 | `trainer-level3-macos-arm64.zip` | `三级助手.app` |

完整解压后运行。Python、OCR 模型和 2,164 道题均已内置，不用安装环境、不用联网。

- **使用：**在题目位置右键。单选、多选显示当前字母；判断题显示“正确／错误”。
- **设置：**双击同文件夹的“设置”，调整字号、透明度、显示时长和截图范围，自动保存。
- **显示时长：**默认 2.5 秒，可调 0.2–5.0 秒。
- **退出：**双击“退出”。日常没有主窗口、菜单栏或托盘入口。

Mac 首次需允许屏幕录制和输入监听。已授权版本保持固定签名身份；新电脑仍需授权。
Windows 普通桌面通常无需单独授权。首次下载可能出现系统安全提示。

Mac 与 Windows 共用 OCR 和匹配逻辑。Mac 已完成截图检查；Windows 实机验收尚未完成。

完整题库与原始数据见 Release 的 `question-bank.zip`。源码入口是 `main.py`，构建说明见 [tools/CLAUDE.md](tools/CLAUDE.md)。
