# [INPUT]: 依赖本机配置、只读题库、OCR、原生边界与 Qt 界面。
# [OUTPUT]: 提供单实例助手、设置/退出、实时截图检查与可选本机诊断。
# [POS]: assistant 的流程入口；监听轻量运行，截图识别在单个工作线程执行。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
import argparse
import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from .config import APP_NAME, VERSION, configure_logging, load_settings, resources, settings_dir

logger = logging.getLogger(__name__)


def entry():
    parser = argparse.ArgumentParser(description="离线截图题库助手")
    parser.add_argument("--configure", action="store_true")
    parser.add_argument("--quit", action="store_true")
    parser.add_argument("--permissions", action="store_true")
    parser.add_argument("--check-image", type=Path)
    parser.add_argument("--check-text", type=Path)
    parser.add_argument("--check-live", choices=['window', 'screen'])
    parser.add_argument("--window-id", type=int)
    parser.add_argument("--diagnostics", action='store_true', help='仅保留最近一次右键诊断截图与文字')
    parser.add_argument("--self-check", action='store_true', help='运行本机离线 OCR 回归检查')
    args = parser.parse_args()
    configure_logging()
    if args.self_check:
        from .validation import run_checks
        destination = settings_dir() / 'self-check.json'
        report = run_checks(resources(), destination)
        print(json.dumps({'passed': report['passed'], 'total': report['total'], 'all_passed': report['all_passed'], 'report': str(destination)}, ensure_ascii=False))
        if sys.platform == 'win32':
            import ctypes
            message = f"本机 OCR 检查：{report['passed']}/{report['total']} 个图像结果符合预期。\n详细记录：{destination}"
            ctypes.windll.user32.MessageBoxW(None, message, '本机识别检查', 0x40 if report['all_passed'] else 0x10)
        return 0 if report['all_passed'] else 1
    if args.check_image or args.check_text or args.check_live:
        from .bank import Bank
        from .ocr import OCR, Row
        from .matching import inspect
        start = time.perf_counter()
        ocr = OCR(resources() / "models")
        settings = load_settings()
        if args.check_image:
            from PIL import Image
            with Image.open(args.check_image) as image:
                rows = ocr.rows(image)
        elif args.check_text:
            rows = [Row(line) for line in args.check_text.read_text(encoding="utf-8").splitlines()]
        else:
            from .native import platform, Click
            native = platform()
            click = native.cursor_click()
            if args.window_id:
                click = Click(click.x, click.y, args.window_id, click.display_bounds)
            image = native.capture(click, args.check_live)
            rows = ocr.rows(image)
            if args.diagnostics:
                folder = settings_dir() / 'diagnostics'
                folder.mkdir(exist_ok=True)
                image.save(folder / 'last.png')
        report = inspect(rows, Bank(resources() / "bank.sqlite3"), settings.threshold_percent / 100)
        print(json.dumps({"answer": report.display(), "question_id": report.result.question_id if report.result else None,
                          "reason": report.reason, "percent": report.percent, "layout": ocr.last_layout,
                          "seconds": round(time.perf_counter() - start, 3), "rows": [row.text for row in rows]}, ensure_ascii=False))
        return 0
    from .native import platform
    if args.permissions:
        status = platform().permissions()
        print(json.dumps({"screen": status.screen, "input": status.input}, ensure_ascii=False))
        return 0

    # ---------- GUI 库仅在后台助手或独立设置入口加载 ----------
    from PySide6.QtCore import QLockFile, QObject, QPoint, QRunnable, QThreadPool, QTimer, Signal, Slot
    from PySide6.QtGui import QCursor
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import QApplication, QMessageBox
    from .ui import FloatingAnswer, SettingsDialog

    application = QApplication(sys.argv[:1])
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(VERSION)
    application.setQuitOnLastWindowClosed(False)
    identity = hashlib.sha256(str(settings_dir()).encode()).hexdigest()[:16]
    server_name = "TrainerLevel3-" + identity
    socket = QLocalSocket()
    socket.connectToServer(server_name)
    command = "configure" if args.configure else "quit" if args.quit else "status"
    if socket.waitForConnected(350):
        socket.write(command.encode())
        socket.flush()
        socket.waitForBytesWritten(350)
        socket.waitForReadyRead(500)
        return 0
    if args.quit:
        return 0

    settings = load_settings()
    native = platform()
    overlay = FloatingAnswer(settings, native)
    if args.configure:
        dialog = SettingsDialog(settings, native, overlay)
        dialog.finished.connect(application.quit)
        dialog.show()
        return application.exec()

    # ---------- 用户目录锁避免同时双击启动两个监听进程 ----------
    instance_lock = QLockFile(str(settings_dir() / "instance.lock"))
    instance_lock.setStaleLockTime(0)
    if not instance_lock.tryLock(0):
        logger.info("已有助手实例正在启动")
        return 0

    from .bank import Bank
    from .ocr import OCR
    from .matching import Report, inspect
    bank = Bank(resources() / "bank.sqlite3")
    ocr = OCR(resources() / "models")

    class WorkerSignals(QObject):
        finished = Signal(object, QPoint, float)

    class Recognition(QRunnable):
        def __init__(self, click, point, mode, threshold):
            super().__init__()
            self.click, self.point, self.mode = click, point, mode
            self.threshold = threshold
            self.signals = WorkerSignals()

        @Slot()
        def run(self):
            start = time.perf_counter()
            report = Report(reason='截图未完成')
            stage = '截图'
            try:
                image = native.capture(self.click, self.mode)
                stage = 'OCR'
                rows = ocr.rows(image)
                stage = '匹配'
                report = inspect(rows, bank, self.threshold)
                if args.diagnostics:
                    folder = settings_dir() / 'diagnostics'
                    folder.mkdir(exist_ok=True)
                    image.save(folder / 'last.png')
                    (folder / 'last.json').write_text(json.dumps({
                        'window': self.click.window, 'mode': self.mode, 'layout': ocr.last_layout,
                        'answer': report.display(), 'reason': report.reason, 'percent': report.percent,
                        'rows': [row.__dict__ for row in rows]}, ensure_ascii=False, indent=2), encoding='utf-8')
            except Exception:
                logger.exception("截图或匹配失败")
                report = Report(reason=stage + '失败，详情见本机日志')
            self.signals.finished.emit(report, self.point, time.perf_counter() - start)

    class Controller(QObject):
        clicked = Signal(object)

        def __init__(self):
            super().__init__()
            self.busy, self.last_click = False, 0
            self.dialog = self.worker = None
            self.last_report = None
            self.connections = []
            self.pool = QThreadPool(self)
            self.pool.setMaxThreadCount(1)
            self.server = QLocalServer(self)
            self.server.setSocketOptions(QLocalServer.UserAccessOption)
            # 连接失败后才清除本机用户遗留的端点。
            QLocalServer.removeServer(server_name)
            if not self.server.listen(server_name):
                raise RuntimeError("助手的本机通信入口无法启动")
            self.server.newConnection.connect(self.accept_connection)
            self.clicked.connect(self.right_clicked)
            application.aboutToQuit.connect(native.stop)
            application.aboutToQuit.connect(self.server.close)

        def accept_connection(self):
            connection = self.server.nextPendingConnection()
            self.connections.append(connection)

            def read():
                message = bytes(connection.readAll()).decode("utf-8", errors="replace")
                connection.write(b"ok")
                connection.flush()
                if message == "quit":
                    application.quit()
                elif message == "configure":
                    self.configure()
                else:
                    overlay.show_message("应用已启动", startup=True)
                connection.disconnectFromServer()
                self.connections.remove(connection)
                connection.deleteLater()
            connection.readyRead.connect(read)
            if connection.bytesAvailable():
                read()

        def configure(self, permission_required=False):
            if self.dialog is None:
                self.dialog = SettingsDialog(settings, native, overlay, permission_required=permission_required)
            self.dialog.show()
            if self.last_report:
                report = self.last_report
                detail = report.reason + (f'（最低匹配度 {report.percent}%）' if report.percent is not None else '')
                self.dialog.last_reason.setText('最近识别依据：' + detail)
            self.dialog.raise_()
            self.dialog.activateWindow()

        @Slot(object)
        def right_clicked(self, click):
            now = time.monotonic()
            if not settings.enabled or self.busy or now - self.last_click < 0.7:
                return
            if self.dialog is not None and self.dialog.isVisible():
                return
            self.busy, self.last_click = True, now
            overlay.hide()
            logger.info('收到右键；窗口=%s；范围=%s', click.window, settings.capture_mode)
            self.worker = Recognition(click, QPoint(QCursor.pos()), settings.capture_mode, settings.threshold_percent / 100)
            self.worker.signals.finished.connect(self.recognized)
            self.pool.start(self.worker)

        @Slot(object, QPoint, float)
        def recognized(self, report, point, seconds):
            self.busy = False
            self.last_report = report
            logger.info('右键识别完成；耗时 %.3f 秒；原因=%s；最低匹配度=%s；版面=%s', seconds, report.reason, report.percent, ocr.last_layout)
            overlay.show_message(report.display(settings.show_score), point)
            self.worker = None

    controller = Controller()
    application._controller = controller
    status = native.permissions()
    logger.info("启动；屏幕录制=%s；输入监听=%s；题库=%s", status.screen, status.input, len(bank.questions))
    if not status.ready:
        controller.configure(permission_required=True)
        controller.dialog.finished.connect(application.quit)
    else:
        try:
            native.start(controller.clicked.emit)
        except Exception as error:
            logger.exception("右键监听启动失败")
            QMessageBox.warning(None, "助手未能开始识别", str(error))
            return 1
        if settings.startup_notice:
            QTimer.singleShot(0, lambda: overlay.show_message("应用启动", startup=True, duration=4000))
    return application.exec()
