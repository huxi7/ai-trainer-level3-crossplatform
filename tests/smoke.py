# [INPUT]: 依赖三张原站截图、交换选项派生图和随包题库模型。
# [OUTPUT]: 校验三类题、乱序、缺项及关键数字；输出实际结果与耗时。
# [POS]: tests 的轻量验收入口；断网运行 OCR，不使用答案区或模型评分作结论。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
import json
import sys
import time
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from assistant.bank import Bank
from assistant.matching import match
from assistant.ocr import OCR, Row


def main():
    bank, ocr = Bank(ROOT / "bank.sqlite3"), OCR(ROOT / "models")
    cases = json.loads((ROOT / "tests/fixtures/manifest.json").read_text(encoding="utf-8"))
    results = []
    with patch("requests.sessions.Session.request", side_effect=AssertionError("运行时不允许联网")), patch("urllib.request.urlopen", side_effect=AssertionError("运行时不允许联网")):
        for case in cases:
            start = time.perf_counter()
            rows = ocr.rows(ROOT / "tests/fixtures" / case["file"])
            result = match(rows, bank)
            actual = result.display if result else "无"
            entry = {"case": case["name"], "file": case["file"], "expected": case["expected"], "actual": actual,
                     "seconds": round(time.perf_counter() - start, 3), "rows": [row.text for row in rows]}
            results.append(entry)
            print(json.dumps(entry, ensure_ascii=False), flush=True)
    question = next(q for q in bank.questions if "kernel_size 为 3" in " ".join(o.text for o in q.options))
    rows = [Row(question.stem)] + [Row(o.label + " " + o.text) for o in question.options]
    assert match(rows, bank) is not None
    changed = [replace(row, text=row.text.replace("stride 为 1", "stride 为 9")) for row in rows]
    assert match(changed, bank) is None
    negated = [Row("不" + question.stem)] + rows[1:]
    assert match(negated, bank) is None
    all_passed = all(case["expected"] == case["actual"] for case in results)
    report = {"screenshot_cases": results, "critical_number_rejection": True, "negation_rejection": True,
              "network_disabled": True, "all_passed": all_passed,
              "scope": "三张真实原站截图，另含乱序和缺项派生图；不代表全题库准确率。"}
    (ROOT / "tests/results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
