# [INPUT]: 依赖随包提供的真实截图、同一 RapidOCR 与共同匹配规则。
# [OUTPUT]: 提供 run_checks，生成本机图像输出、拒答原因和耗时记录。
# [POS]: assistant 的跨平台验收入口；样本通过率不冒充整体准确率。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
import json
import time
from unittest.mock import patch
from .bank import Bank
from .matching import inspect
from .ocr import OCR, Row


def run_checks(root, destination):
    cases = json.loads((root / 'verification/manifest.json').read_text(encoding='utf-8'))
    bank, ocr = Bank(root / 'bank.sqlite3'), OCR(root / 'models')
    results = []
    with patch('requests.sessions.Session.request', side_effect=RuntimeError('验收禁止联网')), patch('urllib.request.urlopen', side_effect=RuntimeError('验收禁止联网')):
        for case in cases:
            start = time.perf_counter()
            rows = ocr.rows(root / 'verification' / case['file'])
            report = inspect(rows, bank, 0.60)
            result = dict(case, actual=report.display(), reason=report.reason, percent=report.percent,
                          seconds=round(time.perf_counter() - start, 3), layout=dict(ocr.last_layout),
                          rows=[row.text for row in rows])
            results.append(result)
    question = next(q for q in bank.questions if 'kernel_size 为 3' in ' '.join(o.text for o in q.options))
    rows = [Row(question.stem)] + [Row(o.label + ' ' + o.text) for o in question.options]
    numeric_changed = [Row(row.text.replace('stride 为 1', 'stride 为 9')) for row in rows]
    safety = {'numeric_rejected': inspect(numeric_changed, bank, 0.40).result is None,
              'negation_rejected': inspect([Row('不' + question.stem)] + rows[1:], bank, 0.40).result is None,
              'missing_rejected_at_low_threshold': inspect(rows[:-1], bank, 0.40).result is None}
    passed = sum(result['expected'] == result['actual'] for result in results)
    output = {'passed': passed, 'total': len(results), 'all_passed': passed == len(results) and all(safety.values()),
              'network_disabled': True, 'safety': safety, 'cases': results,
              'scope': '固定真实截图与必要拒答边界；不代表全题库或真实系统右键准确率。'}
    destination.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return output
