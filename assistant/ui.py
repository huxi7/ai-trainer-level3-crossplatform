# [INPUT]: 依赖 Qt 主线程绘图、本机配置与平台权限接口。
# [OUTPUT]: 提供定时透明浮字、时长/外观/匹配设置和最近拒答原因。
# [POS]: assistant 的视觉边界；后台识别通过信号请求主线程更新。
# [PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
import logging
import sys
from PySide6.QtCore import QPoint, QTimer, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontMetrics, QPainter, QCursor
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QGroupBox,
                              QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget)
from .config import save_settings

logger = logging.getLogger(__name__)


class FloatingAnswer(QWidget):
    def __init__(self, settings, native=None):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
                         Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.settings, self.native = settings, native
        self.text, self.startup = "", False
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        if sys.platform == "darwin":
            self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def font_for_message(self):
        font = QFont(QApplication.font())
        font.setPointSizeF(14 if self.startup else self.settings.font_size)
        font.setWeight(QFont.Normal if self.startup else QFont.Thin)
        return font

    def show_message(self, text, point=None, startup=False, duration=None):
        self.text, self.startup = text, startup
        point = QPoint(point or QCursor.pos())
        metrics = QFontMetrics(self.font_for_message())
        width, height = metrics.horizontalAdvance(text) + 8, metrics.height() + 4
        self.resize(width, height)
        screen = QApplication.screenAt(point) or QApplication.primaryScreen()
        frame = screen.availableGeometry()
        x = max(frame.left(), min(point.x() + 12, frame.right() - width))
        y = max(frame.top(), min(point.y() - height - 12, frame.bottom() - height))
        self.move(x, y)
        self.show()
        if self.native and QApplication.platformName() != "offscreen":
            self.native.prepare_overlay(self)
        self.update()
        milliseconds = duration if duration is not None else (4000 if startup else round(self.settings.answer_duration * 1000))
        self.timer.start(milliseconds)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setFont(self.font_for_message())
        color = QColor(255, 149, 0)
        color.setAlphaF(0.9 if self.startup else self.settings.opacity)
        painter.setPen(color)
        painter.drawText(self.rect().adjusted(2, 2, -2, -2), Qt.AlignCenter, self.text)


