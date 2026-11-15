# [INPUT]: 依赖 NumPy、OpenCV 与截图颜色、文字框位置。
# [OUTPUT]: 提供题目列裁剪、实际按钮图像条与按字高归位的阅读行。
# [POS]: assistant 的跨平台版面边界；Mac 与 Windows 使用同一几何规则。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
import re
from dataclasses import dataclass
from statistics import median

LETTER = re.compile(r"^[^\w]{0,3}([A-H])[.．、:：)）]?$", re.I)


@dataclass
class Fragment:
    text: str
    x: float
    y: float
    width: float
    height: float
    confidence: float = 1


def option_letter(text):
    hit = LETTER.fullmatch(text.strip())
    return hit.group(1).upper() if hit else None


def buttons(rgb):
    import cv2
    import numpy as np
    height, width = rgb.shape[:2]
    pixels = rgb.astype(np.int16)
    mask = ((pixels[:, :, 0] > 180) & (pixels[:, :, 1] > 90) &
            (pixels[:, :, 0] - pixels[:, :, 2] > 110)).astype(np.uint8) * 255
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask, 8)
    minimum = max(16, width / 180)
    maximum = max(120, width / 12)
    candidates = []
    for x, y, w, h, area in stats[1:]:
        if minimum <= w <= maximum and 18 <= h < height * 0.18 and 0.8 <= w / h <= 3.2 and area > w * h * 0.35:
            candidates.append((int(x), int(y), int(w), int(h)))
    groups = []
    for box in candidates:
        x, y, w, h = box
        column = [other for other in candidates if
                  abs(other[0] + other[2] / 2 - x - w / 2) < max(w, other[2]) * 0.25 and
                  abs(other[2] - w) < max(w, other[2]) * 0.12]
        if len(column) >= 2:
            groups.append(column)
    if not groups:
        return []
    result = max(groups, key=lambda group: (len(group), max(b[1] for b in group) - min(b[1] for b in group)))
    # ---------- 已选按钮连接到整行边框；在真实字母列切开后再取连通块 ----------
    column_left = round(median(b[0] for b in result))
    column_width = round(median(b[2] for b in result))
    button_height = median(b[3] for b in result)
    restricted = mask[:, column_left:column_left + column_width]
    _, _, column_stats, _ = cv2.connectedComponentsWithStats(restricted, 8)
    completed = []
    for x, y, w, h, area in column_stats[1:]:
        if w >= column_width * 0.8 and button_height * 0.75 <= h <= button_height * 1.35 and area > w * h * 0.45:
            # 全图中超宽的底部按钮不在题目选项区域。
            if y > height * 0.90:
                continue
            completed.append((column_left + int(x), int(y), int(w), int(h)))
    completed = sorted(set(completed or result), key=lambda box: box[1])
    anchor_y = sorted(b[1] + b[3] / 2 for b in result)
    anchor_gaps = [b - a for a, b in zip(anchor_y, anchor_y[1:]) if b > a]
    maximum_gap = max(max(anchor_gaps, default=0) * 1.15, button_height * 2.8)
    clusters = []
    for box in completed:
        if not clusters or box[1] + box[3] / 2 - (clusters[-1][-1][1] + clusters[-1][-1][3] / 2) > maximum_gap:
            clusters.append([])
        clusters[-1].append(box)
    # 解析标题也会着色；选择包含真实选项列锚点最多的连续按钮组。
    return max(clusters, key=lambda group: (sum(any(abs(b[1] - anchor[1]) < 5 for b in group) for anchor in result), len(group)))


def question_column(rgb, boxes):
    if len(boxes) < 2:
        return rgb, 0
    width = rgb.shape[1]
    left = max(0, min(b[0] for b in boxes) - round(median(b[2] for b in boxes) * 0.5))
    right = min(width, max(b[0] + b[2] for b in boxes) + round(width * 0.50))
    return rgb[:, left:right], left


def letter_strip(rgb, boxes):
    import cv2
    import numpy as np
    # ---------- 保留像素字符，R-B 对比把白字转黑、金色底转白 ----------
    contrast = np.clip((rgb[:, :, 0].astype(np.float32) - rgb[:, :, 2]) * 3.5, 0, 255).astype(np.uint8)
    strip = np.full((180, len(boxes) * 100, 3), 255, dtype=np.uint8)
    for index, (x, y, w, h) in enumerate(boxes):
        crop_w = w * 0.40
        crop_h = min(h * 0.75, w * 0.55)
        left, top = round(x + w / 2 - crop_w / 2), round(y + h / 2 - crop_h / 2)
        crop = contrast[top:round(top + crop_h), left:round(left + crop_w)]
        if crop.size == 0:
            return None
        scaled_h = min(170, round(100 * crop.shape[0] / crop.shape[1]))
        scaled = cv2.resize(crop, (100, scaled_h), interpolation=cv2.INTER_CUBIC)
        top = (180 - scaled_h) // 2
        strip[top:top + scaled_h, index * 100:(index + 1) * 100] = scaled[:, :, None]
    return strip


def combine(fragments, recovered):
    # ---------- 实际补读字母替换同位置的正文误读；不替换选项内容 ----------
    for label in recovered:
        revised = []
        for fragment in fragments:
            overlap = abs(fragment.y - label.y) <= max(fragment.height, label.height)
            overlap &= fragment.x < label.x + label.width and fragment.x + fragment.width >= label.x - label.width
            if overlap:
                text = fragment.text.strip()
                if len(text) <= 3:
                    continue
                text = re.sub(r"^\s*[^\w]{0,3}[A-H0-9](?:[\s.．、:：)）]+|(?=[\u3400-\u9fff]))", "", text)
                fragment = Fragment(text, max(fragment.x, label.x + label.width * 1.2),
                                    fragment.y, fragment.width, fragment.height, fragment.confidence)
            if fragment.text:
                revised.append(fragment)
        fragments = revised + [label]
    # ---------- 居中字母归到右侧段落首行，长选项不按固定像素分行 ----------
    labels = [f for f in fragments if option_letter(f.text)]
    for label in labels:
        content = sorted([f for f in fragments if not option_letter(f.text) and
                          f.x >= label.x + label.width * 0.8 and f.x - label.x < max(150, label.width * 15)],
                         key=lambda f: f.y)
        if not content:
            continue
        index = min(range(len(content)), key=lambda i: abs(content[i].y - label.y))
        if abs(content[index].y - label.y) > max(content[index].height, label.height) * 2:
            continue
        while index:
            previous, current = content[index - 1], content[index]
            other_label = any(other is not label and previous.y - previous.height / 2 <= other.y <= current.y + current.height / 2 for other in labels)
            if current.y - previous.y >= max(previous.height, current.height) * 2 or other_label:
                break
            index -= 1
        label.y = content[index].y
    fragments.sort(key=lambda f: (f.y, f.x))
    grouped = []
    for fragment in fragments:
        if grouped and abs(grouped[-1][0].y - fragment.y) < min(grouped[-1][0].height, fragment.height) * 0.55:
            grouped[-1].append(fragment)
        else:
            grouped.append([fragment])
    return grouped
