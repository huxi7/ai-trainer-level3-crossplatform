# tests/fixtures/
> L2 | 父级: ../CLAUDE.md

三张截图来自旧 Mac 项目的原站采样。
裁去答案和解析区域，保留题干与全部选项。
派生图只验证选项位置交换和缺项拒答。

成员清单
single.png: 原站单选截图裁剪，正确字母为 C。
multiple.png: 原站多选截图裁剪，正确字母为 A、B、E。
judge.png: 原站判断截图裁剪，正确内容为“错误”。
shuffled.png: 交换单选选项内容位置，当前正确字母为 A。
incomplete.png: 单选截图缺少 D 选项，须返回“无”。
manifest.json: 截图来源、裁剪范围与预期输出。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
