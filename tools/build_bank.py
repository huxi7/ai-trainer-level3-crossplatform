#!/usr/bin/env python3
# [INPUT]: 读取 raw 清单与批次，读取 assets.json 图片映射。
# [OUTPUT]: 导出去重 SQLite、Markdown、冲突清单与源文检查报告。
# [POS]: tools 的离线导出器。采集器供给原文，助手查询 SQLite。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""使用 Python 3.9 标准库整理题库；不发起网络请求。"""

import argparse
import hashlib
import html
import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse


EXPECTED_BANKS = ("564", "558", "548", "530", "529", "528")
DEFAULT_BANK_DIR = Path(__file__).resolve().parents[1] / "question_bank"
BLOCK_TAGS = {"p", "div", "li", "tr", "table", "blockquote", "pre"}
TYPE_NAMES = {"1": "单选题", "2": "多选题", "3": "判断题", "4": "填空题", "5": "主观题"}


def dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalized(value):
    """只归一字符组合与水平空白；保留段落、标点和数字。"""
    value = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n"))
    return "\n".join(re.sub(r"[ \t\u00a0]+", " ", line).strip() for line in value.split("\n")).strip()


class FieldParser(HTMLParser):
    """生成文本和 Markdown；原始 HTML 始终另存。"""

    def __init__(self, source_url, assets):
        super().__init__(convert_charrefs=True)
        self.source_url = source_url
        self.assets = assets
        self.text = []
        self.markdown = []
        self.identity = []
        self.images = []
        self.errors = []
        self.skipped = 0
        self.verbatim = 0

    def append(self, text, markdown=None, identity=None):
        self.text.append(text)
        self.markdown.append(text if markdown is None else markdown)
        self.identity.append(text if identity is None else identity)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag in {"script", "style"}:
            if tag == "script" and str(attributes.get("type", "")).startswith("math/tex"):
                self.append("", "$")
                self.verbatim += 1
            else:
                self.skipped += 1
            return
        if self.skipped:
            return
        if tag in {"math", "svg"} or self.verbatim:
            self.verbatim += 1
            original = self.get_starttag_text()
            self.append("", original, original)
            return
        if tag == "img":
            source = attributes.get("src") or attributes.get("data-src")
            if not source:
                self.errors.append("图片缺少地址")
                self.append("[缺失图片]")
                return
            url = urljoin(self.source_url, source)
            asset = self.assets.get(url, {})
            alt = attributes.get("alt") or "图片"
            self.images.append(url)
            available = asset.get("status") == "ok"
            if not available:
                self.errors.append("图片未下载：" + url)
            path = asset.get("path", url) if available else url
            path = str(path).replace(" ", "%20").replace("(", "%28").replace(")", "%29")
            identity = "[图片:" + (asset.get("sha256", "") if available else url) + "]"
            self.append("[图片：" + alt + "]", "![" + alt.replace("]", "\\]") + "](" + path + ")", identity)
        elif tag == "br":
            self.append("\n", "  \n")
        elif tag in BLOCK_TAGS or re.fullmatch(r"h[1-6]", tag):
            self.append("\n", "\n\n")
        elif tag == "sup":
            self.append("^(", "<sup>")
        elif tag == "sub":
            self.append("_(", "<sub>")
        elif tag in {"strong", "b"}:
            self.append("", "**")
        elif tag == "code":
            self.append("", "`")

    def handle_endtag(self, tag):
        if self.skipped:
            if tag in {"script", "style"}:
                self.skipped -= 1
            return
        if self.verbatim:
            self.verbatim -= 1
            if tag == "script":
                self.append("", "$")
            else:
                closing = "</" + tag + ">"
                self.append("", closing, closing)
            return
        if tag in BLOCK_TAGS or re.fullmatch(r"h[1-6]", tag):
            self.append("\n", "\n\n")
        elif tag in {"sup", "sub"}:
            self.append(")", "</" + tag + ">")
        elif tag in {"strong", "b"}:
            self.append("", "**")
        elif tag == "code":
            self.append("", "`")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in {"img", "br", "hr", "input", "meta", "link"}:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if not self.skipped:
            self.append(data)


