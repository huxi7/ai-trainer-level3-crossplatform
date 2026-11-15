# [INPUT]: 依赖 SQLite 只读题库与标准库字符规则。
# [OUTPUT]: 提供 Question、Option 与 Bank 的预计算题目索引。
# [POS]: assistant 的数据入口；只加载匹配所需字段，保留冲突状态。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass

BOUNDARIES = ("答案", "正确答案", "参考答案", "试题解析", "解析", "确定", "提交", "下一题", "交卷")


def normal(text):
    # ---------- 保留数字、上下标和运算符；只移除排版标点 ----------
    value = unicodedata.normalize("NFC", text).lower()
    return "".join(c for c in value if c.isalnum() or c in "+-=<>×÷*/%≤≥≠√^_")


def grams(text):
    return frozenset(text[i:i + 2] for i in range(len(text) - 1))


def critical(text):
    # 全角数字等价，² 等上下标保留，不对整个题目做 NFKC。
    value = unicodedata.normalize("NFC", text).translate(str.maketrans('０１２３４５６７８９．％', '0123456789.%'))
    numbers = tuple(re.findall(r"\d+(?:\.\d+)?%?", value))
    markers = tuple(value.count(c) for c in '不未非无+-=<>%×÷≤≥≠√²³^_')
    return numbers, markers


@dataclass(frozen=True)
class Option:
    label: str
    text: str
    key: str
    norm: str


@dataclass(frozen=True)
class Question:
    id: int
    kind: str
    stem: str
    norm: str
    tokens: frozenset
    options: tuple
    answer_keys: tuple
    answers: tuple
    status: str


class Bank:
    def __init__(self, path):
        uri = path.resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            rows = connection.execute("SELECT id,type_base,stem_text,options_json,answer_keys_json,answer_contents_json,status FROM questions").fetchall()
        self.questions = []
        for ident, kind, stem, options, keys, answers, status in rows:
            norm = normal(stem)
            options = tuple(Option(str(o["label"]), o["text"], o["key"], normal(o["text"])) for o in json.loads(options))
            self.questions.append(Question(ident, str(kind), stem, norm, grams(norm), options,
                                           tuple(json.loads(keys)), tuple(json.loads(answers)), status))
        if not self.questions:
            raise ValueError("题库为空")
