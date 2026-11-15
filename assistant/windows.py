# [INPUT]: 依赖 Win32 低级鼠标钩子、窗口坐标与 GDI 截图。
# [OUTPUT]: 提供保留原菜单的右键事件、窗口截图与显示器截图。
# [POS]: assistant 的 Windows 原生边界；普通用户运行，不请求管理员权限。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
import ctypes as c
import threading
from ctypes import wintypes as w
from .native import Click, Permissions

user = c.WinDLL("user32", use_last_error=True)
gdi = c.WinDLL("gdi32", use_last_error=True)
kernel = c.WinDLL("kernel32", use_last_error=True)
LRESULT = c.c_ssize_t
HOOKPROC = c.WINFUNCTYPE(LRESULT, c.c_int, w.WPARAM, w.LPARAM)


class MouseEvent(c.Structure):
    _fields_ = [("pt", w.POINT), ("mouseData", w.DWORD), ("flags", w.DWORD),
                ("time", w.DWORD), ("extra", c.c_size_t)]


class MonitorInfo(c.Structure):
    _fields_ = [("size", w.DWORD), ("monitor", w.RECT), ("work", w.RECT), ("flags", w.DWORD)]


class BitmapHeader(c.Structure):
    _fields_ = [("size", w.DWORD), ("width", w.LONG), ("height", w.LONG),
                ("planes", w.WORD), ("bitCount", w.WORD), ("compression", w.DWORD),
                ("imageSize", w.DWORD), ("xppm", w.LONG), ("yppm", w.LONG),
                ("used", w.DWORD), ("important", w.DWORD)]


class BitmapInfo(c.Structure):
    _fields_ = [("header", BitmapHeader), ("colors", w.DWORD * 3)]


# ---------- 64 位句柄须声明签名，禁止 ctypes 截断指针 ----------
user.SetWindowsHookExW.argtypes = [c.c_int, HOOKPROC, w.HINSTANCE, w.DWORD]
user.SetWindowsHookExW.restype = w.HANDLE
user.CallNextHookEx.argtypes = [w.HANDLE, c.c_int, w.WPARAM, w.LPARAM]
user.CallNextHookEx.restype = LRESULT
user.UnhookWindowsHookEx.argtypes = [w.HANDLE]
user.WindowFromPoint.argtypes = [w.POINT]
user.WindowFromPoint.restype = w.HWND
user.GetAncestor.argtypes = [w.HWND, w.UINT]
user.GetAncestor.restype = w.HWND
user.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
user.MonitorFromPoint.argtypes = [w.POINT, w.DWORD]
user.MonitorFromPoint.restype = w.HANDLE
user.GetMonitorInfoW.argtypes = [w.HANDLE, c.POINTER(MonitorInfo)]
user.GetDC.argtypes = [w.HWND]
user.GetDC.restype = w.HDC
user.ReleaseDC.argtypes = [w.HWND, w.HDC]
user.PrintWindow.argtypes = [w.HWND, w.HDC, w.UINT]
user.PostThreadMessageW.argtypes = [w.DWORD, w.UINT, w.WPARAM, w.LPARAM]
user.GetMessageW.argtypes = [c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT]
user.PeekMessageW.argtypes = [c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT]
user.GetCursorPos.argtypes = [c.POINTER(w.POINT)]
user.TranslateMessage.argtypes = [c.POINTER(w.MSG)]
user.DispatchMessageW.argtypes = [c.POINTER(w.MSG)]
user.DispatchMessageW.restype = LRESULT
kernel.GetModuleHandleW.argtypes = [w.LPCWSTR]
kernel.GetModuleHandleW.restype = w.HMODULE
kernel.GetCurrentThreadId.restype = w.DWORD
gdi.CreateCompatibleDC.argtypes = [w.HDC]
gdi.CreateCompatibleDC.restype = w.HDC
gdi.CreateCompatibleBitmap.argtypes = [w.HDC, c.c_int, c.c_int]
gdi.CreateCompatibleBitmap.restype = w.HBITMAP
gdi.SelectObject.argtypes = [w.HDC, w.HANDLE]
gdi.SelectObject.restype = w.HANDLE
gdi.DeleteObject.argtypes = [w.HANDLE]
gdi.DeleteDC.argtypes = [w.HDC]
gdi.BitBlt.argtypes = [w.HDC, c.c_int, c.c_int, c.c_int, c.c_int, w.HDC, c.c_int, c.c_int, w.DWORD]
gdi.GetDIBits.argtypes = [w.HDC, w.HBITMAP, w.UINT, w.UINT, c.c_void_p, c.POINTER(BitmapInfo), w.UINT]