def render_field(value, source_url, assets):
    value = "" if value is None else str(value)
    parser = FieldParser(source_url, assets)
    parser.feed(value)
    parser.close()
    return {
        "html": value,
        "text": "".join(parser.text).strip(),
        "markdown": "".join(parser.markdown).strip(),
        "identity": normalized("".join(parser.identity)),
        "asset_urls": list(dict.fromkeys(parser.images)),
        "errors": list(dict.fromkeys(parser.errors)),
    }


def field_inputs(raw, bank):
    fields = [("title", raw.get("title", "")), ("content", raw.get("content", "")), ("parsing", raw.get("parsing", ""))]
    options = raw.get("option", {})
    if isinstance(options, dict):
        for label, value in options.items():
            if str(raw.get("option_type", "0")) == "1" and value and not re.search(r"<img\b", str(value), re.I):
                value = '<img src="' + html.escape(urljoin(bank["source_url"], str(value)), quote=True) + '">'
            fields.append(("option:" + str(label), value))
    return fields


def load_assets(bank_dir):
    path = bank_dir / "assets.json"
    if not path.exists():
        return {}, []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("assets.json 必须是 URL 到图片记录的字典")
    assets, errors = {}, []
    for url, record in data.items():
        record = record if isinstance(record, dict) else {}
        asset = dict(record)
        candidate = (bank_dir / str(asset.get("path", ""))).resolve()
        valid_path = bank_dir.resolve() in candidate.parents and candidate.is_file()
        if asset.get("status") in {"ok", "downloaded", "success", "ready"} and valid_path:
            actual_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
            if asset.get("sha256") and asset["sha256"] != actual_hash:
                errors.append("图片摘要不一致：" + url)
                asset["status"] = "failed"
            else:
                asset.update(status="ok", sha256=actual_hash, path=candidate.relative_to(bank_dir.resolve()).as_posix())
        else:
            asset["status"] = "failed"
        assets[url] = asset
    return assets, errors


