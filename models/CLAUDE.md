# models/
> L2 | 父级: ../CLAUDE.md

CPU mobile 模型执行检测与中文识别。
分类兼容文件供库初始化，不执行方向分类。
识别字典随模型提供。运行时不下载文件。
来源与内容摘要写入 manifest.json。

成员清单
det.onnx: PP-OCRv5 mobile 检测模型。
rec.onnx: PP-OCRv5 mobile 中文识别模型。
cls.onnx: 轻量分类兼容模型，方向分类默认关闭。
keys.txt: PP-OCRv5 中文字符字典。
manifest.json: 官方来源、文件体积与内容摘要。

[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