class SettingsDialog(QDialog):
    def __init__(self, settings, native, overlay, on_change=None, permission_required=False):
        super().__init__()
        self.settings, self.native, self.overlay = settings, native, overlay
        self.on_change = on_change
        self.setWindowTitle("首次权限配置" if permission_required else "助手设置")
        self.setMinimumWidth(420)
        self.persist = QTimer(self)
        self.persist.setSingleShot(True)
        self.persist.timeout.connect(self._save)
        layout = QVBoxLayout(self)
        intro = QLabel("设置保存在本机。关闭后不显示菜单栏、托盘或主窗口。\n在题目位置右键，鼠标旁短暂显示答案。")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.size_label = QLabel()
        self.size_slider = self._slider(layout, self.size_label, 8, 32, settings.font_size)
        self.alpha_label = QLabel()
        self.alpha_slider = self._slider(layout, self.alpha_label, 0, 95, settings.transparency)
        layout.addWidget(QLabel("答案显示时长（出现后多久消失）"))
        self.duration_control = QDoubleSpinBox()
        self.duration_control.setRange(0.2, 5.0)
        self.duration_control.setSingleStep(0.1)
        self.duration_control.setDecimals(1)
        self.duration_control.setSuffix(" 秒")
        self.duration_control.setAccessibleName("答案显示时长")
        self.duration_control.setValue(settings.answer_duration)
        layout.addWidget(self.duration_control)
        self.mode = QComboBox()
        self.mode.addItem("截取右键所在窗口", "window")
        self.mode.addItem("截取鼠标所在屏幕", "screen")
        self.mode.setCurrentIndex(1 if settings.capture_mode == "screen" else 0)
        layout.addWidget(QLabel("截图范围"))
        layout.addWidget(self.mode)
        self.enabled = QCheckBox("启用右键识别")
        self.enabled.setChecked(settings.enabled)
        self.notice = QCheckBox("启动时短暂显示“应用启动”")
        self.notice.setChecked(settings.startup_notice)
        layout.addWidget(self.enabled)
        layout.addWidget(self.notice)
        self.threshold_label = QLabel()
        self.threshold_slider = self._slider(layout, self.threshold_label, 40, 95, settings.threshold_percent)
        self.score_toggle = QCheckBox("显示文字匹配度（不是答对概率）")
        self.score_toggle.setChecked(settings.show_score)
        layout.addWidget(self.score_toggle)
        self.last_reason = QLabel("最近识别依据：尚未识别")
        self.last_reason.setWordWrap(True)
        layout.addWidget(self.last_reason)
        if sys.platform == "darwin":
            group = QGroupBox("这台 Mac 的权限")
            permissions_layout = QVBoxLayout(group)
            self.permission_label = QLabel()
            permissions_layout.addWidget(self.permission_label)
            for label, kind in (("授权屏幕录制", "screen"), ("授权输入监听", "input")):
                button = QPushButton(label)
                button.clicked.connect(lambda checked=False, value=kind: self._permission(value))
                permissions_layout.addWidget(button)
            note = QLabel("在系统设置中允许“三级助手”。授权后退出并重新打开主应用。\n这些授权不能从另一台电脑复制过来。")
            note.setWordWrap(True)
            permissions_layout.addWidget(note)
            layout.addWidget(group)
            self._refresh_permissions()
        footer = QHBoxLayout()
        preview = QPushButton("预览浮字")
        preview.clicked.connect(self._preview)
        done = QPushButton("保存并关闭")
        done.clicked.connect(self.accept)
        footer.addWidget(preview)
        footer.addStretch()
        footer.addWidget(done)
        layout.addLayout(footer)
        self.size_slider.valueChanged.connect(self._changed)
        self.alpha_slider.valueChanged.connect(self._changed)
        self.duration_control.valueChanged.connect(self._changed)
        self.mode.currentIndexChanged.connect(self._changed)
        self.enabled.toggled.connect(self._changed)
        self.notice.toggled.connect(self._changed)
        self.threshold_slider.valueChanged.connect(self._changed)
        self.score_toggle.toggled.connect(self._changed)
        self._labels()

    def _slider(self, layout, label, minimum, maximum, value):
        layout.addWidget(label)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        layout.addWidget(slider)
        return slider

    def _labels(self):
        self.size_label.setText(f"字号：{self.settings.font_size} pt")
        self.alpha_label.setText(f"透明度：{self.settings.transparency}%（越高越淡）")
        self.threshold_label.setText(f"最低文字匹配度：{self.settings.threshold_percent}%（默认 60%）")

    def _changed(self, *args):
        self.settings.font_size = self.size_slider.value()
        self.settings.transparency = self.alpha_slider.value()
        self.settings.answer_duration = self.duration_control.value()
        self.settings.capture_mode = self.mode.currentData()
        self.settings.enabled = self.enabled.isChecked()
        self.settings.startup_notice = self.notice.isChecked()
        self.settings.threshold_percent = self.threshold_slider.value()
        self.settings.show_score = self.score_toggle.isChecked()
        self._labels()
        self.persist.start(200)
        if self.on_change:
            self.on_change(self.settings)
        self._preview()

    def _preview(self):
        self.overlay.show_message("A", QCursor.pos() + QPoint(80, -25))

    def _save(self):
        try:
            save_settings(self.settings)
        except OSError:
            logger.exception("本机设置保存失败")

    def done(self, result):
        self.persist.stop()
        self._save()
        self.overlay.hide()
        super().done(result)

    def _refresh_permissions(self):
        status = self.native.permissions()
        self.permission_label.setText("屏幕录制：" + ("已允许" if status.screen else "未允许") +
                                      "　输入监听：" + ("已允许" if status.input else "未允许"))

    def _permission(self, kind):
        self.native.request_permission(kind)
        pane = "Privacy_ScreenCapture" if kind == "screen" else "Privacy_ListenEvent"
        QDesktopServices.openUrl(QUrl("x-apple.systempreferences:com.apple.preference.security?" + pane))
        QTimer.singleShot(300, self._refresh_permissions)
