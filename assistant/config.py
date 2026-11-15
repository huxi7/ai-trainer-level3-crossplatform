# [INPUT]: 依赖标准库读取预设、本机 JSON 与应用资源路径。
# [OUTPUT]: 提供外观、答案时长与匹配 Settings、配置读写和统一日志入口。
# [POS]: assistant 的配置边界；日常运行不创建设置窗口。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
import json
import logging
import math
import os
import sys
from dataclasses import asdict, dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_NAME = "三级助手"
VERSION = "0.3.1"


def resources():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def settings_dir():
    override = os.environ.get("TRAINER_SETTINGS_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "TrainerLevel3"
    return Path.home() / "Library/Application Support/TrainerLevel3"


@dataclass
class Settings:
    font_size: int = 9
    transparency: int = 85
    capture_mode: str = "window"
    enabled: bool = True
    startup_notice: bool = True
    threshold_percent: int = 60
    show_score: bool = False
    answer_duration: float = 2.5

    def validate(self):
        self.font_size = min(32, max(8, int(self.font_size)))
        self.transparency = min(95, max(0, int(self.transparency)))
        self.capture_mode = "screen" if self.capture_mode == "screen" else "window"
        self.enabled = bool(self.enabled)
        self.startup_notice = bool(self.startup_notice)
        self.threshold_percent = min(95, max(40, int(self.threshold_percent)))
        self.show_score = bool(self.show_score)
        duration = float(self.answer_duration)
        self.answer_duration = round(min(5.0, max(0.2, duration)), 1) if math.isfinite(duration) else 2.5
        return self

    @property
    def opacity(self):
        return 1 - self.transparency / 100


def load_settings():
    values = {}
    for path in (resources() / "defaults.json", settings_dir() / "settings.json"):
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                values.update({k: v for k, v in payload.items() if k in Settings.__dataclass_fields__})
        except (OSError, ValueError, TypeError):
            logging.getLogger(__name__).warning("配置文件无法读取：%s", path)
    try:
        return Settings(**values).validate()
    except (ValueError, TypeError):
        logging.getLogger(__name__).warning("配置值无效，采用预设")
        return Settings()


def save_settings(settings):
    folder = settings_dir()
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / "settings.json.tmp"
    temporary.write_text(json.dumps(asdict(settings.validate()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(folder / "settings.json")


def configure_logging():
    folder = settings_dir()
    folder.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(folder / "assistant.log", maxBytes=512_000, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