def load_raw(bank_dir, expected_banks):
    banks, records, problems = {}, [], []
    coverage = defaultdict(Counter)
    raw_dir = bank_dir / "raw"
    for path in sorted(raw_dir.glob("*.manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        bank_id = str(manifest["bank_id"])
        manifest["bank_id"] = bank_id
        manifest["source_url"] = str(manifest.get("source_url", ""))
        manifest["name"] = str(manifest.get("name", bank_id))
        manifest["total"] = int(manifest["total"])
        if bank_id in banks:
            problems.append("题库清单重复：" + bank_id)
        banks[bank_id] = manifest
        entries = manifest.get("entries", [])
        if len(entries) != manifest["total"]:
            problems.append("题库 " + bank_id + " 的清单长度与公布题数不同")
        expected_list = [(str(entry["index"]), str(entry["id"])) for entry in entries]
        expected = set(expected_list)
        if len(expected) != len(expected_list):
            problems.append("题库 " + bank_id + " 的清单含重复索引与 ID")
        for batch_path in sorted(raw_dir.glob(bank_id + "_*.json")):
            if not re.fullmatch(re.escape(bank_id) + r"_\d+\.json", batch_path.name):
                continue
            response = json.loads(batch_path.read_text(encoding="utf-8"))
            if str(response.get("result", "")).upper() != "SUCCESS":
                problems.append("批次未返回 SUCCESS：" + batch_path.name)
            data = response.get("data", [])
            if isinstance(data, dict):
                items = list(data.items())
            elif isinstance(data, list):
                items = [(str(index), item) for index, item in enumerate(data)]
            else:
                problems.append("批次 data 不是数组或对象：" + batch_path.name)
                continue
            for position, raw in items:
                if not isinstance(raw, dict):
                    problems.append("批次含非对象题目：" + batch_path.name + "/" + str(position))
                    continue
                source_id = str(raw.get("id", ""))
                source_index = str(raw.get("index", position if isinstance(data, dict) else ""))
                pair = (source_index, source_id)
                coverage[bank_id][pair] += 1
                records.append({
                    "raw": raw, "bank": manifest, "source_id": source_id,
                    "source_index": source_index, "raw_file": "raw/" + batch_path.name,
                    "raw_position": str(position), "expected": pair in expected,
                })
    for bank_id in expected_banks:
        if bank_id not in banks:
            problems.append("缺少题库清单：" + bank_id)
    missing, unexpected, repeated = [], [], []
    for bank_id, bank in banks.items():
        expected = {(str(entry["index"]), str(entry["id"])) for entry in bank.get("entries", [])}
        observed = coverage[bank_id]
        for index, source_id in sorted(expected - set(observed), key=lambda pair: pair[0].zfill(8)):
            missing.append({"bank_id": bank_id, "index": index, "id": source_id})
        for index, source_id in sorted(set(observed) - expected):
            unexpected.append({"bank_id": bank_id, "index": index, "id": source_id})
        for (index, source_id), count in observed.items():
            if count > 1:
                repeated.append({"bank_id": bank_id, "index": index, "id": source_id, "count": count})
    return banks, records, {"problems": problems, "missing": missing, "unexpected": unexpected, "repeated": repeated}


def prepare_question(record, assets):
    raw, bank = record["raw"], record["bank"]
    fields = {name: render_field(value, bank["source_url"], assets) for name, value in field_inputs(raw, bank)}
    base = str(bank.get("type_base", {}).get(str(raw.get("type", "")), raw.get("type", "")))
    type_name = str(bank.get("type_labels", {}).get(str(raw.get("type", "")), TYPE_NAMES.get(base, "未知题型")))
    title, content, parsing = fields["title"], fields["content"], fields["parsing"]
    stem_html = "\n".join(item["html"] for item in (title, content) if item["html"])
    stem_text = "\n".join(item["text"] for item in (title, content) if item["text"])
    stem_identity = "\n".join(item["identity"] for item in (title, content) if item["identity"])
    errors = [error for field in fields.values() for error in field["errors"]]
    if not stem_identity:
        errors.append("题干为空")
    if base not in {"1", "2", "3"}:
        errors.append("题型不支持按选项映射")
    if not record["expected"]:
        errors.append("来源索引与 ID 未列入题库清单")
    options = []
    raw_options = raw.get("option", {})
    if not isinstance(raw_options, dict) or not raw_options:
        errors.append("选项缺失或格式无效")
    else:
        for label, original in raw_options.items():
            field = fields["option:" + str(label)]
            if not field["identity"]:
                errors.append("选项为空：" + str(label))
            options.append({
                "label": str(label), "html": field["html"], "text": field["text"],
                "key": digest(field["identity"]), "asset_urls": field["asset_urls"],
                "markdown": field["markdown"],
            })
    answer_labels = raw.get("correct_answer", [])
    valid_answer = isinstance(answer_labels, list) and bool(answer_labels)
    by_label = {option["label"]: option for option in options}
    selected = []
    if valid_answer:
        for label in answer_labels:
            option = by_label.get(str(label))
            if option is None:
                valid_answer = False
                errors.append("答案无法映射选项：" + str(label))
            else:
                selected.append(option)
        if len(set(map(str, answer_labels))) != len(answer_labels):
            valid_answer = False
            errors.append("答案字母重复")
        if base in {"1", "3"} and len(answer_labels) != 1:
            valid_answer = False
            errors.append("单选或判断题答案数量不是 1")
    else:
        errors.append("正确答案缺失或格式无效")
    # ---------- 正确选项同文时，当前字母无法唯一确定 ----------
    option_counts = Counter(option["key"] for option in options)
    if any(option_counts[option["key"]] > 1 for option in selected):
        errors.append("正确答案选项内容重复，无法唯一映射当前字母")
    keys = sorted(option["key"] for option in selected) if valid_answer else []
    identity = digest(dump([base, stem_identity, sorted(option["key"] for option in options)]))
    # ---------- 缺字段题隔离，禁止误归并 ----------
    if not stem_identity or not options or any(not fields.get("option:" + option["label"], {}).get("identity") for option in options):
        identity = digest(identity + record["bank"]["bank_id"] + record["source_id"] + record["source_index"])
    return dict(record, identity_key=identity, type_base=base, question_type=type_name,
                stem_html=stem_html, stem_text=stem_text,
                stem_markdown="\n\n".join(item["markdown"] for item in (title, content) if item["markdown"]),
                options=options, answer_labels=answer_labels, answer_keys=keys,
                answer_contents=[option["text"] for option in selected] if valid_answer else [],
                answer_markdown=[option["markdown"] for option in selected] if valid_answer else [],
                parsing_html=parsing["html"], parsing_text=parsing["text"], parsing_markdown=parsing["markdown"],
                errors=list(dict.fromkeys(errors)), valid_answer=valid_answer,
                images=list(dict.fromkeys(url for field in fields.values() for url in field["asset_urls"])))


def group_questions(records):
    grouped = {}
    for record in records:
        grouped.setdefault(record["identity_key"], []).append(record)
    questions = []
    for question_id, sources in enumerate(grouped.values(), 1):
        variants = {}
        for source in sources:
            if source["valid_answer"]:
                variants.setdefault(tuple(source["answer_keys"]), []).append(source)
        errors = list(dict.fromkeys(error for source in sources for error in source["errors"]))
        conflict = len(variants) > 1
        status = "answer_conflict" if conflict else ("incomplete" if errors else "ready")
        question = dict(sources[0], id=question_id, sources=sources, variants=list(variants.values()),
                        errors=errors, status=status, incomplete=bool(errors))
        if conflict or errors:
            question["answer_keys"] = []
            question["answer_contents"] = []
        questions.append(question)
    return questions


def public_options(options):
    return [{key: value for key, value in option.items() if key != "markdown"} for option in options]


def write_database(bank_dir, banks, questions):
    path = bank_dir / ".questions.sqlite3.tmp"
    if path.exists():
        path.unlink()
    with sqlite3.connect(str(path)) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA user_version = 1")
        db.executescript("""
            CREATE TABLE banks (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, source_url TEXT NOT NULL,
                total INTEGER NOT NULL, captured_at TEXT NOT NULL, type_labels_json TEXT NOT NULL
            );
            CREATE TABLE questions (
                id INTEGER PRIMARY KEY, identity_key TEXT UNIQUE NOT NULL,
                type_base TEXT NOT NULL, question_type TEXT NOT NULL,
                stem_html TEXT NOT NULL, stem_text TEXT NOT NULL, options_json TEXT NOT NULL,
                answer_contents_json TEXT NOT NULL, answer_keys_json TEXT NOT NULL,
                parsing_html TEXT NOT NULL, parsing_text TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('ready', 'answer_conflict', 'incomplete')),
                incomplete INTEGER NOT NULL, answer_variants_json TEXT NOT NULL,
                validation_errors_json TEXT NOT NULL, source_count INTEGER NOT NULL, image_count INTEGER NOT NULL
            );
            CREATE TABLE sources (
                id INTEGER PRIMARY KEY, question_id INTEGER NOT NULL REFERENCES questions(id),
                bank_id TEXT NOT NULL REFERENCES banks(id), source_id TEXT NOT NULL,
                source_index TEXT NOT NULL, raw_file TEXT NOT NULL, raw_position TEXT NOT NULL,
                raw_json TEXT NOT NULL, options_json TEXT NOT NULL, answer_labels_json TEXT NOT NULL,
                answer_contents_json TEXT NOT NULL, answer_keys_json TEXT NOT NULL,
                parsing_html TEXT NOT NULL, validation_errors_json TEXT NOT NULL
            );
            CREATE INDEX sources_question ON sources(question_id);
            CREATE INDEX sources_origin ON sources(bank_id, source_id, source_index);
        """)
        for bank_id, bank in banks.items():
            db.execute("INSERT INTO banks VALUES (?, ?, ?, ?, ?, ?)",
                       (bank_id, bank["name"], bank["source_url"], bank["total"], str(bank.get("captured_at", "")), dump(bank.get("type_labels", {}))))
        for question in questions:
            variants = [{"contents": variant[0]["answer_contents"], "keys": variant[0]["answer_keys"], "source_count": len(variant)} for variant in question["variants"]]
            db.execute("INSERT INTO questions VALUES (" + ",".join("?" for _ in range(17)) + ")", (
                question["id"], question["identity_key"], question["type_base"], question["question_type"],
                question["stem_html"], question["stem_text"], dump(public_options(question["options"])),
                dump(question["answer_contents"]), dump(question["answer_keys"]), question["parsing_html"], question["parsing_text"],
                question["status"], int(question["incomplete"]), dump(variants), dump(question["errors"]),
                len(question["sources"]), len(question["images"])))
            for source in question["sources"]:
                db.execute("INSERT INTO sources (question_id, bank_id, source_id, source_index, raw_file, raw_position, raw_json, options_json, answer_labels_json, answer_contents_json, answer_keys_json, parsing_html, validation_errors_json) VALUES (" + ",".join("?" for _ in range(13)) + ")", (
                    question["id"], source["bank"]["bank_id"], source["source_id"], source["source_index"], source["raw_file"], source["raw_position"],
                    dump(source["raw"]), dump(public_options(source["options"])), dump(source["answer_labels"]),
                    dump(source["answer_contents"]), dump(source["answer_keys"]), source["parsing_html"], dump(source["errors"])))
        integrity = [row[0] for row in db.execute("PRAGMA quick_check")]
        foreign_keys = list(db.execute("PRAGMA foreign_key_check"))
        db.commit()
    path.replace(bank_dir / "questions.sqlite3")
    return integrity, foreign_keys


def source_line(sources):
    return "；".join(dict.fromkeys(source["bank"]["bank_id"] + "/" + source["source_id"] for source in sources))


def markdown_options(options):
    return "\n".join("- **" + option["label"] + ".** " + option["markdown"].replace("\n", "\n  ") for option in options)


def question_markdown(question):
    parts = ["## %04d · %s" % (question["id"], question["question_type"]), question["stem_markdown"], markdown_options(question["options"])]
    if question["status"] == "ready":
        answer = "\n".join("- " + content.replace("\n", "\n  ") for content in question["answer_markdown"])
        parts.append("**正确答案内容：**\n\n" + answer)
    elif question["status"] == "answer_conflict":
        parts.append("**正确答案内容：** 无（答案冲突，见《答案冲突.md》）")
    else:
        parts.append("**正确答案内容：** 无（资料不完整，助手禁用）")
    if question["parsing_markdown"]:
        parts.append("**解析：**\n\n" + question["parsing_markdown"])
    parts.append("来源：" + source_line(question["sources"]))
    return "\n\n".join(parts)


def write_markdown(bank_dir, banks, questions, stats):
    intro = ["# 人工智能训练师三级题库", "原始 %s 条，去重后 %s 题。答案按选项内容显示。" % (stats["raw_count"], stats["unique_count"]),
             "保留源站文字。近似题不合并。选项字母仅用于阅读原题。"]
    intro.extend("- " + bank_id + "：" + bank["name"] for bank_id, bank in banks.items())
    text = "\n\n".join(intro) + "\n\n---\n\n" + "\n\n---\n\n".join(question_markdown(question) for question in questions) + "\n"
    (bank_dir / "题库.md").write_text(text, encoding="utf-8")
    conflicts = ["# 答案冲突", "共 %s 题。保留全部来源答案，助手对这些题显示“无”。" % stats["answer_conflict_count"]]
    for question in questions:
        if question["status"] != "answer_conflict":
            continue
        conflicts.extend(["## %04d · %s" % (question["id"], question["question_type"]), question["stem_markdown"], markdown_options(question["options"])])
        for index, variant in enumerate(question["variants"], 1):
            conflicts.append("**答案版本 %s：**\n\n%s\n\n来源：%s" % (index, "\n".join("- " + item for item in variant[0]["answer_markdown"]), source_line(variant)))
    (bank_dir / "答案冲突.md").write_text("\n\n".join(conflicts) + "\n", encoding="utf-8")


def build_stats(banks, records, questions, audit, asset_errors, expected_total, integrity, foreign_keys):
    errors = [source for source in records if source["errors"]]
    all_images = {url for source in records for url in source["images"]}
    image_failures = {error for source in records for error in source["errors"] if error.startswith("图片")}
    parsing_groups = sum(len({normalized(source["parsing_html"]) for source in question["sources"]}) > 1 for question in questions)
    duplicate_options = []
    for source in records:
        by_key = defaultdict(list)
        for option in source["options"]:
            by_key[option["key"]].append(option)
        repeated = [items for items in by_key.values() if len(items) > 1]
        if repeated:
            duplicate_options.append({
                "bank_id": source["bank"]["bank_id"], "id": source["source_id"],
                "options": [{"text": items[0]["text"], "labels": [item["label"] for item in items]} for items in repeated],
                "answer_mapping_ambiguous": any(items[0]["key"] in source["answer_keys"] for items in repeated),
            })
    complete = not any(audit[key] for key in audit) and not asset_errors
    return {
        "built_at": datetime.now(timezone.utc).isoformat(), "historical_expected_total": expected_total,
        "announced_total": sum(bank["total"] for bank in banks.values()), "raw_count": len(records),
        "unique_count": len(questions), "duplicate_count": len(records) - len(questions),
        "ready_count": sum(question["status"] == "ready" for question in questions),
        "answer_conflict_count": sum(question["status"] == "answer_conflict" for question in questions),
        "incomplete_count": sum(question["incomplete"] for question in questions),
        "invalid_source_count": len(errors), "answer_validation_error_count": sum(not source["valid_answer"] for source in records),
        "parsing_variant_groups": parsing_groups, "asset_reference_count": len(all_images), "image_error_count": len(image_failures),
        "duplicate_option_source_count": len(duplicate_options), "duplicate_option_sources": duplicate_options,
        "inventory_complete": complete, "quick_check": integrity, "foreign_key_errors": foreign_keys,
        "audit": audit, "asset_errors": asset_errors,
        "invalid_sources": [{"bank_id": source["bank"]["bank_id"], "id": source["source_id"], "index": source["source_index"], "errors": source["errors"]} for source in errors],
        "banks": [{"bank_id": bank_id, "name": bank["name"], "announced": bank["total"],
                   "retrieved": sum(source["bank"]["bank_id"] == bank_id for source in records),
                   "missing": sum(item["bank_id"] == bank_id for item in audit["missing"]),
                   "unexpected": sum(item["bank_id"] == bank_id for item in audit["unexpected"])} for bank_id, bank in banks.items()],
    }


def write_report(bank_dir, stats):
    rows = ["# 题库检查报告", "", "采集对账：" + ("完整" if stats["inventory_complete"] else "存在缺失或异常，见下方清单") + "。", "",
            "| 题库 | 名称 | 公布 | 取得 | 缺失 | 多余 |", "| --- | --- | ---: | ---: | ---: | ---: |"]
    rows.extend("| {bank_id} | {name} | {announced} | {retrieved} | {missing} | {unexpected} |".format(**bank) for bank in stats["banks"])
    rows.extend(["", "| 检查项 | 结果 |", "| --- | ---: |",
                 "| 原始条数 | %s |" % stats["raw_count"], "| 去重后题数 | %s |" % stats["unique_count"],
                 "| 重复来源数 | %s |" % stats["duplicate_count"], "| 可查询题数 | %s |" % stats["ready_count"],
                 "| 答案冲突题数 | %s |" % stats["answer_conflict_count"], "| 不完整题数 | %s |" % stats["incomplete_count"],
                 "| 答案映射异常来源数 | %s |" % stats["answer_validation_error_count"],
                 "| 解析不同的重复题组 | %s |" % stats["parsing_variant_groups"],
                 "| 重复选项来源数 | %s |" % stats["duplicate_option_source_count"],
                 "| 图片引用数 | %s |" % stats["asset_reference_count"], "| 图片异常数 | %s |" % stats["image_error_count"],
                 "| SQLite quick_check | %s |" % ", ".join(stats["quick_check"]), "| 外键异常数 | %s |" % len(stats["foreign_key_errors"])])
    if stats["announced_total"] != stats["historical_expected_total"]:
        rows.extend(["", "当前公布 %s 条，与旧调研 %s 条不同；以清单对账为准。" % (stats["announced_total"], stats["historical_expected_total"])])
    rows.extend(["", "## 去重与答案规则", "", "按题型、题干和全部选项的多重集归并。保留选项重复次数。",
                 "仅归一 NFC 和水平空白。保留段落、标点、数字、上下标和公式。",
                 "答案先映射到选项内容，再比较。冲突题不提供单一答案。",
                 "正确选项内容重复时，助手禁用该题。重复干扰选项保留原文。",
                 "缺失字段和未下载图片的题目标记不完整。近似题不合并。",
                 "sources 保留原字段、选项顺序、答案字母、解析与批次位置。",
                 "源错字不改写。解析差异保留在各自来源中。",
                 "本报告检查数据完整性，不代表截图识别准确率。", "", "## 源文提醒", ""])
    for source in stats["duplicate_option_sources"]:
        repeated = "；".join("、".join(item["labels"]) + " 同为“" + item["text"] + "”" for item in source["options"])
        result = "答案映射不唯一，助手禁用" if source["answer_mapping_ambiguous"] else "正确答案内容唯一"
        rows.append("- 来源 " + source["bank_id"] + "/" + source["id"] + "：" + repeated + "；" + result + "。原文保留。")
    if not stats["duplicate_option_sources"]:
        rows.append("无重复选项。")
    rows.extend(["", "## 异常清单", ""])
    found = False
    for key, label in (("problems", "结构异常"), ("missing", "缺失题目"), ("unexpected", "多余题目"), ("repeated", "重复采集")):
        for item in stats["audit"][key]:
            rows.append("- " + label + "：" + (item if isinstance(item, str) else dump(item)))
            found = True
    for item in stats["invalid_sources"]:
        rows.append("- 来源 " + item["bank_id"] + "/" + item["id"] + "（索引 " + item["index"] + "）：" + "；".join(item["errors"]))
        found = True
    for error in stats["asset_errors"]:
        rows.append("- " + error)
        found = True
    if not found:
        rows.append("无结构、缺题、答案映射或图片异常。答案冲突另见《答案冲突.md》。")
    (bank_dir / "检查报告.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def plan_assets(bank_dir, records):
    requests = {}
    for record in records:
        for name, value in field_inputs(record["raw"], record["bank"]):
            field = render_field(value, record["bank"]["source_url"], {})
            for url in field["asset_urls"]:
                suffix = Path(urlparse(url).path).suffix.lower()
                suffix = suffix if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"} else ".img"
                request = requests.setdefault(url, {"url": url, "path": "assets/" + digest(url)[:24] + suffix, "references": []})
                request["references"].append({"bank_id": record["bank"]["bank_id"], "id": record["source_id"], "field": name})
    write_json(bank_dir / "asset_requests.json", list(requests.values()))
    return len(requests)


def self_check():
    bank = {"bank_id": "test", "source_url": "https://example.com/", "type_base": {}, "type_labels": {}}
    raw = {"id": "1", "type": "1", "title": "数字 2 与 ²", "option": {"A": "甲", "B": "乙"}, "correct_answer": ["A"]}
    def prepare(value):
        return prepare_question({"raw": value, "bank": bank, "source_id": value["id"], "source_index": "0", "raw_file": "test", "raw_position": "0", "expected": True}, {})
    first = prepare(raw)
    shuffled = prepare(dict(raw, id="2", option={"A": "乙", "B": "甲"}, correct_answer=["B"]))
    grouped = group_questions([first, shuffled])
    assert len(grouped) == 1 and grouped[0]["status"] == "ready" and grouped[0]["answer_contents"] == ["甲"]
    conflicting = prepare(dict(raw, id="3", correct_answer=["B"]))
    grouped = group_questions([first, conflicting])
    assert len(grouped) == 1 and grouped[0]["status"] == "answer_conflict" and grouped[0]["answer_contents"] == []
    assert normalized("²") != normalized("2")
    repeated_answer = prepare(dict(raw, id="4", option={"A": "甲", "B": "甲"}))
    assert group_questions([repeated_answer])[0]["status"] == "incomplete"
    print("轻量自检通过：选项乱序、答案冲突、上下标保留、重复答案拒绝映射。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank-dir", type=Path, default=DEFAULT_BANK_DIR)
    parser.add_argument("--expected-total", type=int, default=2165)
    parser.add_argument("--expected-banks", nargs="+", default=list(EXPECTED_BANKS))
    parser.add_argument("--plan-assets", action="store_true", help="只导出图片下载清单")
    parser.add_argument("--self-check", action="store_true", help="只检查乱序和冲突两个小样本")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return 0
    bank_dir = args.bank_dir.resolve()
    banks, raw_records, audit = load_raw(bank_dir, args.expected_banks)
    if args.plan_assets:
        print(dump({"asset_requests": plan_assets(bank_dir, raw_records)}))
        return 0
    assets, asset_errors = load_assets(bank_dir)
    records = [prepare_question(record, assets) for record in raw_records]
    questions = group_questions(records)
    integrity, foreign_keys = write_database(bank_dir, banks, questions)
    stats = build_stats(banks, records, questions, audit, asset_errors, args.expected_total, integrity, foreign_keys)
    write_markdown(bank_dir, banks, questions, stats)
    write_report(bank_dir, stats)
    write_json(bank_dir / "stats.json", stats)
    print(dump({key: stats[key] for key in ("raw_count", "unique_count", "duplicate_count", "answer_conflict_count", "incomplete_count", "inventory_complete", "quick_check")}))
    return 0 if stats["inventory_complete"] and integrity == ["ok"] and not foreign_keys else 2


if __name__ == "__main__":
    raise SystemExit(main())
