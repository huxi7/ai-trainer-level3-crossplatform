# tests/
> L2 | 父级: ../CLAUDE.md

检查真实浏览器失败样本与必要拒答边界。
截图来源为参考 Mac 项目的原站采样。
旧裁剪图不含答案区，新窗口图在答案区前停止匹配。
小样本结果不等同于整体准确率。

成员清单
smoke.py: 断网检查真实截图、乱序、缺项与关键数字。
fixtures/CLAUDE.md: 截图来源与派生规则地图。
fixtures/ - 三类原站截图与两张必要派生图。
results.json: 实际输出、耗时与检查范围。
package_results.json: ZIP、模型摘要、Windows DLL 与架构检查。
crossplatform_regression.json: 共同 OCR 的十个回归样本与修复前后结果。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
