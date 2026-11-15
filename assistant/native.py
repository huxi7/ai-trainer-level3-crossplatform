# [INPUT]: 依赖标准库选择操作系统；平台模块提供监听和截图。
# [OUTPUT]: 提供 Click、Permissions 和平台工厂。
# [POS]: assistant 的原生接口边界；共用流程不依赖 Win32 或 AppKit。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Click:
    x: float
    y: float
    window: int = 0
    display_bounds: tuple = ()


@dataclass(frozen=True)
class Permissions:
    screen: bool
    input: bool

    @property
    def ready(self):
        return self.screen and self.input


def platform():
    if sys.platform == "darwin":
        from .macos import Platform
    elif sys.platform == "win32":
        from .windows import Platform
    else:
        raise RuntimeError("本运行包支持 macOS 和 Windows")
    return Platform()
