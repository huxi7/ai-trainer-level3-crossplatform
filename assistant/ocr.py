# [INPUT]: 依赖本地 mobile ONNX 模型与共用版面定位、字母增强规则。
# [OUTPUT]: 提供带位置、字高、置信度的 Row 和惰性 RapidOCR 引擎。
# [POS]: assistant 的统一视觉入口；两平台均识别实际像素，不推断源字母。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
from dataclasses import dataclass
from pathlib import Path
import os
import re
import sys
from .layout import Fragment, buttons, combine, letter_strip, question_column


@dataclass(frozen=True)
class Row:
    text: str
    y: float = 0
    confidence: float = 1
    x: float = 0
    height: float = 0


class OCR:
    def __init__(self, model_dir):
        self.model_dir = Path(model_dir)
        self.engine = None
        self.last_layout = {}

    def _load(self):
        if self.engine is not None:
            return
        from rapidocr import OCRVersion, RapidOCR
        required = ('det.onnx', 'rec.onnx', 'cls.onnx', 'keys.txt')
        if any(not (self.model_dir / name).is_file() for name in required):
            raise FileNotFoundError('OCR 模型缺失，请完整解压运行包')
        self.engine = RapidOCR(params={
            'Det.model_path': str(self.model_dir / 'det.onnx'),
            'Rec.model_path': str(self.model_dir / 'rec.onnx'),
            'Cls.model_path': str(self.model_dir / 'cls.onnx'),
            'Rec.rec_keys_path': str(self.model_dir / 'keys.txt'),
            'Det.ocr_version': OCRVersion.PPOCRV5,
            'Rec.ocr_version': OCRVersion.PPOCRV5,
            'Det.limit_type': 'max', 'Det.limit_side_len': 1920,
            'Global.max_side_len': 2560, 'Global.use_cls': False,
            'Global.log_level': 'error',
            'Global.font_path': str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/segoeui.ttf') if sys.platform == 'win32' else '/System/Library/Fonts/Supplemental/Arial.ttf',
            'EngineConfig.onnxruntime.intra_op_num_threads': 2,
            'EngineConfig.onnxruntime.inter_op_num_threads': 1,
        })

    def _letters(self, rgb, boxes):
        strip = letter_strip(rgb, boxes)
        if strip is None:
            return []
        result = self.engine(strip, use_det=False, use_cls=False, use_rec=True)
        text = ''.join(result.txts or ()).upper()
        text = re.sub(r'\s+', '', text)
        # ---------- 字符数须等于图像槽位数；字母不要求 ABC 顺序 ----------
        if len(text) != len(boxes) or re.fullmatch(r'[A-H]+', text) is None:
            return []
        confidence = min(result.scores or [0])
        if confidence < 0.55:
            return []
        labels = []
        for letter, (x, y, w, h) in zip(text, boxes):
            size = min(h * 0.5, w * 0.3)
            labels.append(Fragment(letter, x + w / 2 - size * 0.4, y + h / 2,
                                   size * 0.8, size, confidence))
        return labels

    def rows(self, image):
        self._load()
        import numpy as np
        if isinstance(image, (str, Path)):
            from PIL import Image
            with Image.open(image) as source:
                image = source.convert('RGB')
        if hasattr(image, 'convert'):
            rgb = np.asarray(image.convert('RGB')).copy()
        else:
            rgb = np.asarray(image)[:, :, ::-1].copy()
        boxes = buttons(rgb)
        cropped, left = question_column(rgb, boxes)
        result = self.engine(cropped[:, :, ::-1].copy(), use_det=True, use_cls=False, use_rec=True, box_thresh=0.3)
        recovered = self._letters(rgb, boxes) if len(boxes) >= 2 else []
        self.last_layout = {'input_size': [rgb.shape[1], rgb.shape[0]],
                            'ocr_size': [cropped.shape[1], cropped.shape[0]],
                            'button_count': len(boxes), 'read_letters': ''.join(f.text for f in recovered)}
        if result.boxes is None or result.txts is None:
            return []
        fragments = []
        for box, text, score in zip(result.boxes, result.txts, result.scores):
            if text.strip():
                fragments.append(Fragment(text, float(box[:, 0].min()) + left,
                                          float(box[:, 1].mean()), float(box[:, 0].max() - box[:, 0].min()),
                                          float(box[:, 1].max() - box[:, 1].min()), float(score)))
        grouped = combine(fragments, recovered)
        return [Row(' '.join(f.text for f in sorted(row, key=lambda f: f.x)), row[0].y,
                    min(f.confidence for f in row), min(f.x for f in row), max(f.height for f in row))
                for row in grouped]
