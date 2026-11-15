# question_bank/
> L2 | 父级: ../CLAUDE.md

原始响应是采集证据。SQLite 是助手查询入口。
Markdown 是人工阅读入口。
去重保留全部来源。冲突题保留全部答案。
本目录不保存登录会话或个人资料。

成员清单
questions.sqlite3: 三表查询库，保留全部来源与答案内容。
题库.md: 去重题目阅读入口，显示原选项和答案内容。
答案冲突.md: 冲突答案与来源清单，冲突题禁用。
检查报告.md: 全库对账、答案映射与源文提醒。
stats.json: 构建统计与完整异常清单。
raw/CLAUDE.md: 原始清单与批次的局部地图。
raw/ - 原始题目字段与来源清单。
assets.json: 图片源地址、本地路径与内容摘要。
assets/CLAUDE.md: 本地源图片的局部地图。
assets/ - 未改写的源站图片。

## 查询边界

questions.status 为 ready 时才取答案。
按 options_json 的内容核对全部当前选项。
answer_keys_json 标识正确选项内容。
把内容映射到当前字母，不复用源字母。
正确选项内容重复时，不提供当前字母。
raw_json 保留原题干、选项、答案与解析。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
