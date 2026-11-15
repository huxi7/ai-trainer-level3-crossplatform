# [INPUT]: 依赖 macOS Quartz、AppKit 与系统 screencapture。
# [OUTPUT]: 提供监听权限、右键事件、窗口或显示器截图。
# [POS]: assistant 的 Mac 原生边界；监听不吞事件，截图避开右键菜单。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
import logging
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from .native import Click, Permissions

logger = logging.getLogger(__name__)


class Platform:
    def __init__(self):
        import Quartz
        self.q = Quartz
        self._port = self._loop = self._thread = None
        self._callback = None

    def permissions(self):
        return Permissions(bool(self.q.CGPreflightScreenCaptureAccess()),
                           bool(self.q.CGPreflightListenEventAccess()))

    def request_permission(self, kind):
        if kind == "screen":
            self.q.CGRequestScreenCaptureAccess()
        else:
            self.q.CGRequestListenEventAccess()

    def _click(self, event):
        q = self.q
        point = q.CGEventGetLocation(event)
        window = 0
        windows = q.CGWindowListCopyWindowInfo(q.kCGWindowListOptionOnScreenOnly | q.kCGWindowListExcludeDesktopElements, q.kCGNullWindowID) or []
        for info in windows:
            if info.get(q.kCGWindowLayer) != 0 or info.get(q.kCGWindowOwnerPID) == os.getpid():
                continue
            bounds = info.get(q.kCGWindowBounds, {})
            x, y = bounds.get("X", 0), bounds.get("Y", 0)
            width, height = bounds.get("Width", 0), bounds.get("Height", 0)
            if width > 350 and height > 250 and x <= point.x < x + width and y <= point.y < y + height:
                window = int(info[q.kCGWindowNumber])
                break
        display_bounds = ()
        error, displays, count = q.CGGetActiveDisplayList(32, None, None)
        if not error:
            for display in displays[:count]:
                rect = q.CGDisplayBounds(display)
                x, y, width, height = rect.origin.x, rect.origin.y, rect.size.width, rect.size.height
                if x <= point.x < x + width and y <= point.y < y + height:
                    display_bounds = (x, y, width, height)
                    break
        return Click(point.x, point.y, window, display_bounds)

    def cursor_click(self):
        return self._click(self.q.CGEventCreate(None))

    def start(self, on_click):
        ready = threading.Event()
        errors = []
        q = self.q

        def callback(proxy, event_type, event, refcon):
            if event_type in (q.kCGEventTapDisabledByTimeout, q.kCGEventTapDisabledByUserInput):
                q.CGEventTapEnable(self._port, True)
            elif event_type == q.kCGEventRightMouseDown:
                try:
                    on_click(self._click(event))
                except Exception:
                    logger.exception("右键事件读取失败")
            return event

        self._callback = callback

        def run():
            try:
                self._port = q.CGEventTapCreate(q.kCGSessionEventTap, q.kCGHeadInsertEventTap,
                                               q.kCGEventTapOptionListenOnly,
                                               1 << q.kCGEventRightMouseDown, callback, None)
                if self._port is None:
                    raise PermissionError("输入监听尚未生效，请授权后重启助手")
                source = q.CFMachPortCreateRunLoopSource(None, self._port, 0)
                self._loop = q.CFRunLoopGetCurrent()
                q.CFRunLoopAddSource(self._loop, source, q.kCFRunLoopCommonModes)
                q.CGEventTapEnable(self._port, True)
                ready.set()
                q.CFRunLoopRun()
            except Exception as error:
                errors.append(error)
                ready.set()
        self._thread = threading.Thread(target=run, daemon=True, name="RightClickListener")
        self._thread.start()
        if not ready.wait(2):
            raise RuntimeError("右键监听启动超时")
        if errors:
            raise errors[0]

    def stop(self):
        if self._port is not None:
            self.q.CGEventTapEnable(self._port, False)
        if self._loop is not None:
            self.q.CFRunLoopStop(self._loop)
        if self._thread is not None:
            self._thread.join(timeout=1)

    def capture(self, click, mode):
        if not self.permissions().screen:
            raise PermissionError("屏幕录制尚未授权")
        from PIL import Image
        command = ["/usr/sbin/screencapture", "-x", "-o"]
        if mode == "window":
            if not click.window:
                raise RuntimeError("未找到右键所在的题目窗口")
            command.extend(["-l", str(click.window)])
        else:
            if not click.display_bounds:
                raise RuntimeError("未找到鼠标所在显示器")
            command.append("-R" + ",".join(str(round(value)) for value in click.display_bounds))
        with tempfile.TemporaryDirectory(prefix="trainer-capture-") as folder:
            filename = Path(folder) / "frame.png"
            completed = subprocess.run(command + [str(filename)], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.PIPE, timeout=5)
            if completed.returncode != 0 or not filename.exists():
                raise RuntimeError("窗口截图失败，请检查屏幕录制授权并重启助手")
            with Image.open(filename) as image:
                return image.convert("RGB")

    def prepare_overlay(self, widget):
        import AppKit
        import objc
        view = objc.objc_object(c_void_p=int(widget.winId()))
        window = view.window()
        window.setLevel_(AppKit.NSScreenSaverWindowLevel)
        window.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces |
                                      AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary)
        window.setIgnoresMouseEvents_(True)
        window.setHasShadow_(False)
