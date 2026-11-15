# [INPUT]: 依赖题库内容索引、OCR 阅读行和用户设置的最低文字匹配度。
# [OUTPUT]: 提供答案、最低匹配度与具体拒答原因；缺项和歧义不出答案。
# [POS]: assistant 的统一匹配边界；吸收参考版编辑距离容错与完整选项规则。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
import math
import re
from dataclasses import dataclass
from .bank import critical, grams, normal

LABEL = re.compile(r'^\s*[^\w]{0,3}\s*([A-H])(?:[\s.．、:：)）]+|(?=[\u3400-\u9fff])|$)(.*)$')
NUMBER = re.compile(r'^\s*\d{1,4}\s*[、.．]\s*')


@dataclass(frozen=True)
class Result:
    question_id: int
    letters: tuple
    contents: tuple
    judgement: bool

    @property
    def display(self):
        return '、'.join(self.contents if self.judgement else self.letters)


@dataclass(frozen=True)
class Report:
    result: object = None
    score: object = None
    reason: str = ''

    @property
    def percent(self):
        return math.floor(self.score * 100 + 0.000001) if self.score is not None else None

    def display(self, show_score=False):
        answer = self.result.display if self.result else '无'
        return f'{answer}  {self.percent}%' if show_score and self.percent is not None else answer


def similarity(original, observed):
    if critical(original) != critical(observed):
        return 0.0
    left, right = normal(original), normal(observed)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left):
        current = [i + 1]
        for j, b in enumerate(right):
            current.append(min(current[j] + 1, previous[j + 1] + 1, previous[j] + (a != b)))
        previous = current
    edit = 1 - previous[-1] / max(len(left), len(right))
    if max(len(left), len(right)) <= 6:
        return edit
    a, b = grams(left), grams(right)
    dice = 2 * len(a & b) / (len(a) + len(b)) if a and b else 0
    return 0.8 * edit + 0.2 * dice


def labelled_choice(text):
    hit = LABEL.match(text)
    return hit.groups() if hit else None


def judgement_choices(text):
    choice = labelled_choice(text)
    value = normal(choice[1] if choice else text)
    mapping = {'正确': ('正确',), '对': ('正确',), 'true': ('正确',),
               '错误': ('错误',), '错': ('错误',), 'false': ('错误',),
               '正确错误': ('正确', '错误'), '错误正确': ('错误', '正确')}
    return mapping.get(value, ())


def is_choice(text):
    return labelled_choice(text) is not None or bool(judgement_choices(text))


def is_boundary(text):
    value = normal(text)
    return (value.startswith(('答案', '正确答案', '参考答案', '營案', '暂存', '暫存', '判断题', '多选题', '单选题', '単选题')) or
            '试题解析' in value or value in ('确定', '提交', '下一题') or '交卷' in value or '答题卡' in value)


def screen_options(rows, end, judgement):
    found, last = {}, None
    for row in rows[end + 1:]:
        text = row.text.strip()
        if is_boundary(text) or (last is not None and NUMBER.match(text)):
            break
        if judgement:
            for value in judgement_choices(text):
                found[value] = value
            if len(found) == 2:
                return found
            continue
        choice = labelled_choice(text)
        if choice:
            label, content = choice
            if label in found:
                return None
            found[label], last = content.strip(), label
        elif last is not None and text:
            found[last] += ' ' + text
    if not found or any(not normal(value) for value in found.values()):
        return None
    # 页面字母可以乱序；每个实际字母必须唯一、完整。
    return found


def assign(question, current):
    source, labels = question.options, sorted(current)
    scores = [[similarity(option.text, current[label]) for label in labels] for option in source]
    ranked = []

    def visit(index, used, mapping, total):
        if index == len(source):
            ranked.append((total, tuple(mapping)))
            return
        for j, label in enumerate(labels):
            if j in used or scores[index][j] < 0.40:
                continue
            visit(index + 1, used | {j}, mapping + [j], total + scores[index][j])
    visit(0, set(), [], 0)
    if not ranked:
        return None
    ranked.sort(key=lambda entry: entry[0], reverse=True)
    answer_indices = []
    for key in question.answer_keys:
        matches = [i for i, option in enumerate(source) if option.key == key]
        if len(matches) != 1:
            return None
        answer_indices.append(matches[0])
    best_total, best = ranked[0]
    letters = tuple(sorted(labels[best[i]] for i in answer_indices))
    ambiguous = any(best_total - total < 0.12 and
                    tuple(sorted(labels[mapping[i]] for i in answer_indices)) != letters
                    for total, mapping in ranked[1:])
    actual_scores = [scores[i][j] for i, j in enumerate(best)]
    return letters, actual_scores, ambiguous


def inspect(rows, bank, minimum_similarity=0.60):
    threshold = min(0.95, max(0.40, minimum_similarity))
    windows = []
    for end in range(len(rows) - 1):
        if not is_choice(rows[end + 1].text):
            continue
        text = ''
        for start in range(end, max(-1, end - 20), -1):
            if is_choice(rows[start].text) or is_boundary(rows[start].text):
                break
            text = NUMBER.sub('', rows[start].text) + text
            if len(normal(text)) >= 6:
                windows.append((text, end))
    if not windows:
        return Report(reason='未识别到完整题干和选项字母')
    screen_characters = set(normal(''.join(row.text for row in rows)))
    hits = []
    for question in bank.questions:
        if len(question.norm) < 6 or sum(c in screen_characters for c in question.norm) / len(question.norm) < 0.4:
            continue
        score, end = max(((similarity(question.stem, text), end) for text, end in windows), key=lambda entry: entry[0])
        if score >= 0.40:
            hits.append((score, end, question))
    hits.sort(key=lambda entry: entry[0], reverse=True)
    if not hits:
        return Report(reason='题干不同，或关键数字／否定词不一致')
    candidates = []
    failure = '选项缺失、错行或字母未识别'
    for stem_score, end, question in hits[:32]:
        if question.status != 'ready':
            failure = '题库答案冲突或数据不完整'
            continue
        current = screen_options(rows, end, question.kind == '3')
        if current is None or len(current) != len(question.options):
            continue
        mapping = assign(question, current)
        if mapping is None:
            failure = '选项内容差异过大，或关键数字／否定词不一致'
            continue
        letters, scores, ambiguous = mapping
        if not letters:
            continue
        result = Result(question.id, letters, question.answers, question.kind == '3')
        score = min(stem_score, min(scores))
        rank = 0.55 * stem_score + 0.45 * sum(scores) / len(scores)
        candidates.append((rank, score, ambiguous, result))
    candidates.sort(key=lambda entry: entry[0], reverse=True)
    if not candidates:
        return Report(reason=failure)
    rank, score, ambiguous, result = candidates[0]
    other_answer = any(rank - other_rank < 0.04 and
                       (other.display != result.display or set(map(normal, other.contents)) != set(map(normal, result.contents)))
                       for other_rank, _, _, other in candidates[1:])
    if ambiguous or other_answer:
        return Report(score=score, reason='多个答案接近，无法明确区分')
    if score < threshold:
        return Report(score=score, reason=f'低于当前阈值 {round(threshold * 100)}%')
    return Report(result, score, '已匹配')


def match(rows, bank, minimum_similarity=0.60):
    return inspect(rows, bank, minimum_similarity).result