class Platform:
    def __init__(self):
        self._thread = self._thread_id = self._hook = self._callback = None
        # Qt 和原生截图均使用物理坐标，避免 Win10/11 125%/150% 缩放截错范围。
        if hasattr(user, 'SetProcessDpiAwarenessContext'):
            user.SetProcessDpiAwarenessContext.argtypes = [w.HANDLE]
            user.SetProcessDpiAwarenessContext.restype = w.BOOL
            user.SetProcessDpiAwarenessContext(w.HANDLE(-4))

    def permissions(self):
        return Permissions(True, True)

    def request_permission(self, kind):
        return None

    def _click(self, point):
        window = user.GetAncestor(user.WindowFromPoint(point), 2)
        rect = w.RECT()
        if not window or not user.GetWindowRect(window, c.byref(rect)) or rect.right - rect.left <= 350 or rect.bottom - rect.top <= 250:
            window = 0
        monitor = user.MonitorFromPoint(point, 2)
        info = MonitorInfo(size=c.sizeof(MonitorInfo))
        bounds = ()
        if user.GetMonitorInfoW(monitor, c.byref(info)):
            r = info.monitor
            bounds = (r.left, r.top, r.right - r.left, r.bottom - r.top)
        return Click(point.x, point.y, int(window or 0), bounds)

    def cursor_click(self):
        point = w.POINT()
        if not user.GetCursorPos(c.byref(point)):
            raise RuntimeError('无法读取鼠标位置')
        return self._click(point)

    def start(self, on_click):
        ready = threading.Event()
        errors = []

        @HOOKPROC
        def callback(code, message, parameter):
            if code >= 0 and message == 0x0204:
                event = c.cast(parameter, c.POINTER(MouseEvent)).contents
                try:
                    on_click(self._click(event.pt))
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception("右键事件读取失败")
            return user.CallNextHookEx(self._hook, code, message, parameter)

        self._callback = callback

        def run():
            self._thread_id = kernel.GetCurrentThreadId()
            self._hook = user.SetWindowsHookExW(14, callback, kernel.GetModuleHandleW(None), 0)
            if not self._hook:
                errors.append(c.WinError(c.get_last_error()))
                ready.set()
                return
            # 提前创建消息队列，确保退出消息能送达。
            msg = w.MSG()
            user.PeekMessageW(c.byref(msg), None, 0, 0, 0)
            ready.set()
            try:
                while user.GetMessageW(c.byref(msg), None, 0, 0) > 0:
                    user.TranslateMessage(c.byref(msg))
                    user.DispatchMessageW(c.byref(msg))
            finally:
                user.UnhookWindowsHookEx(self._hook)

        self._thread = threading.Thread(target=run, daemon=True, name="RightClickListener")
        self._thread.start()
        if not ready.wait(2):
            raise RuntimeError("右键监听启动超时")
        if errors:
            raise errors[0]

    def stop(self):
        if self._thread_id:
            user.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
        if self._thread:
            self._thread.join(timeout=1)

    def capture(self, click, mode):
        from PIL import Image, ImageStat
        if mode == "window":
            rect = w.RECT()
            if not click.window or not user.GetWindowRect(click.window, c.byref(rect)):
                raise RuntimeError("未找到题目窗口")
            left, top, width, height = rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        else:
            if not click.display_bounds:
                raise RuntimeError("未找到鼠标所在显示器")
            left, top, width, height = map(int, click.display_bounds)
        if width <= 0 or height <= 0 or width * height > 40_000_000:
            raise RuntimeError("截图范围无效")
        screen = user.GetDC(None)
        memory = gdi.CreateCompatibleDC(screen)
        bitmap = gdi.CreateCompatibleBitmap(screen, width, height)
        if not screen or not memory or not bitmap:
            if bitmap:
                gdi.DeleteObject(bitmap)
            if memory:
                gdi.DeleteDC(memory)
            if screen:
                user.ReleaseDC(None, screen)
            raise RuntimeError("系统无法创建截图资源")
        previous = gdi.SelectObject(memory, bitmap)
        try:
            captured = mode == "window" and user.PrintWindow(click.window, memory, 2)
            if not captured:
                if not gdi.BitBlt(memory, 0, 0, width, height, screen, left, top, 0x00CC0020 | 0x40000000):
                    raise RuntimeError("桌面截图失败")
            header = BitmapHeader(size=c.sizeof(BitmapHeader), width=width, height=-height, planes=1, bitCount=32)
            info = BitmapInfo(header=header)
            pixels = c.create_string_buffer(width * height * 4)
            gdi.SelectObject(memory, previous)
            previous = None
            if gdi.GetDIBits(screen, bitmap, 0, height, pixels, c.byref(info), 0) != height:
                raise RuntimeError("截图像素读取失败")
            image = Image.frombytes("RGB", (width, height), pixels.raw, "raw", "BGRX")
            if max(ImageStat.Stat(image).stddev) < 1:
                raise RuntimeError("窗口返回空白图像，改用屏幕截图模式")
            return image
        finally:
            if previous:
                gdi.SelectObject(memory, previous)
            gdi.DeleteObject(bitmap)
            gdi.DeleteDC(memory)
            user.ReleaseDC(None, screen)

    def prepare_overlay(self, widget):
        user.SetWindowPos.argtypes = [w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT]
        user.SetWindowPos(w.HWND(int(widget.winId())), w.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
