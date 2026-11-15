# verification/
> L2 | 父级: ../CLAUDE.md

截图复现用户遇到的 Chrome 原生窗口失败。
同一组图在 Mac 与 Windows 使用同一检查入口。
答案区可留在图中，匹配在答案区之前停止。
预期结果由去重 SQLite 的答案内容独立核对。

成员清单
manifest.json: 图像来源、预期当前答案与回归范围。
multiple-1.png: 真实 Chrome 第一题，预期 A、B、E。
multiple-2.png: 已选按钮与答案区，预期 A、C、E。
multiple-3.png: 侧栏图标干扰，预期 A、B、C。
multiple-4.png: 真实 Chrome 第四题，预期 A、C。
multiple-5.png: 中英文短选项，预期 B、C、D、E。
labels-reordered.png: 页面字母乱序，预期 B、C、E。
wrapped.png: 多行选项与居中字母，预期 A、B、C、D。
judge-wrapped.png: 六行判断题干，预期“正确”。
single.png: 单选原站截图，预期 C。
incomplete.png: 单选缺少整项，必须显示“无”。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
