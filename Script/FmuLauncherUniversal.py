import sys, os, json, time, threading, subprocess, re, socket, zipfile, base64, queue, ddm_pb2
import ctypes
from ctypes import wintypes
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QGridLayout, QLabel, QLineEdit, QPushButton, QFrame, QScrollArea, 
                             QTextEdit, QProgressBar, QCheckBox, QFileDialog, QTreeWidget, 
                             QTreeWidgetItem, QHeaderView, QDialog, QGraphicsDropShadowEffect, QMessageBox, QSizeGrip,
                             QTableWidget, QTableWidgetItem, QAbstractItemView, QColorDialog, QStackedWidget, QSlider, QComboBox,
                             QSizePolicy)
from PySide6.QtCore import Qt, QTimer, Signal, QSize, QRect, QPoint
from PySide6.QtGui import QFont, QColor, QIcon, QPainter, QBrush, QPen, QCursor, QTextCursor

APP_VERSION = "v26.0719.1055"

# ─── Resource Helpers ───
def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# 强制 Windows 任务栏显示图标
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FmuSolver.Launcher.V1")
except: pass

# ─── Windows Acrylic Blur API ───
class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t)
    ]

class ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_int),
        ("AnimationId", ctypes.c_int)
    ]

def set_blur_behind(hwnd):
    """Enable Windows Acrylic Blur behind the frameless window."""
    accent = ACCENT_POLICY()
    accent.AccentState = 3 # ACCENT_ENABLE_BLURBEHIND
    accent.GradientColor = 0x00FFFFFF
    data = WINDOWCOMPOSITIONATTRIBDATA()
    data.Attribute = 19 # WCA_ACCENT_POLICY
    data.SizeOfData = ctypes.sizeof(accent)
    data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
    try:
        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.pointer(data))
    except: pass

def disable_blur_behind(hwnd):
    """Disable acrylic blur while live-resizing to keep Windows resize responsive."""
    accent = ACCENT_POLICY()
    accent.AccentState = 0 # ACCENT_DISABLED
    accent.GradientColor = 0x00FFFFFF
    data = WINDOWCOMPOSITIONATTRIBDATA()
    data.Attribute = 19
    data.SizeOfData = ctypes.sizeof(accent)
    data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
    try:
        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.pointer(data))
    except: pass

# ─── Constants & Sequoia Colors ───
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

GUI_CONFIG_PATH = os.path.join(APP_DIR, "gui_config.json")

CONTROL_PORT = 8898

class AsyncRotatingFileLogger:
    """Bounded async file logger: keeps UI threads away from slow disk IO."""
    def __init__(self, path, max_bytes=10 * 1024 * 1024, backups=3, queue_size=2000, flush_interval=0.5, batch_size=100):
        self.path = path
        self.max_bytes = max(1024 * 1024, int(max_bytes))
        self.backups = max(1, int(backups))
        self.flush_interval = max(0.1, float(flush_interval))
        self.batch_size = max(1, int(batch_size))
        self.queue = queue.Queue(maxsize=max(10, int(queue_size)))
        self.stop_event = threading.Event()
        self.drop_count = 0
        self.thread = threading.Thread(target=self._loop, name="FmuSolverAsyncLog", daemon=True)
        self.thread.start()

    def log(self, line, important=False):
        text = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {line}\n"
        try:
            self.queue.put_nowait((text, important))
        except queue.Full:
            self.drop_count += 1
            if not important:
                return
            try:
                self.queue.get_nowait()
                try: self.queue.task_done()
                except Exception: pass
            except Exception:
                pass
            try:
                self.queue.put_nowait((text, important))
            except Exception:
                pass

    def close(self, timeout=2.0):
        self.stop_event.set()
        try: self.thread.join(timeout=timeout)
        except Exception: pass

    def _rotate_if_needed(self):
        try:
            if not os.path.exists(self.path) or os.path.getsize(self.path) <= self.max_bytes:
                return
            for idx in range(self.backups, 0, -1):
                src = f"{self.path}.{idx}"
                dst = f"{self.path}.{idx + 1}"
                if os.path.exists(dst):
                    try: os.remove(dst)
                    except Exception: pass
                if os.path.exists(src):
                    try: os.replace(src, dst)
                    except Exception: pass
            try: os.replace(self.path, f"{self.path}.1")
            except Exception: pass
        except Exception:
            pass

    def _loop(self):
        pending = []
        last_flush = time.time()
        while not self.stop_event.is_set() or not self.queue.empty() or pending:
            timeout = max(0.05, self.flush_interval - (time.time() - last_flush))
            try:
                item, _important = self.queue.get(timeout=timeout)
                pending.append(item)
                try: self.queue.task_done()
                except Exception: pass
                while len(pending) < self.batch_size:
                    try:
                        item, _important = self.queue.get_nowait()
                        pending.append(item)
                        try: self.queue.task_done()
                        except Exception: pass
                    except queue.Empty:
                        break
            except queue.Empty:
                pass
            if pending and (len(pending) >= self.batch_size or time.time() - last_flush >= self.flush_interval or self.stop_event.is_set()):
                try:
                    os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
                    self._rotate_if_needed()
                    if self.drop_count:
                        pending.insert(0, f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [LOG] dropped {self.drop_count} runtime log lines due to backpressure\n")
                        self.drop_count = 0
                    with open(self.path, "a", encoding="utf-8", buffering=1024 * 1024) as f:
                        f.writelines(pending)
                except Exception:
                    pass
                pending.clear()
                last_flush = time.time()

# Soft glass palette aligned to the reference dashboard
C_BG_START = "rgba(250, 252, 255, 220)"
C_BG_MID   = "rgba(250, 252, 255, 220)"
C_BG_END   = "rgba(250, 252, 255, 220)"
C_CARD     = "rgba(255, 255, 255, 228)"
C_ACCENT   = "#2F87F6"
C_SUCCESS  = "#28C840"
C_ERROR    = "#FF5B57"
C_WARNING  = "#FF9F0A"
C_TEXT     = "#15181E"
C_MUTED    = "#6B7280"
C_INPUT_BG = "rgba(241, 243, 247, 250)"
C_CONSOLE  = "#14171B"

# ─── Global QSS ───
APP_QSS = f"""
QMainWindow, QDialog {{
    background: transparent;
    color: {C_TEXT};
    font-family: 'SF Pro Display', 'Inter', 'PingFang SC', 'Microsoft YaHei UI', 'Segoe UI', sans-serif;
    font-size: 13px;
}}

QWidget#MainContainer {{
    background: rgba(240, 242, 246, 180);
    border: none;
    border-radius: 12px;
}}

QWidget#TitleBar {{
    background: transparent;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid rgba(255,255,255,80);
}}

QWidget#ContentStack {{
    background: transparent;
}}

QWidget#TabContainer {{
    background: transparent;
    border: none;
}}

QLabel#BrandLabel {{
    color: #111111;
    font-size: 15px;
    font-weight: 800;
}}

QLabel#VersionBadge {{
    color: #4B5563;
    background: rgba(255,255,255,150);
    border: 1px solid rgba(0,0,0,18);
    border-radius: 8px;
    padding: 2px 7px;
    font-size: 10px;
    font-weight: 800;
}}

QLabel#HeaderLabel {{
    color: #111111;
    font-size: 15px;
    font-weight: 800;
}}

QLabel#SubHeaderLabel {{
    color: #86868B;
    font-size: 11px;
    font-weight: 600;
}}

QLabel#StatusText {{
    color: #4B5563;
    font-size: 11px;
    font-weight: 700;
}}

QFrame#Card {{
    background: rgba(255, 255, 255, 200);
    border: 1px solid rgba(216, 221, 230, 235);
    border-radius: 14px;
}}

QFrame#SegTrack {{
    background: rgba(0, 0, 0, 15);
    border: 1px solid rgba(0, 0, 0, 8);
    border-radius: 17px;
}}
QPushButton#SegBtn {{
    background: transparent;
    color: rgba(60, 60, 67, 165);
    border: none;
    border-radius: 15px;
    padding: 0 14px;
    min-height: 32px;
    max-height: 32px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton#SegBtn:hover {{
    background: rgba(255, 255, 255, 80);
    color: rgba(60, 60, 67, 210);
}}
QPushButton#SegBtnActive {{
    background: rgba(255, 255, 255, 252);
    color: #111111;
    border: none;
    border-radius: 15px;
    padding: 0 14px;
    min-height: 32px;
    max-height: 32px;
    font-weight: 800;
    font-size: 13px;
}}

QLabel#Title {{
    color: #1D1D1F;
    font-size: 12pt;
    font-weight: 800;
}}

QLabel#Muted {{
    color: #86868B;
    font-size: 11px;
    font-weight: 600;
}}

QLabel#ParamLabel {{
    color: #86868B;
    font-size: 10px;
    font-weight: 600;
}}

QLineEdit#PathEdit {{
    background: rgba(0, 0, 0, 8);
    border: none;
    border-radius: 6px;
    color: #111827;
    font-family: 'SF Mono', 'Cascadia Mono', 'Consolas', monospace;
    font-size: 11px;
    font-weight: 600;
    min-height: 26px;
    max-height: 26px;
    padding: 0 10px;
}}
QLineEdit#ParamEdit {{
    background: rgba(0, 0, 0, 13);
    border: none;
    border-radius: 6px;
    color: #111827;
    font-family: 'SF Mono', 'Cascadia Mono', 'Consolas', monospace;
    font-size: 12px;
    font-weight: 600;
    min-height: 25px;
    max-height: 25px;
    padding: 0 10px;
}}
QLineEdit#ParamEdit:focus, QLineEdit#PathEdit:focus {{
    background: rgba(255, 255, 255, 250);
    border: 1px solid rgba(0, 122, 255, 90);
}}
QLineEdit#SeriesEdit {{
    background: rgba(255, 255, 255, 180);
    border: none;
    border-bottom: 1px solid #E5E5E5;
    border-radius: 6px;
    color: #111827;
    font-family: 'SF Mono', 'Cascadia Mono', 'Consolas', monospace;
    font-size: 11px;
    font-weight: 600;
    min-height: 25px;
    max-height: 25px;
    padding: 0 10px;
}}

QPushButton {{
    background: rgba(236, 238, 242, 245);
    color: #374151;
    border: 1px solid rgba(205, 210, 220, 235);
    border-radius: 16px;
    padding: 0 14px;
    font-weight: 700;
    font-size: 13px;
    min-height: 34px;
    max-height: 34px;
}}
QPushButton:hover {{ background: rgba(228, 231, 236, 250); }}
QPushButton:pressed {{ background: rgba(220, 224, 230, 255); }}
QPushButton:disabled {{
    color: rgba(107, 114, 128, 185);
    background: rgba(232, 234, 238, 210);
    border: 1px solid rgba(209, 213, 219, 185);
}}

QPushButton#PrimaryAction {{
    background: #007AFF;
    color: white;
    border: 1px solid rgba(0, 98, 204, 235);
    font-weight: 800;
}}
QPushButton#PrimaryAction:hover {{
    background: #0A84FF;
}}
QPushButton#PrimaryAction:pressed {{
    background: #006AE0;
}}
QPushButton#PrimaryAction:disabled {{
    background: rgba(88, 166, 255, 160);
    color: rgba(255,255,255,210);
    border: 1px solid rgba(88, 166, 255, 150);
}}

QPushButton#Danger {{
    background: rgba(255, 59, 48, 42);
    color: #FF3B30;
    border: 1px solid rgba(255, 59, 48, 120);
    font-weight: 800;
}}
QPushButton#Danger:hover {{
    background: rgba(255, 59, 48, 60);
}}
QPushButton#Danger:pressed {{
    background: rgba(255, 59, 48, 78);
}}

QCheckBox {{ spacing: 8px; font-size: 12px; color: {C_TEXT}; font-weight: 600; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border-radius: 4px; background: rgba(255, 255, 255, 180); border: 1px solid rgba(210, 214, 222, 220); }}
QCheckBox::indicator:checked {{ background: #007AFF; border: 1px solid #007AFF; }}
QCheckBox#SwitchCheck, QCheckBox#CaptureLogs {{ color: #2F87F6; font-size: 11px; font-weight: 700; }}
QCheckBox#SwitchCheck::indicator, QCheckBox#CaptureLogs::indicator {{ background: rgba(60, 130, 246, 45); border: 1px solid rgba(96, 165, 250, 160); }}
QCheckBox#SwitchCheck::indicator:checked, QCheckBox#CaptureLogs::indicator:checked {{ background: #3B82F6; border: 1px solid #3B82F6; }}

QProgressBar {{
    background: rgba(0, 0, 0, 10);
    border: none;
    border-radius: 3px;
    min-height: 6px;
    max-height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: #2F8CFF;
    border-radius: 3px;
}}

QFrame#ConsoleShell {{
    background: rgba(30, 30, 30, 242);
    border: none;
    border-radius: 12px;
}}

QTextEdit#Console {{
    background: transparent;
    color: #FFFFFF;
    border: none;
    font-family: 'SF Mono', 'Consolas', monospace;
    font-size: 11px;
    padding: 2px;
    selection-background-color: #2F8CFF;
}}

QLabel#ConsoleTitle {{
    color: rgba(248, 250, 252, 205);
    font-size: 11px;
    font-weight: 700;
}}

QLabel#ConsoleStar {{
    color: rgba(245, 245, 245, 160);
    font-size: 18px;
    font-weight: 600;
}}

QPushButton#ConsoleToggle {{
    background: rgba(255, 255, 255, 24);
    color: rgba(248, 250, 252, 220);
    border: 1px solid rgba(255, 255, 255, 42);
    border-radius: 7px;
    padding: 0 10px;
    font-size: 11px;
    font-weight: 700;
}}

QPushButton#ConsoleToggle:hover {{
    background: rgba(255, 255, 255, 38);
}}

QScrollBar:vertical, QScrollBar:horizontal {{
    background: transparent;
    width: 0px;
    height: 0px;
}}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal,
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
    width: 0px;
    height: 0px;
}}
"""

# ─── Modern UI Components ───

class SimpleColorDialog(QDialog):
    def __init__(self, initial_color, title, parent=None):
        super().__init__(parent)
        self._selected_color = QColor(initial_color)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint | Qt.WindowTitleHint)
        self.setModal(True)
        self.setFixedSize(420, 320)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #111111;")
        root.addWidget(title_lbl)

        content = QHBoxLayout()
        content.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(10)
        self.preview = QFrame()
        self.preview.setFixedSize(128, 128)
        self.preview.setStyleSheet("border-radius: 14px; border: 1px solid rgba(0,0,0,0.10);")
        left.addWidget(self.preview, 0, Qt.AlignLeft)

        self.hex_edit = QLineEdit()
        self.hex_edit.setPlaceholderText("#RRGGBB")
        self.hex_edit.editingFinished.connect(self.apply_hex)
        left.addWidget(self.hex_edit)

        presets_wrap = QGridLayout()
        presets_wrap.setHorizontalSpacing(8)
        presets_wrap.setVerticalSpacing(8)
        preset_colors = [
            '#f0f2f6', '#ffffff', '#111111', '#2F87F6', '#28C840', '#FF5B57',
            '#FF9F0A', '#6B7280', '#DCE6F8', '#E9F7EF', '#FFF4E5', '#FDECEC'
        ]
        for idx, color in enumerate(preset_colors):
            swatch = QPushButton()
            swatch.setFixedSize(28, 28)
            swatch.setCursor(Qt.PointingHandCursor)
            swatch.setStyleSheet(f"QPushButton {{ background: {color}; border-radius: 14px; border: 1px solid rgba(0,0,0,0.14); }} QPushButton:hover {{ border: 2px solid #2F87F6; }}")
            swatch.clicked.connect(lambda _=False, c=color: self.set_color(QColor(c)))
            presets_wrap.addWidget(swatch, idx // 6, idx % 6)
        left.addLayout(presets_wrap)
        left.addStretch()
        content.addLayout(left)

        right = QVBoxLayout()
        right.setSpacing(12)
        self.r_slider = self._make_slider()
        self.g_slider = self._make_slider()
        self.b_slider = self._make_slider()
        self.r_value = QLabel()
        self.g_value = QLabel()
        self.b_value = QLabel()
        right.addLayout(self._channel_row('R', self.r_slider, self.r_value))
        right.addLayout(self._channel_row('G', self.g_slider, self.g_value))
        right.addLayout(self._channel_row('B', self.b_slider, self.b_value))
        right.addStretch()
        content.addLayout(right, 1)
        root.addLayout(content)

        actions = QHBoxLayout()
        actions.addStretch()
        cancel_btn = QPushButton('取消')
        ok_btn = QPushButton('确定')
        ok_btn.setDefault(True)
        for button in (cancel_btn, ok_btn):
            button.setMinimumWidth(96)
            button.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self.accept)
        actions.addWidget(cancel_btn)
        actions.addWidget(ok_btn)
        root.addLayout(actions)

        self.setStyleSheet("""
            QDialog {
                background: #F7F8FB;
            }
            QLineEdit {
                background: white;
                border: 1px solid rgba(205, 210, 220, 235);
                border-radius: 10px;
                min-height: 32px;
                padding: 0 10px;
                font-size: 13px;
                color: #111111;
            }
            QPushButton {
                background: rgba(236, 238, 242, 245);
                color: #111111;
                border: 1px solid rgba(205, 210, 220, 235);
                border-radius: 14px;
                min-height: 34px;
                padding: 0 14px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: rgba(228, 231, 236, 250);
            }
            QLabel {
                color: #111111;
                font-size: 13px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: rgba(15, 23, 42, 0.10);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                margin: -5px 0;
                background: white;
                border: 1px solid rgba(15, 23, 42, 0.18);
                border-radius: 8px;
            }
        """)

        self.r_slider.valueChanged.connect(self.sync_from_sliders)
        self.g_slider.valueChanged.connect(self.sync_from_sliders)
        self.b_slider.valueChanged.connect(self.sync_from_sliders)
        self.set_color(self._selected_color)

    def _make_slider(self):
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 255)
        return slider

    def _channel_row(self, name, slider, value_label):
        row = QVBoxLayout()
        row.setSpacing(4)
        header = QHBoxLayout()
        label = QLabel(name)
        label.setFixedWidth(20)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(label)
        header.addStretch()
        header.addWidget(value_label)
        row.addLayout(header)
        row.addWidget(slider)
        return row

    def set_color(self, color):
        self._selected_color = QColor(color)
        for slider, value in ((self.r_slider, color.red()), (self.g_slider, color.green()), (self.b_slider, color.blue())):
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self.refresh_preview()

    def sync_from_sliders(self):
        self._selected_color = QColor(self.r_slider.value(), self.g_slider.value(), self.b_slider.value())
        self.refresh_preview()

    def refresh_preview(self):
        color = self._selected_color
        self.preview.setStyleSheet(f"background: {color.name()}; border-radius: 14px; border: 1px solid rgba(0,0,0,0.10);")
        self.hex_edit.setText(color.name())
        self.r_value.setText(str(color.red()))
        self.g_value.setText(str(color.green()))
        self.b_value.setText(str(color.blue()))

    def apply_hex(self):
        text = self.hex_edit.text().strip()
        color = QColor(text)
        if color.isValid():
            self.set_color(color)
        else:
            self.refresh_preview()

    def selectedColor(self):
        return QColor(self._selected_color)

class ThemeColorEditor(QFrame):
    def __init__(self, title, initial_color, parent=None):
        super().__init__(parent)
        self._selected_color = QColor(initial_color)
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        lay.addWidget(lbl(title, obj="Title"))

        top = QHBoxLayout()
        top.setSpacing(12)
        self.preview = QFrame()
        self.preview.setFixedSize(84, 84)
        self.preview.setStyleSheet("border-radius: 16px; border: 1px solid rgba(0,0,0,0.10);")
        top.addWidget(self.preview, 0, Qt.AlignTop)

        right = QVBoxLayout()
        right.setSpacing(8)
        self.hex_edit = QLineEdit()
        self.hex_edit.setObjectName("ParamEdit")
        self.hex_edit.editingFinished.connect(self.apply_hex)
        right.addWidget(self.hex_edit)

        self.r_slider = self._make_slider()
        self.g_slider = self._make_slider()
        self.b_slider = self._make_slider()
        self.r_value = QLabel()
        self.g_value = QLabel()
        self.b_value = QLabel()
        right.addLayout(self._channel_row('R', self.r_slider, self.r_value))
        right.addLayout(self._channel_row('G', self.g_slider, self.g_value))
        right.addLayout(self._channel_row('B', self.b_slider, self.b_value))
        top.addLayout(right, 1)
        lay.addLayout(top)

        presets_wrap = QGridLayout()
        presets_wrap.setHorizontalSpacing(8)
        presets_wrap.setVerticalSpacing(8)
        preset_colors = [
            '#f0f2f6', '#ffffff', '#111111', '#2F87F6', '#28C840', '#FF5B57',
            '#FF9F0A', '#6B7280', '#DCE6F8', '#E9F7EF', '#FFF4E5', '#FDECEC'
        ]
        for idx, color in enumerate(preset_colors):
            swatch = QPushButton()
            swatch.setFixedSize(24, 24)
            swatch.setCursor(Qt.PointingHandCursor)
            swatch.setStyleSheet(f"QPushButton {{ background: {color}; border-radius: 12px; border: 1px solid rgba(0,0,0,0.14); padding: 0; min-height: 24px; max-height: 24px; }} QPushButton:hover {{ border: 2px solid #2F87F6; }}")
            swatch.clicked.connect(lambda _=False, c=color: self.set_color(QColor(c)))
            presets_wrap.addWidget(swatch, idx // 6, idx % 6)
        lay.addLayout(presets_wrap)

        for slider in (self.r_slider, self.g_slider, self.b_slider):
            slider.valueChanged.connect(self.sync_from_sliders)
        self.set_color(self._selected_color)

    def _make_slider(self):
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 255)
        return slider

    def _channel_row(self, name, slider, value_label):
        row = QVBoxLayout()
        row.setSpacing(2)
        head = QHBoxLayout()
        head.setSpacing(6)
        label = QLabel(name)
        label.setFixedWidth(18)
        value_label.setMinimumWidth(28)
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        head.addWidget(label)
        head.addStretch()
        head.addWidget(value_label)
        row.addLayout(head)
        row.addWidget(slider)
        return row

    def set_color(self, color):
        self._selected_color = QColor(color)
        for slider, value in ((self.r_slider, color.red()), (self.g_slider, color.green()), (self.b_slider, color.blue())):
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self.refresh_preview()

    def sync_from_sliders(self):
        self._selected_color = QColor(self.r_slider.value(), self.g_slider.value(), self.b_slider.value())
        self.refresh_preview()

    def refresh_preview(self):
        color = self._selected_color
        self.preview.setStyleSheet(f"background: {color.name()}; border-radius: 16px; border: 1px solid rgba(0,0,0,0.10);")
        self.hex_edit.setText(color.name())
        self.r_value.setText(str(color.red()))
        self.g_value.setText(str(color.green()))
        self.b_value.setText(str(color.blue()))

    def apply_hex(self):
        color = QColor(self.hex_edit.text().strip())
        if color.isValid():
            self.set_color(color)
        else:
            self.refresh_preview()

    def selectedColor(self):
        return QColor(self._selected_color)

class ThemeDialog(QDialog):
    """Modern theme adjustment panel."""
    def __init__(self, parent):
        super().__init__(parent)
        self._parent = parent
        self.setWindowTitle("主题与色彩定制")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(760, 520)
        set_blur_behind(self.winId())
        if parent and hasattr(parent, 'styleSheet'):
            self.setStyleSheet(parent.styleSheet())
        self.theme_presets = self._load_theme_presets()

        self.root = QWidget(self)
        self.root.setObjectName("MainContainer")
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.addWidget(self.root)

        vlay = QVBoxLayout(self.root)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        self.title_bar = TitleBar(self, is_dialog=True)
        self.title_bar.brand_lbl.setText("主题与色彩定制")
        self.title_bar.title_lbl.setText("Theme Studio")
        self.title_bar.btn_min.hide()
        self.title_bar.theme_btn.hide()
        vlay.addWidget(self.title_bar)

        content = QWidget()
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(22, 18, 22, 22)
        content_lay.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        self.bg_editor = ThemeColorEditor("背景色", getattr(self._parent, 'current_bg', QColor(240, 242, 246)), self)
        self.text_editor = ThemeColorEditor("字体色", getattr(self._parent, 'current_text', QColor(17, 17, 17)), self)
        top_row.addWidget(self.bg_editor, 1)
        top_row.addWidget(self.text_editor, 1)
        content_lay.addLayout(top_row)

        preset_card = card()
        preset_lay = QVBoxLayout(preset_card)
        preset_lay.setContentsMargins(16, 14, 16, 14)
        preset_lay.setSpacing(10)
        preset_lay.addWidget(lbl("主题预设", obj="Title"))

        preset_row = QHBoxLayout()
        preset_row.setSpacing(10)
        self.theme_preset_combo = QComboBox()
        self.theme_preset_combo.setMinimumWidth(220)
        preset_row.addWidget(self.theme_preset_combo)
        load_btn = btn("加载", False)
        save_btn = btn("保存当前", False)
        del_btn = btn("删除", False)
        load_btn.clicked.connect(self.load_selected_preset)
        save_btn.clicked.connect(self.save_current_preset)
        del_btn.clicked.connect(self.delete_selected_preset)
        preset_row.addWidget(load_btn)
        preset_row.addWidget(save_btn)
        preset_row.addWidget(del_btn)
        preset_row.addStretch()
        preset_lay.addLayout(preset_row)
        content_lay.addWidget(preset_card)

        actions = QHBoxLayout()
        actions.addStretch()
        reset_btn = btn("恢复默认", False)
        apply_btn = btn("应用主题", True)
        close_btn = btn("关闭", False)
        reset_btn.clicked.connect(self.reset_default_theme)
        apply_btn.clicked.connect(self.apply_current_theme)
        close_btn.clicked.connect(self.accept)
        actions.addWidget(reset_btn)
        actions.addWidget(close_btn)
        actions.addWidget(apply_btn)
        content_lay.addLayout(actions)

        vlay.addWidget(content)

        for slider in (self.bg_editor.r_slider, self.bg_editor.g_slider, self.bg_editor.b_slider,
                       self.text_editor.r_slider, self.text_editor.g_slider, self.text_editor.b_slider):
            slider.valueChanged.connect(self.apply_current_theme)
        self.bg_editor.hex_edit.editingFinished.connect(self.apply_current_theme)
        self.text_editor.hex_edit.editingFinished.connect(self.apply_current_theme)
        self.refresh_preset_combo()
        self.apply_current_theme()

    def pick_bg(self):
        current = getattr(self._parent, 'current_bg', QColor(240, 242, 246))
        c = self._open_color_dialog(current, "选择主背景颜色")
        if c.isValid():
            self._parent.apply_theme(c, getattr(self._parent, 'current_text', None))

    def pick_text(self):
        current = getattr(self._parent, 'current_text', QColor(17, 17, 17))
        c = self._open_color_dialog(current, "选择全局字体颜色")
        if c.isValid():
            self._parent.apply_theme(getattr(self._parent, 'current_bg', QColor(240, 242, 246)), c)

    def _open_color_dialog(self, current, title):
        return self._parent._open_color_dialog(current, title)

    def apply_current_theme(self):
        bg = self.bg_editor.selectedColor()
        text = self.text_editor.selectedColor()
        if bg.isValid() and text.isValid():
            self._parent.apply_theme(bg, text)
            if hasattr(self, 'setStyleSheet') and self._parent.styleSheet():
                self.setStyleSheet(self._parent.styleSheet())

    def _theme_preset_path(self):
        return os.path.join(APP_DIR, 'theme_presets.json')

    def _load_theme_presets(self):
        path = self._theme_preset_path()
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {
            '默认浅色': {'bg': '#f0f2f6', 'text': '#111111'}
        }

    def _save_theme_presets(self):
        try:
            with open(self._theme_preset_path(), 'w', encoding='utf-8') as f:
                json.dump(self.theme_presets, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def refresh_preset_combo(self, current_name=None):
        names = sorted(self.theme_presets.keys())
        self.theme_preset_combo.blockSignals(True)
        self.theme_preset_combo.clear()
        self.theme_preset_combo.addItems(names)
        if current_name and current_name in names:
            self.theme_preset_combo.setCurrentText(current_name)
        self.theme_preset_combo.blockSignals(False)

    def save_current_preset(self):
        name = f"预设{len(self.theme_presets) + 1}"
        base = name
        idx = 1
        while name in self.theme_presets:
            idx += 1
            name = f"{base}_{idx}"
        self.theme_presets[name] = {
            'bg': self.bg_editor.selectedColor().name(),
            'text': self.text_editor.selectedColor().name(),
        }
        self._save_theme_presets()
        self.refresh_preset_combo(name)

    def load_selected_preset(self):
        name = self.theme_preset_combo.currentText().strip()
        preset = self.theme_presets.get(name)
        if not preset:
            return
        self.bg_editor.set_color(QColor(preset.get('bg', '#f0f2f6')))
        self.text_editor.set_color(QColor(preset.get('text', '#111111')))
        self.apply_current_theme()

    def delete_selected_preset(self):
        name = self.theme_preset_combo.currentText().strip()
        if not name or name == '默认浅色':
            return
        if name in self.theme_presets:
            del self.theme_presets[name]
            self._save_theme_presets()
            self.refresh_preset_combo()

    def reset_default_theme(self):
        self.bg_editor.set_color(QColor('#f0f2f6'))
        self.text_editor.set_color(QColor('#111111'))
        self.apply_current_theme()

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        # Use theme-aware background
        is_dark = self._parent.brightness < 128 if hasattr(self._parent, 'brightness') else False
        bg_color = QColor(40, 40, 40, 250) if is_dark else QColor(255, 255, 255, 250)
        border_color = QColor(255, 255, 255, 40) if is_dark else QColor(0, 0, 0, 30)
        
        p.setBrush(QBrush(bg_color))
        p.setPen(QPen(border_color, 1))
        p.drawRoundedRect(self.rect(), 16, 16)

class TitleBar(QWidget):
    """Custom header bar aligned to the reference dashboard."""
    def __init__(self, parent, is_dialog=False):
        super().__init__(parent)
        self._parent = parent
        self._drag_pos = None
        self.setObjectName("TitleBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(65)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(12)

        self.btn_close = QPushButton()
        self.btn_close.setObjectName("ControlBtn")
        self.btn_close.setFixedSize(14, 14); self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("关闭")
        self.btn_close.setStyleSheet("QPushButton { background: #FF5F56; border-radius: 7px; border: 1px solid rgba(0,0,0,0.1); } QPushButton:hover { background: #FF3B30; }")
        self.btn_close.clicked.connect(self._parent.close)

        self.theme_btn = QPushButton()
        self.theme_btn.setObjectName("ControlBtn")
        self.theme_btn.setFixedSize(14, 14); self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.setToolTip("主题/配色控制")
        self.theme_btn.setStyleSheet("QPushButton { background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #FF5F56, stop:0.5 #FFBD2E, stop:1 #27C93F); border-radius: 7px; border: 1px solid rgba(0,0,0,0.1); }")
        if hasattr(self._parent, 'open_theme_dialog'):
            self.theme_btn.clicked.connect(self._parent.open_theme_dialog)
        else:
            self.theme_btn.hide()

        self.btn_min = QPushButton()
        self.btn_min.setObjectName("ControlBtn")
        self.btn_min.setFixedSize(14, 14); self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.setToolTip("最小化")
        self.btn_min.setStyleSheet("QPushButton { background: #FFBD2E; border-radius: 7px; border: 1px solid rgba(0,0,0,0.1); } QPushButton:hover { background: #E0A628; }")
        self.btn_min.clicked.connect(self._parent.showMinimized)

        self.btn_max = QPushButton()
        self.btn_max.setObjectName("ControlBtn")
        self.btn_max.setFixedSize(14, 14); self.btn_max.setCursor(Qt.PointingHandCursor)
        self.btn_max.setToolTip("最大化/还原")
        self.btn_max.setStyleSheet("QPushButton { background: #28C840; border-radius: 7px; border: 1px solid rgba(0,0,0,0.1); } QPushButton:hover { background: #24B338; }")
        self.btn_max.clicked.connect(self._toggle_max_restore)

        if not is_dialog:
            lay.addWidget(self.btn_close)
            lay.addWidget(self.btn_max)
            lay.addSpacing(6)
            lay.addWidget(self.theme_btn)
            lay.addSpacing(10)
            
            self.brand_lbl = QLabel("FmuSolver")
            self.brand_lbl.setObjectName("BrandLabel")
            lay.addWidget(self.brand_lbl)
            self.version_lbl = QLabel(APP_VERSION)
            self.version_lbl.setObjectName("VersionBadge")
            self.version_lbl.setToolTip(f"FmuSolver version {APP_VERSION}")
            lay.addWidget(self.version_lbl)
            lay.addSpacing(12)

            t_lay = QVBoxLayout(); t_lay.setSpacing(2); t_lay.setContentsMargins(0, 10, 0, 10)
            self.title_lbl = QLabel("Satellite Payload Simulation & Orbit Prediction Platform")
            self.title_lbl.setObjectName("HeaderLabel")
            self.sub_lbl = QLabel("Industrial Simulation Dashboard")
            self.sub_lbl.setObjectName("SubHeaderLabel")
            t_lay.addWidget(self.title_lbl)
            t_lay.addWidget(self.sub_lbl)
            lay.addLayout(t_lay)
            
            lay.addStretch()

            self.led_dot = QLabel("●")
            self.led_dot.setStyleSheet("color: #27C93F; font-size: 13px; margin-right: 4px;")
            self.led_txt = QLabel("READY")
            self.led_txt.setObjectName("StatusText")
            lay.addWidget(self.led_dot)
            lay.addWidget(self.led_txt)
            lay.addSpacing(15)

            # Move ONLY MINIMIZE to the RIGHT
            lay.addWidget(self.btn_min)
            lay.addSpacing(5)
        else:
            self.brand_lbl = QLabel("")
            self.brand_lbl.setObjectName("BrandLabel")
            lay.addWidget(self.brand_lbl)
            self.version_lbl = QLabel("")
            self.version_lbl.setObjectName("VersionBadge")
            self.version_lbl.hide()
            
            self.title_lbl = QLabel(""); self.title_lbl.setObjectName("HeaderLabel")
            self.sub_lbl = QLabel(""); self.sub_lbl.setObjectName("SubHeaderLabel")
            lay.addWidget(self.title_lbl)
            
            lay.addStretch()
            lay.addWidget(self.btn_min)
            lay.addWidget(self.theme_btn)
            lay.addWidget(self.btn_close)
            
            self.led_dot = QLabel(); self.led_dot.hide()
            self.led_txt = QLabel(); self.led_txt.hide()

    def _toggle_max_restore(self):
        if self._parent.isMaximized():
            self._parent.showNormal()
        else:
            self._parent.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self._parent.move(self._parent.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._toggle_max_restore()

class ModernCard(QFrame):
    """Floating translucent card."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

class PillInput(QWidget):
    """Compact label + value field with word wrap for long descriptions."""
    def __init__(self, label_text, value="", parent=None, wide=False):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 1, 0, 1)
        lay.setSpacing(10)

        self.lbl = QLabel(label_text)
        self.lbl.setObjectName("ParamLabel")
        self.lbl.setWordWrap(True)
        if wide:
            self.lbl.setFixedWidth(400)
            self.lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        else:
            self.lbl.setFixedWidth(160)
            self.lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.edit = QLineEdit(str(value))
        self.edit.setObjectName("SeriesEdit" if wide else "ParamEdit")
        self.edit.setFixedHeight(30)
        self.edit.setMinimumHeight(30)
        if not wide:
            self.edit.setFixedWidth(92)

        lay.addWidget(self.lbl)
        lay.addWidget(self.edit, 1 if wide else 0)
        if not wide:
            lay.addStretch()

class SegmentedControl(QFrame):
    """macOS-style segmented control."""
    changed = Signal(int)

    def __init__(self, labels, parent=None):
        super().__init__(parent)
        self.setObjectName("SegTrack")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(36)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)
        self.buttons = []
        for i, text in enumerate(labels):
            b = QPushButton(text)
            b.setObjectName("SegBtn")
            b.setAttribute(Qt.WA_StyledBackground, True)
            b.clicked.connect(lambda _, idx=i: self.set_index(idx))
            b.setCursor(Qt.PointingHandCursor)
            lay.addWidget(b)
            self.buttons.append(b)
        self.set_index(0)

    def set_index(self, idx):
        for i, b in enumerate(self.buttons):
            active = (i == idx)
            b.setObjectName("SegBtnActive" if active else "SegBtn")
            b.setGraphicsEffect(None)
            b.style().unpolish(b)
            b.style().polish(b)
            b.update()
        self.changed.emit(idx)

# ─── Helper Factories ───
def card(parent=None): return ModernCard(parent)
def pill_field(label, value="", parent=None, wide=False): return PillInput(label, value, parent, wide)
def btn(text, primary=True, parent=None):
    b = QPushButton(text, parent)
    b.setAttribute(Qt.WA_StyledBackground, True)
    if primary: b.setObjectName("PrimaryAction")
    b.setCursor(Qt.PointingHandCursor)
    return b
def danger_btn(text, parent=None):
    b = QPushButton(text, parent)
    b.setAttribute(Qt.WA_StyledBackground, True)
    b.setObjectName("Danger")
    b.setCursor(Qt.PointingHandCursor)
    return b
def lbl(text, parent=None, obj=None):
    w = QLabel(text, parent)
    if obj: w.setObjectName(obj)
    return w
def divider(parent=None):
    f = QFrame(parent)
    f.setFixedHeight(1)
    f.setStyleSheet("background: rgba(0,0,0,0.08);")
    return f

def console_panel(title, editor, parent=None, min_height=None, fixed_height=None):
    shell = QFrame(parent)
    shell.setObjectName("ConsoleShell")
    shell._log_collapsed = False
    shell._expanded_min_height = min_height
    shell._expanded_fixed_height = fixed_height
    shell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    lay = QVBoxLayout(shell)
    lay.setContentsMargins(12, 10, 12, 10)
    lay.setSpacing(6)
    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(8)
    header.addWidget(lbl(title, obj="ConsoleTitle"))
    header.addStretch()
    toggle_btn = QPushButton("折叠日志")
    toggle_btn.setObjectName("ConsoleToggle")
    toggle_btn.setToolTip("折叠后停止向界面写入日志，完整日志仍写入文件")
    toggle_btn.setFixedHeight(24)
    header.addWidget(toggle_btn)
    lay.addLayout(header)
    editor.setObjectName("Console")
    editor.setReadOnly(True)
    editor.document().setMaximumBlockCount(min(editor.document().maximumBlockCount() or 120, 120))
    if fixed_height is not None:
        editor.setFixedHeight(fixed_height)
    if min_height is not None:
        editor.setMinimumHeight(min_height)
    lay.addWidget(editor)
    foot = QHBoxLayout()
    foot.setContentsMargins(0, 0, 0, 0)
    foot.addStretch()
    star = QLabel("✦")
    star.setObjectName("ConsoleStar")
    foot.addWidget(star)
    lay.addLayout(foot)

    def toggle_console():
        collapsed = not getattr(shell, "_log_collapsed", False)
        shell._log_collapsed = collapsed
        editor.setProperty("log_collapsed", collapsed)
        editor.setVisible(not collapsed)
        star.setVisible(not collapsed)
        if collapsed:
            editor.clear()
            shell.setMinimumHeight(48)
            shell.setMaximumHeight(48)
            shell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            toggle_btn.setText("展开日志")
            toggle_btn.setToolTip("展开后恢复显示新的日志信息")
        else:
            shell.setMinimumHeight(0)
            shell.setMaximumHeight(16777215)
            shell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            toggle_btn.setText("折叠日志")
            toggle_btn.setToolTip("折叠后停止向界面写入日志，完整日志仍写入文件")
        shell.updateGeometry()
        parent_widget = shell.parentWidget()
        if parent_widget and parent_widget.layout():
            parent_widget.layout().activate()

    toggle_btn.clicked.connect(toggle_console)
    editor._log_toggle_button = toggle_btn
    editor._log_panel_shell = shell
    return shell

# ─── Low-level Engine Helpers ───

def get_fmu_arch(fmu_path):
    try:
        with zipfile.ZipFile(fmu_path, 'r') as z:
            names = z.namelist()
            if any(n.startswith('binaries/win64/') for n in names): return 64
            if any(n.startswith('binaries/win32/') for n in names): return 32
    except: pass
    return None

def ensure_ascii_fmu_path(fmu_path, log_fn=None):
    """32位打包Worker(旧PyInstaller引导器)会把含中文/非ASCII字符的argv按UTF-8
    误解码成乱码，导致 FileNotFoundError。路径含非ASCII字符时，先把FMU复制到
    纯ASCII的 C:\\FmuSolver_Runtime\\fmu_input 下，再把安全路径传给Worker。"""
    try:
        fmu_path.encode('ascii')
        return fmu_path
    except UnicodeEncodeError:
        pass
    import hashlib, shutil
    safe_dir = r"C:\FmuSolver_Runtime\fmu_input"
    try:
        os.makedirs(safe_dir, exist_ok=True)
        tag = hashlib.md5(fmu_path.encode('utf-8')).hexdigest()[:8]
        safe_path = os.path.join(safe_dir, "input_%s.fmu" % tag)
        if (not os.path.exists(safe_path)) or (os.path.getmtime(safe_path) < os.path.getmtime(fmu_path)):
            shutil.copy2(fmu_path, safe_path)
        if log_fn:
            log_fn(f"[*] FMU路径含非ASCII字符，已复制到 {safe_path} 供Worker使用", "sys")
        return safe_path
    except Exception as e:
        if log_fn:
            log_fn(f"[!] FMU安全路径复制失败({e})，仍使用原路径，中文路径可能导致Worker报错", "error")
        return fmu_path

def _norm_existing(path):
    if path and os.path.exists(path): return os.path.normpath(path)
    return None

def _find_file_by_names(search_roots, names):
    for root in search_roots:
        if not os.path.isdir(root): continue
        for name in names:
            direct = os.path.join(root, name)
            if os.path.exists(direct): return os.path.normpath(direct)
    return None

def auto_find_fmu(names, keywords=None):
    roots = [
        os.path.join(APP_DIR, "FMU"),
        os.path.join(APP_DIR, "..", "FMU"),
        os.path.join(APP_DIR, "..", "FmuSolver_Package", "FMU"),
        os.path.join(APP_DIR, "..", "FmuSolver_Package05061502", "FmuSolver_Package", "FMU"),
        APP_DIR,
        os.path.join(APP_DIR, ".."),
    ]
    result = _find_file_by_names(roots, names)
    if result: return result
    
    if keywords:
        for r in roots:
            if not os.path.isdir(r): continue
            for cr, _, files in os.walk(r):
                if cr.count(os.sep) - r.count(os.sep) > 2: continue 
                for f in files:
                    if f.endswith('.fmu') and all(k.lower() in f.lower() for k in keywords):
                        return os.path.normpath(os.path.join(cr, f))
    return None

def auto_find_yaoce_dir():
    for c in [os.path.join(APP_DIR, "yaocetest"), os.path.join(APP_DIR, "..", "yaocetest")]:
        if os.path.isdir(c) and os.path.exists(os.path.join(c, "config.ini")):
            return os.path.normpath(c)
    return None

class SmartParseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(720, 520)
        set_blur_behind(self.winId())
        if parent and hasattr(parent, 'styleSheet'):
            self.setStyleSheet(parent.styleSheet())
        
        self.root = QWidget(self); self.root.setObjectName("MainContainer")
        root_lay = QVBoxLayout(self); root_lay.setContentsMargins(0, 0, 0, 0); root_lay.addWidget(self.root)
        
        vlay = QVBoxLayout(self.root); vlay.setContentsMargins(0, 0, 0, 0); vlay.setSpacing(0)
        
        self.title_bar = TitleBar(self, is_dialog=True)
        self.title_bar.brand_lbl.setText("智能解析 (Modelica 语法)")
        self.title_bar.btn_min.hide()
        vlay.addWidget(self.title_bar)
        
        content = QWidget(); content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(25, 20, 25, 25); content_lay.setSpacing(15)
        
        hint = QLabel("直接粘贴包含变量声明的代码 (如: output Real MTSatPos[3] ...):")
        hint.setObjectName("Muted")
        content_lay.addWidget(hint)
        
        self.txt = QTextEdit()
        self.txt.setStyleSheet("""
            QTextEdit {
                background: rgba(0, 0, 0, 15);
                border: 1px solid rgba(128, 128, 128, 40);
                border-radius: 12px;
                padding: 15px;
                font-family: 'SF Mono', 'Cascadia Mono', 'Consolas', monospace;
                font-size: 13px;
                color: inherit;
            }
            QTextEdit:focus {
                border: 1px solid #007AFF;
                background: rgba(255, 255, 255, 20);
            }
        """)
        self.txt.setPlaceholderText("output Real MTSatPos[3] = enviroment.SatPos \"J2000位置矢量km\";")
        content_lay.addWidget(self.txt)
        
        btn_lay = QHBoxLayout()
        b_ok = btn("确认解析", True)
        b_ok.clicked.connect(self.accept)
        b_cancel = btn("取消", False)
        b_cancel.clicked.connect(self.reject)
        btn_lay.addStretch(); btn_lay.addWidget(b_cancel); btn_lay.addWidget(b_ok)
        content_lay.addLayout(btn_lay)
        
        vlay.addWidget(content)
        
        self.history_file = os.path.join(APP_DIR, "viz_parse_history.txt")
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.txt.setPlainText(f.read())
            except: pass
        
    def accept(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                f.write(self.txt.toPlainText())
        except: pass
        super().accept()
        
    def get_result(self):
        content = self.txt.toPlainText().strip()
        if not content: return []
        
        lines = content.split('\n')
        results = []
        for line in lines:
            line = line.strip()
            if not line: continue
            m = re.search(r'(?:output\s+)?(?:(Real|Integer|Boolean|String)\s+)?([a-zA-Z0-9_\.]+)(?:\[(\d+)\])?(?:\s*=\s*([a-zA-Z0-9_\.]+))?(.*)', line)
            if m:
                var_type = m.group(1) or 'Real'
                base_name = m.group(2)
                size = int(m.group(3)) if m.group(3) else 1
                desc_match = re.search(r'\"([^\"]+)\"', m.group(5))
                desc = desc_match.group(1) if desc_match else ''
                
                for i in range(1, size + 1):
                    name = f"{base_name}[{i}]" if size > 1 else base_name
                    results.append({"name": name, "source": name, "type": var_type, "desc": desc, "sync": True})
            else:
                results.append({"name": line, "source": line, "type": "Real", "desc": "", "sync": True})
        return results

class FieldsDialog(QDialog):
    def __init__(self, sync_path, parent=None):
        super().__init__(parent)
        self.sync_path = sync_path
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(950, 650)
        set_blur_behind(self.winId())
        if parent and hasattr(parent, 'styleSheet'):
            self.setStyleSheet(parent.styleSheet())
        self.root = QWidget(self); self.root.setObjectName("MainContainer")
        root_lay = QVBoxLayout(self); root_lay.setContentsMargins(0, 0, 0, 0); root_lay.addWidget(self.root)
        vlay = QVBoxLayout(self.root); vlay.setContentsMargins(0, 0, 0, 0); vlay.setSpacing(0)
        self.title_bar = TitleBar(self, is_dialog=True)
        self.title_bar.brand_lbl.setText("变量同步配置 (DDM 映射)")
        self.title_bar.btn_min.hide()
        vlay.addWidget(self.title_bar)
        content = QWidget(); content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(20, 15, 20, 20); content_lay.setSpacing(12)
        toolbar = QHBoxLayout()
        b_add = btn("+ 手动添加", False)
        b_add.clicked.connect(self.add_manual)
        b_parse = btn("⚡ 智能解析粘贴文本", False)
        b_parse.clicked.connect(self.open_smart_parse)
        b_del = btn("➖ 删除选中", False)
        b_del.clicked.connect(self.delete_selected)
        b_clear = btn("🗑 清除所有字段", False)
        b_clear.clicked.connect(self.clear_all)
        toolbar.addWidget(b_add); toolbar.addWidget(b_parse); toolbar.addWidget(b_del); toolbar.addWidget(b_clear)
        toolbar.addStretch()
        b_save = btn("💾 保存并应用", True)
        b_save.clicked.connect(self.save_and_close)
        toolbar.addWidget(b_save)
        content_lay.addLayout(toolbar)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["字段名 (唯一键)", "类型", "描述", "同步"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 300)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(3, 80)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setStyleSheet("""
            QTableWidget { background: rgba(0,0,0,15); border: 1px solid rgba(128,128,128,40); border-radius: 8px; color: inherit; }
            QHeaderView::section { background: rgba(0,0,0,30); padding: 4px; border: none; font-weight: bold; }
        """)
        content_lay.addWidget(self.table)
        vlay.addWidget(content)
        self.load_data()
        
    def add_manual(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem("NewVariable"))
        self.table.setItem(row, 1, QTableWidgetItem("Real"))
        self.table.setItem(row, 2, QTableWidgetItem("手动添加"))
        self.table.setCellWidget(row, 3, self._create_center_cb(True))
        
    def _create_center_cb(self, checked):
        w = QWidget(); lay = QHBoxLayout(w)
        cb = QCheckBox(); cb.setChecked(checked)
        lay.addWidget(cb); lay.setAlignment(Qt.AlignCenter); lay.setContentsMargins(0, 0, 0, 0)
        w.cb = cb
        return w

    def open_smart_parse(self):
        dlg = SmartParseDialog(self)
        if dlg.exec() == QDialog.Accepted:
            items = dlg.get_result()
            for item in items:
                exists = False
                for r in range(self.table.rowCount()):
                    it = self.table.item(r, 0)
                    if it and it.text() == item["name"]:
                        exists = True; break
                if not exists:
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    it_name = QTableWidgetItem(item["name"])
                    it_name.fmu_source = item["source"]
                    self.table.setItem(row, 0, it_name)
                    self.table.setItem(row, 1, QTableWidgetItem(item["type"]))
                    self.table.setItem(row, 2, QTableWidgetItem(item["desc"]))
                    self.table.setCellWidget(row, 3, self._create_center_cb(True))

    def clear_all(self):
        if QMessageBox.question(self, "确认", "是否清除所有已配置的字段？") == QMessageBox.Yes:
            self.table.setRowCount(0)

    def delete_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def load_data(self):
        if not os.path.exists(self.sync_path): return
        try:
            with open(self.sync_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    name = item.get("name", "")
                    source = item.get("source") or name
                    vtype = item.get("type", "Real")
                    desc = item.get("desc") or item.get("description") or ""
                    sync = item.get("sync", True)
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    item_name = QTableWidgetItem(name)
                    item_name.fmu_source = source
                    self.table.setItem(row, 0, item_name)
                    self.table.setItem(row, 1, QTableWidgetItem(vtype))
                    self.table.setItem(row, 2, QTableWidgetItem(desc))
                    self.table.setCellWidget(row, 3, self._create_center_cb(sync))
        except: pass

    def save_and_close(self):
        data = []
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if not it or not it.text().strip(): continue
            name = it.text().strip()
            vtype_it = self.table.item(r, 1)
            vtype = vtype_it.text() if vtype_it else "Real"
            desc_it = self.table.item(r, 2)
            desc = desc_it.text() if desc_it else ""
            cb_w = self.table.cellWidget(r, 3)
            sync = cb_w.cb.isChecked() if cb_w and hasattr(cb_w, 'cb') else True
            source = getattr(it, "fmu_source", name)
            data.append({"name": name, "source": source, "type": vtype, "desc": desc, "sync": sync})
        try:
            with open(self.sync_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

class FmuSolverGUI(QMainWindow):
    sig_log          = Signal(str, str)
    sig_olog         = Signal(str, str)
    sig_ylog         = Signal(str, str)
    sig_sim_prog     = Signal(int, str)
    sig_orbit_prog   = Signal(int, str)
    sig_reset_ui     = Signal()
    sig_orbit_done   = Signal()
    sig_export_ready = Signal()

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        
        # ─── Activate High Fidelity Blur ───
        set_blur_behind(self.winId())
        
        self.worker_process = None
        self.visualizer_process = None
        self.orbit_data = []
        self.orbit_proc = None
        self.current_sim_id = None
        self._yaoce_log_pos = 0
        self.runtime_log_path = os.path.join(APP_DIR, "fmusolver_runtime.log")
        self.runtime_logger = AsyncRotatingFileLogger(
            self.runtime_log_path,
            max_bytes=int(os.environ.get("FMUSOLVER_RUNTIME_LOG_MB", "10")) * 1024 * 1024,
            backups=int(os.environ.get("FMUSOLVER_RUNTIME_LOG_BACKUPS", "3")),
            queue_size=int(os.environ.get("FMUSOLVER_RUNTIME_LOG_QUEUE", "2000")),
            flush_interval=float(os.environ.get("FMUSOLVER_RUNTIME_LOG_FLUSH", "0.5")),
            batch_size=int(os.environ.get("FMUSOLVER_RUNTIME_LOG_BATCH", "100")),
        )
        self.last_ui_heartbeat = time.time()
        self._runtime_log_last_size_check = 0.0
        self._ui_log_throttle = {}
        self._resize_perf_mode = False
        self._resize_restore_timer = QTimer(self)
        self._resize_restore_timer.setSingleShot(True)
        self._resize_restore_timer.timeout.connect(self._end_resize_perf_mode)
        self.gui_config_path = GUI_CONFIG_PATH
        self.gui_config = self._load_gui_config()
        self.default_sim_fmu   = self._resolve_sim_fmu()
        self.default_orbit_fmu = self._resolve_orbit_fmu()
        self.yaoce_dir = self._resolve_yaoce_dir()
        self.default_ip   = str(self.gui_config.get("ip", "127.0.0.1"))
        self.default_port = int(self.gui_config.get("port", 8889))
        
        self._setup_window()
        self._cleanup_on_start()
        self._build_ui()
        
        # Connect signals AFTER UI is built
        self.sig_log.connect(lambda m, t: self._append_log(self.txt_log, m, t))
        self.sig_olog.connect(lambda m, t: self._append_log(self.txt_orbit_log, m, t))
        self.sig_ylog.connect(lambda m, t: self._append_log(self.txt_yaoce_log, m, t))
        self.sig_sim_prog.connect(self._apply_sim_prog)
        self.sig_orbit_prog.connect(self._apply_orbit_prog)
        self.sig_reset_ui.connect(self._reset_ui)
        self.sig_orbit_done.connect(self._orbit_done_ui)
        self.sig_export_ready.connect(lambda: self.btn_export.setEnabled(True))
        # Start the endpoint when the main window is ready; forwarding still
        # requires a live FMU worker.
        self.log("[*] 初始化后准备启动变量注入监听", "sys")
        self._start_injection_listener()
        self.ui_heartbeat_timer = QTimer(self)
        self.ui_heartbeat_timer.timeout.connect(self._write_ui_heartbeat)
        self.ui_heartbeat_timer.start(10000)

    def _begin_resize_perf_mode(self):
        if self._resize_perf_mode:
            return
        self._resize_perf_mode = True
        try:
            disable_blur_behind(self.winId())
        except Exception:
            pass
        try:
            self.setUpdatesEnabled(False)
            self.root_container.setUpdatesEnabled(False)
        except Exception:
            pass

    def _end_resize_perf_mode(self):
        if not self._resize_perf_mode:
            return
        self._resize_perf_mode = False
        try:
            self.root_container.setUpdatesEnabled(True)
            self.setUpdatesEnabled(True)
        except Exception:
            pass
        try:
            set_blur_behind(self.winId())
        except Exception:
            pass
        self.update()

    def resizeEvent(self, event):
        if not self.isMaximized() and not self.isFullScreen():
            self._begin_resize_perf_mode()
            self._resize_restore_timer.start(180)
        return super().resizeEvent(event)

    def _cleanup_on_start(self):
        """ 清理旧的日志和临时文件，确保空间不膨胀 """
        try:
            # 1. 清理旧的 raw_record 模式日志
            import glob
            old_logs = glob.glob(os.path.join(APP_DIR, "raw_record_*.log"))
            for f in old_logs:
                try: os.remove(f)
                except: pass
            
            # 2. 清理 C 盘临时工作目录 (如果存在且未被占用)
            import shutil
            runtime_dir = "C:\\FmuSolver_Runtime"
            if os.path.exists(runtime_dir):
                # 仅尝试删除子文件夹，避免删除根目录失败
                for item in os.listdir(runtime_dir):
                    item_path = os.path.join(runtime_dir, item)
                    try:
                        if os.path.isdir(item_path): shutil.rmtree(item_path)
                        else: os.remove(item_path)
                    except: pass
        except: pass

    def _setup_window(self):
        # 优先从资源目录加载图标 (兼容 OneFile 打包)
        icon_path = get_resource_path("fmusolver_full.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(APP_DIR, "fmusolver_full.ico")
            
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.resize(1100, 780)
        cfg_path = os.path.join(APP_DIR, "gui_config.json")
        bg_c = QColor(240, 242, 246)
        txt_c = None
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                    if "bg" in d: bg_c = QColor(d["bg"])
                    if "text" in d: txt_c = QColor(d["text"])
            except: pass
        self.apply_theme(bg_c, txt_c)

    def _build_ui(self):
        # High Fidelity Main Container with Frosted Layering
        self.root_container = QWidget()
        self.root_container.setObjectName("MainContainer")
        self.root_container.setAttribute(Qt.WA_StyledBackground, True)
        self.setCentralWidget(self.root_container)
        
        vlay = QVBoxLayout(self.root_container)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        # 1. macOS TitleBar
        self.title_bar = TitleBar(self)
        vlay.addWidget(self.title_bar)
        
        # 2. Navigation (Floating Island)
        nav_wrap = QWidget()
        nav_h = QHBoxLayout(nav_wrap)
        nav_h.setContentsMargins(18, 14, 18, 10)
        self.seg = SegmentedControl(["轨道预示计算", "实时仿真控制", "遥测接收转发"])
        nav_h.addWidget(self.seg)
        nav_h.addStretch()
        vlay.addWidget(nav_wrap)

        # 3. Content
        from PySide6.QtWidgets import QStackedWidget
        self.stack = QStackedWidget()
        self.stack.setObjectName("ContentStack")
        self.stack.setAttribute(Qt.WA_StyledBackground, True)
        
        self.tab_orbit = QScrollArea()
        self.tab_sim   = QScrollArea()
        self.tab_yaoce = QScrollArea()
        
        for t in [self.tab_orbit, self.tab_sim, self.tab_yaoce]:
            t.setWidgetResizable(True)
            t.setFrameShape(QFrame.NoFrame)
            t.setStyleSheet("QScrollArea, QWidget#qt_scrollarea_viewport { background: transparent; border: none; }")
            t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.stack.addWidget(t)
            
        self.seg.changed.connect(self.stack.setCurrentIndex)
        vlay.addWidget(self.stack, 1)

        # Initial Build
        self.tab_sim.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._build_orbit_tab()
        self._build_sim_tab()
        self._build_yaoce_tab()
        self._restore_form_config()

    def _update_led(self, state):
        m = {
            "ready":   ("#28C840", "READY"),
            "running": ("#28C840", "RUNNING"),
            "error":   ("#FF3B30", "ERROR"),
            "stopped": ("#FF9F0A", "STOPPED")
        }
        dot_c, label = m.get(state, ("#28C840", "READY"))
        self.title_bar.led_dot.setStyleSheet(f"color: {dot_c}; font-size: 14px; margin-right: 4px;")
        self.title_bar.led_txt.setText(label)

    def _kill_process_tree(self, proc):
        if not proc or proc.poll() is not None:
            return
        try:
            if os.name == 'nt':
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(proc.pid)], creationflags=0x08000000)
            else:
                proc.terminate()
                proc.wait(timeout=1)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def closeEvent(self, event):
        """退出时确保所有子进程都已关闭"""
        try:
            self._save_gui_config()
        except:
            pass
        try:
            for p in [self.visualizer_process, self.worker_process, self.orbit_proc, getattr(self, 'yaoce_proc', None)]:
                self._kill_process_tree(p)
        except: pass
        try:
            if hasattr(self, 'inj_stop_events') and self.inj_stop_events:
                for ev in self.inj_stop_events:
                    try: ev.set()
                    except: pass
        except: pass
        try:
            if hasattr(self, 'runtime_logger') and self.runtime_logger:
                self.runtime_logger.close()
        except: pass
        super().closeEvent(event)

    def _apply_sim_prog(self, pct, text):
        self.sim_progress.setValue(pct)
        self.sim_prog_lbl.setText(f"仿真计算进度: {pct}% | {text}")

    def _apply_orbit_prog(self, pct, text):
        self.orbit_progress.setValue(pct)
        self.orbit_prog_lbl.setText(f"轨道预示进度: {pct}% | {text}")

    def _orbit_done_ui(self):
        self.btn_run_orbit.setText("▶ 开始预示解算")
        self.btn_run_orbit.setEnabled(True)
        if hasattr(self, 'btn_pause_orbit'):
            self.btn_pause_orbit.setEnabled(False)
            self.btn_pause_orbit.setText("⏸ 暂停")
        self.btn_stop_orbit.setEnabled(False)
        self.orbit_paused = False

    def _load_gui_config(self):
        if os.path.exists(self.gui_config_path):
            try:
                with open(self.gui_config_path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if isinstance(d, dict): return d
            except: pass
        return {}

    def _save_gui_config(self):
        data = self._load_gui_config()
        data.update({
            "sim_fmu":    self.fmu_path_edit.text().strip(),
            "orbit_fmu":  self.orbit_fmu_edit.text().strip(),
            "yaoce_dir":  getattr(self, "yaoce_dir", ""),
            "ip":         self.ip_edit.edit.text().strip(),
            "port":       self.port_edit.edit.text().strip(),
            "inj_ip":     self.inj_ip_edit.edit.text().strip(),
            "inj_port":   self.inj_port_edit.edit.text().strip(),
            "replace_dot": self.chk_replace_dot.isChecked(),
            "auto_vis":   self.chk_auto_vis.isChecked(),
            "orbit_year": self.year_e.edit.text().strip(),
            "orbit_mon":  self.mon_e.edit.text().strip(),
            "orbit_day":  self.day_e.edit.text().strip(),
            "orbit_hour": self.hour_e.edit.text().strip(),
            "orbit_min":  self.min_e.edit.text().strip(),
            "orbit_sec":  self.sec_e.edit.text().strip(),
            "orbit_a":    self.a_e.edit.text().strip(),
            "orbit_ecc":  self.ecc_e.edit.text().strip(),
            "orbit_inc":  self.inc_e.edit.text().strip(),
            "orbit_om":   self.om_e.edit.text().strip(),
            "orbit_w":    self.w_e.edit.text().strip(),
            "orbit_f":    self.f_e.edit.text().strip(),
            "orbit_step": self.o_step_e.edit.text().strip(),
            "orbit_rate": self.o_rate_e.edit.text().strip(),
            "orbit_freq": self.o_freq_e.edit.text().strip(),
            "orbit_dur":  self.o_dur_e.edit.text().strip(),
            "cj_year":    self.cj_year_e.edit.text().strip(),
            "cj_mon":     self.cj_mon_e.edit.text().strip(),
            "cj_day":     self.cj_day_e.edit.text().strip(),
            "cj_hour":    self.cj_hour_e.edit.text().strip(),
            "cj_min":     self.cj_min_e.edit.text().strip(),
            "cj_sec":     self.cj_sec_e.edit.text().strip(),
            "table_a":    self.cj_ta_e.edit.text().strip(),
            "table_b":    self.cj_tb_e.edit.text().strip(),
            "table_fb":   self.cj_tfb_e.edit.text().strip(),
            "table_att":  self.cj_tatt_e.edit.text().strip(),
            "point_sun":  self.chk_pointsun.isChecked(),
            "sim_step":   self.step_e.edit.text().strip(),
            "sim_rate":   self.rate_e.edit.text().strip(),
            "sim_freq":   self.freq_e.edit.text().strip(),
            "sim_time":   self.time_e.edit.text().strip(),
        })
        try:
            with open(self.gui_config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.gui_config = data
        except: pass

    def _restore_form_config(self):
        cfg = self.gui_config if isinstance(self.gui_config, dict) else {}

        orbit_defaults = {
            self.year_e.edit: ("orbit_year", "2026"),
            self.mon_e.edit: ("orbit_mon", "4"),
            self.day_e.edit: ("orbit_day", "10"),
            self.hour_e.edit: ("orbit_hour", "8"),
            self.min_e.edit: ("orbit_min", "0"),
            self.sec_e.edit: ("orbit_sec", "0.0"),
            self.a_e.edit: ("orbit_a", "6766.71777"),
            self.ecc_e.edit: ("orbit_ecc", "0.00110"),
            self.inc_e.edit: ("orbit_inc", "41.627"),
            self.om_e.edit: ("orbit_om", "137.492"),
            self.w_e.edit: ("orbit_w", "77.010"),
            self.f_e.edit: ("orbit_f", "57.552"),
            self.o_step_e.edit: ("orbit_step", "10.0"),
            self.o_rate_e.edit: ("orbit_rate", "0.0"),
            self.o_freq_e.edit: ("orbit_freq", "0.1"),
            self.o_dur_e.edit: ("orbit_dur", "86400.0"),
        }
        for widget, (key, fallback) in orbit_defaults.items():
            widget.setText(str(cfg.get(key, fallback)))

        sim_defaults = {
            self.ip_edit.edit: ("ip", "127.0.0.1"),
            self.port_edit.edit: ("port", "8889"),
            self.inj_ip_edit.edit: ("inj_ip", "0.0.0.0"),
            self.inj_port_edit.edit: ("inj_port", "9988"),
            self.cj_year_e.edit: ("cj_year", "2026"),
            self.cj_mon_e.edit: ("cj_mon", "3"),
            self.cj_day_e.edit: ("cj_day", "31"),
            self.cj_hour_e.edit: ("cj_hour", "12"),
            self.cj_min_e.edit: ("cj_min", "19"),
            self.cj_sec_e.edit: ("cj_sec", "0.0"),
            self.cj_ta_e.edit: ("table_a", "1000, 3640; 2000, 3640"),
            self.cj_tb_e.edit: ("table_b", "1000, 3640; 2000, 3640"),
            self.cj_tfb_e.edit: ("table_fb", "1000, 360, 184; 2000, 300, 184"),
            self.cj_tatt_e.edit: ("table_att", "1000, 0, 3, 90, 2000, 0, 3, 90"),
            self.step_e.edit: ("sim_step", "0.02"),
            self.rate_e.edit: ("sim_rate", "1.0"),
            self.freq_e.edit: ("sim_freq", "50.0"),
            self.time_e.edit: ("sim_time", "86400.0"),
        }
        for widget, (key, fallback) in sim_defaults.items():
            widget.setText(str(cfg.get(key, fallback)))

        self.chk_replace_dot.setChecked(bool(cfg.get("replace_dot", False)))
        self.chk_auto_vis.setChecked(bool(cfg.get("auto_vis", True)))
        self.chk_pointsun.setChecked(bool(cfg.get("point_sun", False)))

    def _resolve_sim_fmu(self):
        a = auto_find_fmu(["MTLibrary_System_EPS_PD_EPS_CJ.fmu","FMU_Model1.fmu","TestFmu.fmu"],["eps","cj"])
        return a or _norm_existing(self.gui_config.get("sim_fmu")) or ""

    def _resolve_orbit_fmu(self):
        a = auto_find_fmu(["MTLibrary_System_EPS_PD_Orbit_Pre.fmu"],["orbit","pre"])
        return a or _norm_existing(self.gui_config.get("orbit_fmu")) or ""

    def _resolve_yaoce_dir(self):
        a = auto_find_yaoce_dir()
        return a or _norm_existing(self.yaoce_dir if hasattr(self, 'yaoce_dir') else None) or self.gui_config.get("yaoce_dir") or os.path.normpath(os.path.join(APP_DIR,"yaocetest"))

    def _child_env(self):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["FMUSOLVER_PARENT_PID"] = str(os.getpid())
        env.setdefault("FMUSOLVER_VIZ_SEND_HZ", "5.0")
        env.setdefault("FMUSOLVER_VIZ_PORTS", "22345,8888")
        env.setdefault("FMUSOLVER_EXT_INJECT_MIN_INTERVAL", "0.2")
        env.setdefault("FMUSOLVER_SENSITIVE_INJECT_MIN_INTERVAL", "1.0")
        env.setdefault("FMUSOLVER_INJECTION_STDOUT_INTERVAL", "10.0")
        env.setdefault("FMUSOLVER_EXT_INJECT_GRACE_SIM_SEC", "2.0")
        return env

    def _append_runtime_log(self, line):
        try:
            important = "[ERROR]" in str(line) or "[!]" in str(line) or "Fatal" in str(line) or "Traceback" in str(line)
            logger = getattr(self, 'runtime_logger', None)
            if logger:
                logger.log(line, important=important)
        except Exception:
            pass

    def _write_ui_heartbeat(self):
        try:
            proc_info = ""
            if os.name == 'nt':
                try:
                    import ctypes
                    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong), ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t), ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t), ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t), ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
                    counters = PROCESS_MEMORY_COUNTERS(); counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                    if ctypes.WinDLL('psapi').GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                        proc_info = f" ui_mem={counters.WorkingSetSize // (1024*1024)}MB"
                except Exception:
                    pass
            self._append_runtime_log(
                f"[HEARTBEAT][UI] worker_alive={bool(self.worker_process and self.worker_process.poll() is None)} "
                f"yaoce_alive={bool(getattr(self, 'yaoce_proc', None) and self.yaoce_proc.poll() is None)} "
                f"viz_alive={bool(self.visualizer_process and self.visualizer_process.poll() is None)} "
                f"log_blocks={self.txt_log.document().blockCount() if hasattr(self, 'txt_log') else -1} "
                f"yc_log_blocks={self.txt_yaoce_log.document().blockCount() if hasattr(self, 'txt_yaoce_log') else -1}{proc_info}"
            )
        except Exception:
            pass

    def pick_theme(self):
        bg_color = self._open_color_dialog(QColor(240, 242, 246), "选择主背景颜色")
        if not bg_color.isValid(): return
        brightness = (bg_color.red() * 299 + bg_color.green() * 587 + bg_color.blue() * 114) / 1000
        default_text = QColor(255, 255, 255) if brightness < 128 else QColor(17, 17, 17)
        text_color = self._open_color_dialog(default_text, "选择全局字体颜色")
        if text_color.isValid():
            self.apply_theme(bg_color, text_color)

    def _open_color_dialog(self, current, title):
        if getattr(sys, 'frozen', False):
            runner = [sys.executable]
        else:
            runner = [sys.executable, os.path.abspath(__file__)]

        try:
            completed = subprocess.run(
                runner + ["--pickcolor", current.name(), title],
                capture_output=True,
                text=True,
                cwd=APP_DIR,
                env=self._child_env(),
                creationflags=0x08000000 if os.name == 'nt' else 0,
                timeout=180,
            )
            picked = (completed.stdout or '').strip()
            color = QColor(picked)
            if completed.returncode == 0 and color.isValid():
                return color
        except Exception:
            pass

        return QColor()

    def apply_theme(self, base_color, text_color=None):
        self.current_bg = base_color
        r, g, b = base_color.red(), base_color.green(), base_color.blue()
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        is_dark = brightness < 128
        
        if text_color:
            self.current_text = text_color
            text_c = text_color.name()
        else:
            text_c = "#FFFFFF" if is_dark else "#111111"
            
        main_bg = f"rgba({r}, {g}, {b}, 215)"
        
        if is_dark:
            cr, cg, cb = min(r+25, 255), min(g+25, 255), min(b+25, 255)
        else:
            cr, cg, cb = min(r+15, 255), min(g+15, 255), min(b+15, 255)
            
        card_bg = f"rgba({cr}, {cg}, {cb}, 250)"
        btn_border = "rgba(255, 255, 255, 40)" if is_dark else "rgba(205, 210, 220, 235)"
        btn_bg = f"rgba({cr}, {cg}, {cb}, 245)"
        btn_hover = f"rgba({min(cr+15, 255)}, {min(cg+15, 255)}, {min(cb+15, 255)}, 250)"
        input_bg = "rgba(0, 0, 0, 50)" if is_dark else "rgba(0, 0, 0, 13)"
        
        seg_bg = "rgba(255, 255, 255, 30)" if is_dark else "rgba(0, 0, 0, 15)"
        seg_btn_hover = "rgba(255, 255, 255, 50)" if is_dark else "rgba(255, 255, 255, 80)"
        seg_btn_active = "rgba(0, 0, 0, 180)" if is_dark else "rgba(255, 255, 255, 252)"
        seg_btn_active_text = "#FFFFFF" if is_dark else "#111111"
        
        # Persistence
        try:
            data = self._load_gui_config()
            data["bg"] = base_color.name()
            data["text"] = text_c
            with open(self.gui_config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.gui_config = data
        except: pass
        
        qss = f"""
        QMainWindow, QDialog {{ background: transparent; color: {text_c}; font-family: 'SF Pro Display', 'Inter', 'PingFang SC', 'Microsoft YaHei UI', sans-serif; font-size: 13px; }}
        QWidget#MainContainer {{ background: {main_bg}; border: none; border-radius: 12px; }}
        QWidget#TitleBar {{ background: transparent; border-top-left-radius: 12px; border-top-right-radius: 12px; border-bottom: 1px solid rgba(255,255,255,40); }}
        QWidget#TabContainer {{ background: transparent; border: none; }}
        QWidget#ContentStack {{ background: transparent; }}
        QLabel#BrandLabel, QLabel#HeaderLabel {{ color: {text_c}; font-size: 14px; font-weight: 800; }}
        QLabel#VersionBadge {{ color: {text_c}; background: rgba(255,255,255,90); border: 1px solid rgba(255,255,255,70); border-radius: 8px; padding: 2px 7px; font-size: 10px; font-weight: 800; }}
        QLabel#SubHeaderLabel, QLabel#StatusText, QLabel#Muted, QLabel#ParamLabel {{ color: {text_c}; font-weight: 600; font-size: 12px; }}
        QLabel#StatusText {{ font-size: 11px; font-weight: 700; }}
        QLabel#SubHeaderLabel {{ font-size: 11px; opacity: 0.8; }}
        QLabel#ParamLabel {{ font-size: 11px; opacity: 0.8; }}
        
        QPushButton#ControlBtn {{ min-width: 14px; max-width: 14px; min-height: 14px; max-height: 14px; padding: 0; margin: 0; border: none; border-radius: 7px; }}
        QPushButton#ThemeBtn {{ min-width: 14px; max-width: 14px; min-height: 14px; max-height: 14px; padding: 0; border: none; border-radius: 7px; background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FF5F56, stop:0.5 #FFBD2E, stop:1 #27C93F); }}
        QPushButton#ThemeBtn:hover {{ border: 1px solid rgba(255,255,255,180); }}
        
        QFrame#Card {{ background: {card_bg}; border: 1px solid {btn_border}; border-radius: 14px; }}
        QFrame#SegTrack {{ background: {seg_bg}; border: 1px solid rgba(0, 0, 0, 8); border-radius: 17px; }}
        QPushButton#SegBtn {{ background: transparent; color: {text_c}; border: none; border-radius: 15px; padding: 0 14px; min-height: 32px; max-height: 32px; font-weight: 600; font-size: 13px; }}
        QPushButton#SegBtn:hover {{ background: {seg_btn_hover}; color: {text_c}; }}
        QPushButton#SegBtnActive {{ background: {seg_btn_active}; color: {seg_btn_active_text}; border: none; border-radius: 15px; padding: 0 14px; min-height: 32px; max-height: 32px; font-weight: 800; font-size: 13px; }}
        QLabel#Title {{ color: {text_c}; font-size: 12pt; font-weight: 800; }}
        
        QLineEdit#PathEdit, QLineEdit#ParamEdit, QLineEdit#SeriesEdit {{ background: {input_bg}; border: none; border-radius: 6px; color: {text_c}; font-family: 'SF Mono', 'Cascadia Mono', 'Consolas', monospace; font-weight: 600; padding: 0 10px; }}
        QLineEdit#PathEdit {{ min-height: 30px; max-height: 30px; font-size: 11px; }}
        QLineEdit#ParamEdit {{ min-height: 30px; max-height: 30px; font-size: 12px; }}
        QLineEdit#SeriesEdit {{ min-height: 30px; max-height: 30px; font-size: 11px; border-bottom: 1px solid rgba(128,128,128,50); background: transparent; }}
        QLineEdit#ParamEdit:focus, QLineEdit#PathEdit:focus {{ background: {card_bg}; border: 1px solid rgba(0, 122, 255, 90); }}
        
        QPushButton {{ background: {btn_bg}; color: {text_c}; border: 1px solid {btn_border}; border-radius: 16px; padding: 0 14px; font-weight: 700; font-size: 13px; min-height: 34px; max-height: 34px; }}
        QPushButton:hover {{ background: {btn_hover}; }}
        QPushButton:disabled {{ color: {text_c}; opacity: 0.5; background: rgba(128, 128, 128, 30); border: 1px solid rgba(128, 128, 128, 20); }}
        QPushButton#PrimaryAction {{ background: #007AFF; color: white; border: 1px solid rgba(0, 98, 204, 235); font-weight: 800; }}
        QPushButton#Danger {{ background: rgba(255, 59, 48, 42); color: #FF3B30; border: 1px solid rgba(255, 59, 48, 120); font-weight: 800; }}
        
        QCheckBox {{ spacing: 8px; font-size: 12px; color: {text_c}; font-weight: 600; }}
        QCheckBox::indicator {{ width: 15px; height: 15px; border-radius: 4px; background: {card_bg}; border: 1px solid {btn_border}; }}
        QCheckBox::indicator:checked {{ background: #007AFF; border: 1px solid #007AFF; }}
        
        QProgressBar {{ background: rgba(0, 0, 0, 10); border: none; border-radius: 3px; min-height: 6px; max-height: 6px; text-align: center; color: transparent; }}
        QProgressBar::chunk {{ background: #2F8CFF; border-radius: 3px; }}
        
        QFrame#ConsoleShell {{ background: rgba(30, 30, 30, 242); border: none; border-radius: 12px; }}
        QTextEdit#Console {{ background: transparent; color: #FFFFFF; border: none; font-family: 'SF Mono', 'Consolas', monospace; font-size: 11px; line-height: 1.4; }}
        QPushButton#ConsoleToggle {{ background: rgba(255,255,255,26); color: #FFFFFF; border: 1px solid rgba(255,255,255,42); border-radius: 7px; padding: 0 10px; font-size: 11px; font-weight: 700; }}
        QPushButton#ConsoleToggle:hover {{ background: rgba(255,255,255,42); }}
        
        QScrollBar:vertical {{ border: none; background: transparent; width: 8px; margin: 0px 0px 0px 0px; }}
        QScrollBar::handle:vertical {{ background: rgba(128, 128, 128, 100); min-height: 30px; border-radius: 4px; }}
        QScrollBar::handle:vertical:hover {{ background: rgba(128, 128, 128, 150); }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QScrollBar:horizontal {{ height: 0px; }}
        """
        self.setStyleSheet(qss)

    def open_theme_dialog(self):
        dlg = ThemeDialog(self)
        dlg.exec_()

    def _build_orbit_tab(self):
        w = QWidget(); w.setObjectName("TabContainer"); lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 6, 10, 6); lay.setSpacing(6)

        config_panel = card(); config_l = QVBoxLayout(config_panel)
        config_l.setContentsMargins(12, 10, 12, 10); config_l.setSpacing(6)
        config_l.addWidget(lbl("轨道预示配置", obj="Title"))

        path_row = QHBoxLayout(); path_row.setSpacing(8)
        self.orbit_fmu_edit = QLineEdit(self.default_orbit_fmu)
        self.orbit_fmu_edit.setObjectName("PathEdit")
        self.orbit_fmu_edit.setFixedHeight(26)
        b_browse = btn("浏览...", True)
        b_browse.clicked.connect(self._browse_orbit_fmu)
        path_row.addWidget(self.orbit_fmu_edit, 1); path_row.addWidget(b_browse)
        config_l.addLayout(path_row)

        g2 = QGridLayout(); g2.setHorizontalSpacing(10); g2.setVerticalSpacing(4)
        self.year_e = pill_field("Year (北京时间):", "2026"); self.mon_e = pill_field("Month (北京时间):", "4"); self.day_e = pill_field("Day (北京时间):", "10")
        self.hour_e = pill_field("Hour (北京时间):", "8"); self.min_e = pill_field("Min (北京时间):", "0"); self.sec_e = pill_field("Sec (北京时间):", "0.0")
        g2.addWidget(self.year_e, 0, 0); g2.addWidget(self.mon_e, 0, 1); g2.addWidget(self.day_e, 0, 2)
        g2.addWidget(self.hour_e, 1, 0); g2.addWidget(self.min_e, 1, 1); g2.addWidget(self.sec_e, 1, 2)
        config_l.addLayout(g2)

        config_l.addWidget(divider())
        g2e = QGridLayout(); g2e.setHorizontalSpacing(10); g2e.setVerticalSpacing(4)
        self.a_e = pill_field("MTC半长轴 A (KM):", "6766.71777"); self.ecc_e = pill_field("MTC偏心率 E:", "0.00110"); self.inc_e = pill_field("MTC轨道倾角 I (deg):", "41.627")
        self.om_e = pill_field("MTC升交点赤经 Ω (deg):", "137.492"); self.w_e = pill_field("MTC近地点幅角 ω (deg):", "77.010"); self.f_e = pill_field("MTC真近点角 F (deg):", "57.552")
        g2e.addWidget(self.a_e, 0, 0); g2e.addWidget(self.ecc_e, 0, 1); g2e.addWidget(self.inc_e, 0, 2)
        g2e.addWidget(self.om_e, 1, 0); g2e.addWidget(self.w_e, 1, 1); g2e.addWidget(self.f_e, 1, 2)
        config_l.addLayout(g2e)

        strategy = QGridLayout(); strategy.setHorizontalSpacing(10); strategy.setVerticalSpacing(4)
        self.o_step_e = pill_field("步长 (S):", "10.0"); self.o_rate_e = pill_field("速率 (1X):", "0.0")
        self.o_freq_e = pill_field("采样 (HZ):", "0.1"); self.o_dur_e = pill_field("时长 (S):", "86400.0")
        strategy.addWidget(self.o_step_e, 0, 0); strategy.addWidget(self.o_rate_e, 0, 1)
        strategy.addWidget(self.o_freq_e, 1, 0); strategy.addWidget(self.o_dur_e, 1, 1)
        config_l.addLayout(strategy)
        lay.addWidget(config_panel)

        execution_panel = card(); exec_l = QVBoxLayout(execution_panel)
        exec_l.setContentsMargins(12, 8, 12, 8); exec_l.setSpacing(6)
        exec_l.addWidget(lbl("运行控制", obj="Title"))
        self.orbit_progress = QProgressBar(); exec_l.addWidget(self.orbit_progress)
        self.orbit_prog_lbl = lbl("等待启动...", obj="Muted"); self.orbit_prog_lbl.setAlignment(Qt.AlignCenter); exec_l.addWidget(self.orbit_prog_lbl)

        act = QHBoxLayout(); act.setContentsMargins(0, 0, 0, 0); act.setSpacing(8)
        self.btn_run_orbit = btn("▶ 开始预示解答", True); self.btn_pause_orbit = btn("⏸ 暂停", False); self.btn_pause_orbit.setEnabled(False); self.orbit_paused = False; self.btn_stop_orbit = danger_btn("■ 停止运行"); self.btn_stop_orbit.setEnabled(False)
        self.btn_export = btn("↓ 导出结果", False); self.btn_export.setEnabled(False)
        self.btn_run_orbit.clicked.connect(self.run_orbit_precalc); self.btn_pause_orbit.clicked.connect(self.toggle_orbit_pause); self.btn_stop_orbit.clicked.connect(self.stop_orbit); self.btn_export.clicked.connect(self.export_orbit_txt)
        act.addStretch(); act.addWidget(self.btn_run_orbit); act.addWidget(self.btn_pause_orbit); act.addWidget(self.btn_stop_orbit); act.addWidget(self.btn_export); act.addStretch()
        exec_l.addLayout(act)
        lay.addWidget(execution_panel)

        self.txt_orbit_log = QTextEdit()
        self.txt_orbit_log.document().setMaximumBlockCount(300)
        lay.addWidget(console_panel("轨道预示运行日志", self.txt_orbit_log, min_height=100))
        lay.addStretch(1)

        self.tab_orbit.setWidget(w)
        self.year_edit = self.year_e.edit; self.mon_edit = self.mon_e.edit; self.day_edit = self.day_e.edit
        self.hour_edit_o = self.hour_e.edit; self.min_edit_o = self.min_e.edit; self.sec_edit_o = self.sec_e.edit
        self.a_edit = self.a_e.edit; self.ecc_edit = self.ecc_e.edit; self.inc_edit = self.inc_e.edit
        self.om_edit = self.om_e.edit; self.w_edit = self.w_e.edit; self.f_edit = self.f_e.edit
        self.o_step_edit = self.o_step_e.edit; self.o_rate_edit = self.o_rate_e.edit; self.o_freq_edit = self.o_freq_e.edit; self.o_dur_edit = self.o_dur_e.edit

    def _build_sim_tab(self):
        w = QWidget(); w.setObjectName("TabContainer"); lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 6, 10, 6); lay.setSpacing(6)

        c1 = card(); cl1 = QVBoxLayout(c1); cl1.setContentsMargins(12, 10, 12, 10); cl1.setSpacing(6)
        cl1.addWidget(lbl("1. 模型与路径配置", obj="Title"))
        row1 = QHBoxLayout(); row1.setSpacing(8)
        self.fmu_path_edit = QLineEdit(self.default_sim_fmu)
        self.fmu_path_edit.setObjectName("PathEdit")
        self.fmu_path_edit.setFixedHeight(26)
        b_sim_browse = btn("浏览...", True)
        b_sim_browse.clicked.connect(self.browse_file)
        row1.addWidget(self.fmu_path_edit, 1); row1.addWidget(b_sim_browse)
        cl1.addLayout(row1)
        lay.addWidget(c1)

        c2 = card(); cl2 = QVBoxLayout(c2); cl2.setContentsMargins(12, 10, 12, 10); cl2.setSpacing(6)
        title2_row = QHBoxLayout()
        title2_row.addWidget(lbl("2. 通信网络设置", obj="Title"))
        title2_row.addStretch()
        title2_row.addWidget(lbl("🛜", obj="Muted"))
        cl2.addLayout(title2_row)
        
        g2 = QGridLayout(); g2.setHorizontalSpacing(12); g2.setVerticalSpacing(4)
        self.ip_edit = pill_field("远程推送地址 (Remote IP):", self.default_ip)
        self.port_edit = pill_field("远程回传端口 (Remote Port):", str(self.default_port))
        self.inj_ip_edit = pill_field("注入监听地址 (Inj IP):", "0.0.0.0")
        self.inj_port_edit = pill_field("注入监听端口 (Inj Port):", "9988")
        
        g2.addWidget(self.ip_edit, 0, 0); g2.addWidget(self.port_edit, 0, 1)
        g2.addWidget(self.inj_ip_edit, 1, 0); g2.addWidget(self.inj_port_edit, 1, 1)
        cl2.addLayout(g2)
        
        self.chk_replace_dot = QCheckBox(" 将变量名中的 ':' 转换为 '_' (兼容模式)")
        self.chk_replace_dot.setChecked(self.gui_config.get("replace_dot", False))
        self.chk_replace_dot.setStyleSheet("QCheckBox { margin-left: 4px; padding-left: 2px; }")
        cl2.addWidget(self.chk_replace_dot)
        lay.addWidget(c2)

        c3 = card(); cl3 = QVBoxLayout(c3); cl3.setContentsMargins(12, 10, 12, 10); cl3.setSpacing(6)
        cl3.addWidget(lbl("3. 初值与参数定义 (EPS_CJ)", obj="Title"))
        
        g3 = QGridLayout(); g3.setHorizontalSpacing(10); g3.setVerticalSpacing(4)
        self.cj_year_e = pill_field("Year (北京时间):", "2026")
        self.cj_mon_e = pill_field("Mon (北京时间):", "3"); self.cj_day_e = pill_field("Day (北京时间):", "31")
        self.cj_hour_e = pill_field("Hour (北京时间):", "12"); self.cj_min_e = pill_field("Min (北京时间):", "19"); self.cj_sec_e = pill_field("Sec (北京时间):", "0.0")
        g3.addWidget(self.cj_year_e, 0, 0); g3.addWidget(self.cj_mon_e, 0, 1); g3.addWidget(self.cj_day_e, 0, 2)
        g3.addWidget(self.cj_hour_e, 1, 0); g3.addWidget(self.cj_min_e, 1, 1); g3.addWidget(self.cj_sec_e, 1, 2)
        cl3.addLayout(g3)

        self.cj_ta_e = pill_field("Table_A (A母线负载时序表，第一列为时间段、第二列为负载功耗值):", "1000, 3640; 2000, 3640", wide=True)
        self.cj_tb_e = pill_field("Table_B (B母线负载时序表，第一列为时间段、第二列为负载功耗值):", "1000, 3640; 2000, 3640", wide=True)
        self.cj_tfb_e = pill_field("Table_FB (帆板转角时序表，第1列为时间段，第2列为Beta转角(deg),第3列为Alpha转角(deg)):", "1000, 360, 184; 2000, 300, 184", wide=True)
        self.cj_tatt_e = pill_field("Table_Att (MTC姿态时序表，第1列为时间段，第2列为滚转角(deg),第2列为俯仰转角(deg),第3列为偏航转角(deg)组合体状态90度，单舱飞行为0deg):", "1000, 0, 3, 90, 2000, 0, 3, 90", wide=True)
        for p in [self.cj_ta_e, self.cj_tb_e, self.cj_tfb_e, self.cj_tatt_e]: cl3.addWidget(p)

        note = QHBoxLayout(); note.setSpacing(8)
        note.addWidget(lbl("备注: 数据序列格式为 '时间, 值1, 值2; ...' 按时间升序排列", obj="Muted"))
        note.addStretch()
        self.chk_pointsun = QCheckBox("Alpha轴对日定向 (PointSun)")
        self.chk_pointsun.setObjectName("SwitchCheck")
        note.addWidget(self.chk_pointsun)
        cl3.addLayout(note)
        lay.addWidget(c3)

        c4 = card(); cl4 = QVBoxLayout(c4); cl4.setContentsMargins(12, 10, 12, 10); cl4.setSpacing(6)
        cl4.addWidget(lbl("4. 仿真策略配置", obj="Title"))
        g4 = QGridLayout(); g4.setHorizontalSpacing(12); g4.setVerticalSpacing(4)
        self.step_e = pill_field("步长 (s):", "0.02"); self.rate_e = pill_field("仿真速率 (1x):", "1.0")
        self.freq_e = pill_field("采样(Hz):", "50.0"); self.time_e = pill_field("停止 (s):", "86400.0")
        g4.addWidget(self.step_e, 0, 0); g4.addWidget(self.rate_e, 0, 1)
        g4.addWidget(self.freq_e, 1, 0); g4.addWidget(self.time_e, 1, 1)
        cl4.addLayout(g4)
        lay.addWidget(c4)

        self.sim_progress = QProgressBar(); lay.addWidget(self.sim_progress)
        self.sim_prog_lbl = lbl("等待启动...", obj="Muted"); self.sim_prog_lbl.setAlignment(Qt.AlignCenter); lay.addWidget(self.sim_prog_lbl)

        bar = QHBoxLayout(); bar.setSpacing(8)
        self.btn_start = btn("▶ 启动仿真", True); self.chk_auto_vis = QCheckBox("自动开启看板"); self.chk_auto_vis.setObjectName("SwitchCheck"); self.chk_auto_vis.setChecked(True)
        self.btn_pause = btn("⏸ 暂停", False); self.btn_pause.setEnabled(False); self.sim_paused = False
        self.btn_fields = btn("变量配置", False); self.btn_initial = btn("⚡ 同步 (0)", False); self.btn_stop = danger_btn("■ 停止"); self.btn_stop.setEnabled(False)
        self.btn_viz = btn("📊 看板", False); self.btn_out = btn("📁 输出包", False); self.status_lbl = lbl("就绪", obj="Muted")
        self.btn_start.clicked.connect(self.start_sim); self.btn_pause.clicked.connect(self.toggle_sim_pause); self.btn_stop.clicked.connect(self.stop_sim); self.btn_fields.clicked.connect(self._open_fields); self.btn_initial.clicked.connect(self.toggle_is_initial)
        self.btn_viz.clicked.connect(self._launch_viz_manual); self.btn_out.clicked.connect(lambda: os.startfile(os.path.join(APP_DIR, "txt")))
        for b in [self.btn_start, self.chk_auto_vis, self.btn_pause, self.btn_fields, self.btn_initial, self.btn_stop, self.btn_viz, self.btn_out]: bar.addWidget(b)
        bar.addStretch(); bar.addWidget(lbl("📡", obj="Muted")); bar.addWidget(self.status_lbl)
        lay.addLayout(bar)

        self.txt_log = QTextEdit()
        self.txt_log.document().setMaximumBlockCount(300)
        lay.addWidget(console_panel("实时运行状态与诊断", self.txt_log, min_height=100))
        lay.addStretch(1)
        self.tab_sim.setWidget(w)
        self.cj_year_e_edit = self.cj_year_e.edit; self.cj_mon_e_edit = self.cj_mon_e.edit; self.cj_day_e_edit = self.cj_day_e.edit
        self.cj_hour_edit = self.cj_hour_e.edit; self.cj_min_edit = self.cj_min_e.edit; self.cj_sec_edit = self.cj_sec_e.edit
        self.step_edit = self.step_e.edit; self.rate_edit = self.rate_e.edit; self.freq_edit = self.freq_e.edit; self.time_edit = self.time_e.edit
        self.ta_edit = self.cj_ta_e.edit; self.tb_edit = self.cj_tb_e.edit; self.tfb_edit = self.cj_tfb_e.edit; self.tatt_edit = self.cj_tatt_e.edit
        
    def _build_yaoce_tab(self):
        w = QWidget(); w.setObjectName("TabContainer"); lay = QVBoxLayout(w); lay.setContentsMargins(10, 6, 10, 6); lay.setSpacing(6)
        c1 = card(); cl1 = QVBoxLayout(c1); cl1.setContentsMargins(12, 10, 12, 10); cl1.setSpacing(8)
        cl1.addWidget(lbl("转发配置与过滤规则", obj="Title"))
        self.yaoce_dir_lbl = lbl(f"配置目录: {self.yaoce_dir}", obj="Muted"); cl1.addWidget(self.yaoce_dir_lbl)
        row = QHBoxLayout(); row.setSpacing(8)
        b_dir = btn("更改目录", False); b_cfg = btn("打开 config.ini", False); b_xml = btn("打开 ParamFilter.xml", False); b_rel = btn("DTS关系配置", False); b_logs = btn("打开日志文件夹", False)
        b_dir.clicked.connect(self._choose_yaoce_dir); b_cfg.clicked.connect(lambda: self._open_yaoce_file("config.ini")); b_xml.clicked.connect(lambda: self._open_yaoce_file("ParamFilter.xml")); b_rel.clicked.connect(lambda: self._open_yaoce_file("DTS.TM.Sim.Relationship.xml")); b_logs.clicked.connect(self._open_yaoce_logs)
        for bw in [b_dir, b_cfg, b_xml, b_rel, b_logs]: row.addWidget(bw)
        cl1.addLayout(row)
        lay.addWidget(c1)

        ctrl = QHBoxLayout(); ctrl.setSpacing(10)
        self.btn_yaoce_start = btn("▶ 启动转发引擎", True); self.btn_yaoce_stop = danger_btn("■ 停止服务"); self.btn_yaoce_stop.setEnabled(False)
        self.btn_yaoce_start.clicked.connect(self.start_yaoce); self.btn_yaoce_stop.clicked.connect(self.stop_yaoce)
        ctrl.addWidget(self.btn_yaoce_start, 1); ctrl.addWidget(self.btn_yaoce_stop, 1); ctrl.addStretch()
        lay.addLayout(ctrl)

        self.txt_yaoce_log = QTextEdit()
        self.txt_yaoce_log.document().setMaximumBlockCount(300)
        lay.addWidget(console_panel("实时转发调试日志", self.txt_yaoce_log, min_height=200))
        lay.addStretch(1)
        self.tab_yaoce.setWidget(w)
    def _choose_yaoce_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择遥测配置文件目录 (需包含 config.ini)", APP_DIR)
        if d:
            self.yaoce_dir = os.path.normpath(d)
            self.yaoce_dir_lbl.setText(f"当前配置读取目录: {self.yaoce_dir}")
            self._save_gui_config()

    def _open_yaoce_file(self, name):
        p = os.path.join(self.yaoce_dir, name)
        if os.path.exists(p): os.startfile(p)
        else: self.ylog(f"[!] {p} 不存在!", "error")

    def _open_yaoce_logs(self):
        log_dir = os.path.join(self.yaoce_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        os.startfile(log_dir)

    def nativeEvent(self, eventType, message):
        if eventType in ("windows_generic_MSG", b"windows_generic_MSG", "windows_dispatcher_MSG", b"windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(message.__int__())
            if msg.message == 0x0084: # WM_NCHITTEST
                pos = self.mapFromGlobal(QCursor.pos())
                lx, ly = pos.x(), pos.y()
                w, h = self.width(), self.height()

                if not self.isMaximized() and not self.isFullScreen():
                    # Prioritize resize borders so full-bleed widgets do not swallow edge hit tests.
                    bw = 10
                    if lx <= bw:
                        if ly <= bw:
                            return True, 13 # HTTOPLEFT
                        if ly >= h - bw:
                            return True, 16 # HTBOTTOMLEFT
                        return True, 10 # HTLEFT
                    if lx >= w - bw:
                        if ly <= bw:
                            return True, 14 # HTTOPRIGHT
                        if ly >= h - bw:
                            return True, 17 # HTBOTTOMRIGHT
                        return True, 11 # HTRIGHT
                    if ly <= bw:
                        return True, 12 # HTTOP
                    if ly >= h - bw:
                        return True, 15 # HTBOTTOM

                child = self.childAt(lx, ly)
                if isinstance(child, QPushButton) or (child and child.parent() and isinstance(child.parent(), QPushButton)):
                    return False

                if hasattr(self, 'title_bar') and self.title_bar.geometry().contains(pos):
                    return True, 2 # HTCAPTION

        return super().nativeEvent(eventType, message)

    def _open_fields(self):
        sync_path = os.path.join(APP_DIR, "sync_fields.json")
        dlg = FieldsDialog(sync_path, self)
        dlg.exec()

    # ─── Business Logic ───
    def _browse_orbit_fmu(self):
        initial_dir = os.path.dirname(self.orbit_fmu_edit.text().strip()) or os.path.join(APP_DIR, "FMU")
        f = QFileDialog.getOpenFileName(self, 'Open FMU', initial_dir, 'FMU Files (*.fmu)')[0]
        if f:
            self.orbit_fmu_edit.setText(os.path.normpath(f))
            self._save_gui_config()


    def _append_log(self, widget, msg, tag="sys"):
        """Internal helper to append text to log widgets with timestamps and colors."""
        if widget.property("log_collapsed"):
            return
        msg_text = str(msg)
        if ("[Live]" in msg_text or "[PERF]" in msg_text) and tag != "error":
            key = (id(widget), msg_text.split(']', 1)[0] if ']' in msg_text else msg_text[:24])
            now = time.time()
            last = self._ui_log_throttle.get(key, 0.0)
            if now - last < 5.0:
                return
            self._ui_log_throttle[key] = now
        elif tag != "error":
            key = (id(widget), msg_text[:40])
            now = time.time()
            last = self._ui_log_throttle.get(key, 0.0)
            if ("Injected " in msg_text or "Injection summary" in msg_text or "RECV Protobuf" in msg_text or "variables mirrored" in msg_text) and now - last < 5.0:
                return
            self._ui_log_throttle[key] = now
        ts = datetime.now().strftime("%H:%M:%S")
        color = "#8E8E93"
        if tag == "error": color = C_ERROR
        elif tag == "success": color = C_SUCCESS
        elif tag == "warn": color = C_WARNING

        html_msg = f'<span style="color:#666;">[{ts}]</span> <span style="color:{color};">{msg_text}</span>'

        widget.moveCursor(QTextCursor.End)
        widget.insertHtml(html_msg + "<br>")
        widget.moveCursor(QTextCursor.End)
        widget.verticalScrollBar().setValue(widget.verticalScrollBar().maximum())

    def log(self, msg, tag="sys"):
        self._append_runtime_log(f"[SIM_UI][{tag}] {msg}")
        self.sig_log.emit(str(msg), tag)

    def olog(self, msg, tag="sys"):
        self.sig_olog.emit(str(msg), tag)

    def ylog(self, msg, tag="sys"):
        self._append_runtime_log(f"[YC_UI][{tag}] {msg}")
        self.sig_ylog.emit(str(msg), tag)

    def _decode_process_line(self, data):
        """Decode mixed Python UTF-8 logs and native FMU/DLL console output safely."""
        if isinstance(data, str):
            return data.rstrip("\r\n")
        if not data:
            return ""
        for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "mbcs"):
            try:
                return data.decode(enc).rstrip("\r\n")
            except Exception:
                continue
        return data.decode("utf-8", errors="replace").rstrip("\r\n")

    def _is_structured_runner_log(self, line):
        """Structured runner logs are useful; raw FMU console chatter is throttled separately."""
        if not line:
            return False
        prefixes = ("[*]", "[OK]", "[!]", "[ERROR]", "[SUCCESS]", "[EXPORT_READY]", "[Live]")
        return line.startswith(prefixes) or line.startswith("Traceback") or "Fatal" in line
        
        

    def start_yaoce(self):
        log_file = os.path.join(APP_DIR, "yaoce_run.log")
        if getattr(sys, 'frozen', False):
            yaoce_exe = os.path.join(APP_DIR, "YaoCe_LinkLayer64.exe")
            if not os.path.exists(yaoce_exe):
                yaoce_exe = os.path.join(APP_DIR, "YaoCe_LinkLayer32.exe")
            worker_cmd = [yaoce_exe, self.yaoce_dir]
        else:
            # Source mode should launch the lightweight telemetry bridge directly.
            # Starting this whole launcher again loads Qt/UI dependencies and can exhaust memory.
            yaoce_main = os.path.join(APP_DIR, "yaocetest", "main.py")
            worker_cmd = [sys.executable, "-u", yaoce_main, self.yaoce_dir]
        
        self.btn_yaoce_start.setEnabled(False)
        self.btn_yaoce_stop.setEnabled(True)
        
        self.ylog("===========================================", "sys")
        self.ylog(f"[*] 启动底层遥测子进程... CMD={worker_cmd}", "sys")
        self.ylog(f"[*] 遥测运行日志: {log_file}", "sys")
        if getattr(sys, 'frozen', False) and not os.path.exists(worker_cmd[0]):
            self.ylog(f"[!] 遥测转发 EXE 不存在: {worker_cmd[0]}", "error")
            self.stop_yaoce()
            return
        
        # UI端主动清空老日志，避免被旧数据污染或截断判定干扰
        try:
            with open(log_file, "w", encoding="utf-8") as f: f.write("")
        except: pass

        self._yaoce_log_pos = 0
        try:
            cf = 0x08000000 if os.name == 'nt' else 0 # CREATE_NO_WINDOW
            child_env = self._child_env()
            child_env["FMUSOLVER_PE_IP"] = self.ip_edit.edit.text().strip() or "127.0.0.1"
            child_env["FMUSOLVER_PE_PORT"] = self.port_edit.edit.text().strip() or "8889"
            child_env["FMUSOLVER_LOCAL_INJECT_PORT"] = str(CONTROL_PORT)
            child_env["FMUSOLVER_YC_INJECT_FREQ"] = str(min(5.0, float(self.freq_e.edit.text() or "50.0")))
            child_env["FMUSOLVER_MERGE_TELEMETRY_VIA_WORKER"] = "1"
            child_env.setdefault("FMUSOLVER_YC_RAW_LOG_SAMPLE", "5000")
            child_env.setdefault("FMUSOLVER_YC_SEND_LOG_SAMPLE", "5000")
            child_env.setdefault("FMUSOLVER_YC_LIVE_LOG_INTERVAL", "30")
            child_env.setdefault("FMUSOLVER_YC_LOG_QUEUE_MAX", "200")
            child_env["PYTHONUNBUFFERED"] = "1"
            self.ylog(f"[*] 遥测将先注入 FMU Worker，并与仿真数据合包转发到 PE: {child_env['FMUSOLVER_PE_IP']}:{child_env['FMUSOLVER_PE_PORT']}", "sys")
            self.ylog(f"[*] 遥测同步注入到本机 FMU 监听端口: 127.0.0.1:{child_env['FMUSOLVER_LOCAL_INJECT_PORT']}", "sys")
            self._yaoce_log_handle = open(log_file, "a", encoding="utf-8", buffering=1)
            self.yaoce_proc = subprocess.Popen(worker_cmd, stdout=self._yaoce_log_handle, stderr=subprocess.STDOUT, cwd=APP_DIR, env=child_env, creationflags=cf)
            self.ylog(f"[OK] 遥测子进程已启动: pid={self.yaoce_proc.pid} cwd={APP_DIR}", "info")
            self.ylog(f"[*] 遥测诊断参数: merge_via_worker={child_env.get('FMUSOLVER_MERGE_TELEMETRY_VIA_WORKER')} data_q={child_env.get('FMUSOLVER_YC_DATA_QUEUE_MAX', '3000')} log_q={child_env.get('FMUSOLVER_YC_LOG_QUEUE_MAX', '2000')}", "sys")
            
            def poll_log():
                if not hasattr(self, 'yaoce_proc') or not self.yaoce_proc: return
                if os.path.exists(log_file):
                    try:
                        sz = os.path.getsize(log_file)
                        if sz < self._yaoce_log_pos: self._yaoce_log_pos = 0
                        with open(log_file, "r", encoding="utf-8") as f:
                            f.seek(self._yaoce_log_pos)
                            new_data = f.read()
                            self._yaoce_log_pos = f.tell()
                            if new_data:
                                lines = [l.strip() for l in new_data.split('\n') if l.strip()]
                                dropped_lines = max(0, len(lines) - 120)
                                if dropped_lines:
                                    lines = lines[-120:]
                                    self.ylog(f"[PERF][YAOCE_UI] 日志显示限流: 本轮省略 {dropped_lines} 行，完整内容仍在 yaoce_run.log", "info")
                                for l in lines:
                                    tag = "sys"
                                    if "[SEND]" in l or "[TCP/UDP]" in l or "[RECV]" in l or "[OK]" in l or "[*]" in l: tag = "info"
                                    elif "[-]" in l: tag = "error"
                                    elif "[WARN]" in l: tag = "error"
                                    elif "[!]" in l or "Error" in l or "Exception" in l: tag = "error"
                                    self.ylog(l, tag)
                    except: pass
                
                if self.yaoce_proc.poll() is None:
                    QTimer.singleShot(5000, poll_log)
                else:
                    rc = self.yaoce_proc.poll()
                    self.ylog(f"[SYS] 转发引擎退出，退出码: {rc}，完整日志: {log_file}", "sys" if rc == 0 else "error")
                    if hasattr(self, '_yaoce_log_handle') and self._yaoce_log_handle:
                        try: self._yaoce_log_handle.close()
                        except: pass
                        self._yaoce_log_handle = None
                    self.btn_yaoce_start.setEnabled(True)
                    self.btn_yaoce_stop.setEnabled(False)

            QTimer.singleShot(5000, poll_log)
        except Exception as e:
            self.ylog(f"[!] 独立子进程启动致命失败: {e}", "error")
            self.stop_yaoce()



    def stop_yaoce(self):
        if hasattr(self, 'yaoce_proc') and self.yaoce_proc:
            try:
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.yaoce_proc.pid)], creationflags=subprocess.CREATE_NO_WINDOW)
                self.ylog("[*] 发送强制终止指令...", "error")
            except: pass
            self.yaoce_proc = None
        if hasattr(self, '_yaoce_log_handle') and self._yaoce_log_handle:
            try: self._yaoce_log_handle.close()
            except: pass
            self._yaoce_log_handle = None
        self.btn_yaoce_start.setEnabled(True)
        self.btn_yaoce_stop.setEnabled(False)


    def browse_file(self):
        initial_dir = os.path.dirname(self.fmu_path_edit.text().strip()) or os.path.join(APP_DIR, "FMU")
        f = QFileDialog.getOpenFileName(self, 'Open FMU', initial_dir, 'FMU Files (*.fmu)')[0]
        if f:
            self.fmu_path_edit.setText(os.path.normpath(f))
            self._save_gui_config()
        

    def get_cj_params(self):
        return {
            "Year": int(self.cj_year_e.edit.text() or '2026'), "Mon": int(self.cj_mon_e.edit.text() or '3'), "Day": int(self.cj_day_e.edit.text() or '31'),
            "Hour": int(self.cj_hour_e.edit.text() or '12'), "Min": int(self.cj_min_e.edit.text() or '19'), "Sec": float(self.cj_sec_e.edit.text() or '0.0'),
            "Table_A": self.cj_ta_e.edit.text(), "Table_B": self.cj_tb_e.edit.text(),
            "Table_FB": self.cj_tfb_e.edit.text(), "Table_Att": self.cj_tatt_e.edit.text(),
            "PointSun": 1.0 if self.chk_pointsun.isChecked() else 0.0
        }


    def start_sim(self):
        self._save_gui_config()
        fmu_path = self.fmu_path_edit.text().strip()
        if not os.path.exists(fmu_path): self.olog(f"[!] 找不到文件 {fmu_path}", "error"); return
        if not fmu_path or not os.path.exists(fmu_path):
            QMessageBox.critical(self, "错误", "请先选择有效的 FMU 模型文件")
            return
        
        # 生成唯一会话 ID，防止陈旧 UDP 指令干扰
        self.current_sim_id = str(int(time.time()))
        self.sim_pause_file = os.path.join(APP_DIR, f"sim_pause_{self.current_sim_id}.flag")
        try:
            if os.path.exists(self.sim_pause_file): os.remove(self.sim_pause_file)
        except Exception:
            pass
        
        sim_args = ["--step", str(float(self.step_e.edit.text() or '0.02')), "--rate", str(float(self.rate_e.edit.text() or '1.0')), 
                    "--freq", str(float(self.freq_e.edit.text() or '50.0')), "--time", str(float(self.time_e.edit.text() or '86400.0')),
                    "--sim_id", self.current_sim_id,
                    "--ip", self.ip_edit.edit.text().strip(), "--port", str(int(self.port_edit.edit.text() or '12345')),
                    "--params", json.dumps(self.get_cj_params()), "--control_port", str(CONTROL_PORT),
                    "--pause_file", self.sim_pause_file]
        
        # 确保传入变量过滤配置
        sync_path = os.path.join(APP_DIR, "sync_fields.json")
        if os.path.exists(sync_path):
            sim_args.extend(["--sync_vars", sync_path])
            
        if self.chk_replace_dot.isChecked():
            sim_args.append("--replace_dot")
        
        # 恢复使用基于内容的架构探测，确保兼容任何命名的 FMU
        arch_val = get_fmu_arch(fmu_path)
        fmu_bit = str(arch_val) if arch_val else ("32" if "32" in fmu_path else "64")
        fmu_path = ensure_ascii_fmu_path(fmu_path, self.olog)
        
        # 兼容源码运行与打包运行
        if getattr(sys, 'frozen', False):
            # 自动选择对应的 Worker
            if fmu_bit == "32":
                worker_p = os.path.join(APP_DIR, "FmuWorker32.exe")
            else:
                worker_p = os.path.join(APP_DIR, "FmuWorker64.exe")
                # 兼容旧版命名
                if not os.path.exists(worker_p): worker_p = os.path.join(APP_DIR, "FmuSolver.exe")
            
            cmd = [worker_p]
            if "FmuSolver.exe" in worker_p: cmd.append("--worker")
            cmd.extend([fmu_path] + sim_args)
        else:
            # 源码模式下使用对应的 Python 环境
            player_script = os.path.join(APP_DIR, "fmu_player.py")
            py_exe = sys.executable if fmu_bit == "64" else r"C:\Py32\python.exe"
            cmd = [py_exe, player_script, fmu_path] + sim_args

        self.sim_paused = False
        self.btn_start.setEnabled(False); self.btn_pause.setEnabled(True); self.btn_pause.setText("⏸ 暂停"); self.btn_stop.setEnabled(True)
        self.sim_progress.setValue(int(0)); self.sim_prog_lbl.setText("正在启动...")
        self._update_led("running")
        self.txt_log.clear()
        self.olog(f"[*] 启动仿真引擎 (ID: {self.current_sim_id}, Arch: {fmu_bit})...", "sys")
        self.log(f"[*] Worker CMD={cmd}", "sys")
        
        try:
            # --- 可视化终端同步启动 ---
            if self.chk_auto_vis.isChecked():
                self._launch_viz_manual()

            cf = 0x08000000 if os.name == 'nt' else 0 # CREATE_NO_WINDOW
            self.worker_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0, cwd=APP_DIR, env=self._child_env(), creationflags=cf)
            self.log(f"[OK] FMU Worker 已启动: pid={self.worker_process.pid} cwd={APP_DIR}", "info")
            QTimer.singleShot(2000, self.update_params) # 延迟2秒同步参数
            threading.Thread(target=self._read_worker_logs, daemon=True).start()
            
            # 启动变量注入监听
            self.log(f"[*] Worker 启动后准备重试变量注入监听 (inj_ip={self.inj_ip_edit.edit.text().strip() or '0.0.0.0'}, inj_port={self.inj_port_edit.edit.text() or '9988'})", "sys")
            self._start_injection_listener()
        except Exception as e:
            self.olog(f"[!] 启动失败: {e}", "error")
            self._reset_ui()


    def _read_worker_logs(self):
        if not self.worker_process: return
        total_t = float(self.time_e.edit.text() or '86400.0')
        last_live_log_at = 0.0
        last_perf_log_at = 0.0
        last_injection_ui_log_at = 0.0
        for line in iter(self.worker_process.stdout.readline, b''):
            if not line: continue
            line_str = self._decode_process_line(line).strip()
            self._append_runtime_log(f"[FMU_WORKER] {line_str}")
            pct_match = re.search(r'\[(\d+)%\]', line_str)
            if pct_match:
                try:
                    pct_val = int(pct_match.group(1))
                    t_str = line_str.split("Time:")[1].split("s")[0] if "Time:" in line_str else "0.0"
                    t_val = float(t_str)
                    self.sig_sim_prog.emit(pct_val, f"仿真进度: {pct_val}% (已运行 {t_val:.1f}s / 总计 {total_t:.0f}s)")
                except: pass
            is_live = "[Live]" in line_str
            now = time.time()
            if is_live:
                if now - last_live_log_at >= 2.0:
                    self.sig_log.emit(line_str, "sys")
                    last_live_log_at = now
            elif "[PERF][FMU]" in line_str:
                if now - last_perf_log_at >= 30.0:
                    self.sig_log.emit(line_str, "sys")
                    last_perf_log_at = now
            elif "Injected " in line_str or "Injection summary" in line_str or "variables mirrored" in line_str:
                if "[!]" in line_str or now - last_injection_ui_log_at >= 5.0:
                    tag = "error" if "[!]" in line_str else "info"
                    self.sig_log.emit(line_str, tag)
                    last_injection_ui_log_at = now
            else:
                tag = "info" if "[OK]" in line_str else ("error" if "[!]" in line_str else "sys")
                self.sig_log.emit(line_str, tag)
        self.worker_process.stdout.close()
        rc = self.worker_process.wait()
        tag = "sys" if rc == 0 else "error"
        self.sig_log.emit(f"[SYS] FMU Worker 退出，退出码: {rc}", tag)
        self.sig_sim_prog.emit(100, f"仿真完成: 100% (总时长 {total_t:.0f}s)" if rc == 0 else f"仿真异常结束: rc={rc}")
        self.sig_reset_ui.emit()


    def _launch_viz_manual(self):
        # 如果已经有看板在运行，则尝试置顶
        if self.visualizer_process and self.visualizer_process.poll() is None:
            try:
                import ctypes
                hwnd = ctypes.windll.user32.FindWindowW(None, "FmuSolver - Data Visualizer")
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 5) # SW_SHOW
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    return
            except: pass
            # 如果置顶失败，且进程还活着，直接返回不重复开
            return

        try:
            viz_dir = os.path.join(APP_DIR, "Visualizer")
            viz_exe = os.path.join(viz_dir, "DataVisualizer64.exe")
            if not os.path.exists(viz_exe):
                viz_exe = os.path.join(viz_dir, "DataVisualizer32.exe")
            
            python_viz = os.path.join(APP_DIR, "DataVisualizerPython.py")
            cf = 0x08000000 if os.name == 'nt' else 0 # CREATE_NO_WINDOW
            viz_env = self._child_env()
            viz_env.setdefault("FMUSOLVER_VIZ_MAX_POINTS", "12000")
            viz_env.setdefault("FMUSOLVER_VIZ_ACC_LIMIT", "8000")
            viz_env.setdefault("FMUSOLVER_VIZ_PACKET_QUEUE_MAX", "20")
            viz_env.setdefault("FMUSOLVER_VIZ_MAX_PACKETS_PER_TICK", "3")
            viz_env.setdefault("FMUSOLVER_VIZ_MEMORY_SOFT_LIMIT_MB", "900")
            viz_env.setdefault("OPENBLAS_NUM_THREADS", "1")
            viz_env.setdefault("OMP_NUM_THREADS", "1")
            
            if os.path.exists(viz_exe):
                self.log(f"[*] Launching Visualizer EXE: {viz_exe}", "sys")
                self.visualizer_process = subprocess.Popen([viz_exe, "--port", "22345"], cwd=viz_dir, env=viz_env, creationflags=cf)
            elif os.path.exists(python_viz):
                self.log(f"[*] Launching Visualizer Script: {python_viz}", "sys")
                cf = 0x08000000 if os.name == 'nt' else 0
                self.visualizer_process = subprocess.Popen([sys.executable, python_viz, "--port", "22345"], cwd=APP_DIR, env=viz_env, creationflags=cf)
            else:
                self.log(f"[!] Visualizer NOT FOUND (EXE or Script)", "error")
        except Exception as e:
            self.log(f"[!] Manual viz launch failed: {str(e)}", "error")


    def _reset_ui(self):
        self.btn_start.setEnabled(True); self.btn_pause.setEnabled(False); self.btn_pause.setText("⏸ 暂停"); self.btn_stop.setEnabled(False); self.worker_process = None
        self.sim_paused = False
        self.current_sim_id = None
        self._update_led("ready")
        self.sim_progress.setValue(int(0)); self.sim_prog_lbl.setText("仿真停止")
        self.orbit_progress.setValue(int(0)); self.orbit_prog_lbl.setText("计算停止")
        # 停止注入监听
        if hasattr(self, 'inj_stop_events') and self.inj_stop_events:
            for ev in self.inj_stop_events:
                try: ev.set()
                except: pass
        self._injection_listener_signature = None


    def stop_sim(self):
        if self.worker_process:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # 必须带上 sim_id，Worker 才会响应退出指令
                msg = {"sim_id": getattr(self, 'current_sim_id', ""), "exit": True}
                sock.sendto(json.dumps(msg).encode('utf-8'), ("127.0.0.1", CONTROL_PORT))
            except: pass
            finally: sock.close()
            
            # 延迟杀掉进程以允许优雅退出
            QTimer.singleShot(500, self._terminate_worker)
        
        if hasattr(self, 'visualizer_process') and self.visualizer_process:
            try:
                self.visualizer_process.terminate()
            except: pass
            self.visualizer_process = None
        
        self.btn_pause.setEnabled(False)
        self.btn_pause.setText("⏸ 暂停")
        self.sim_paused = False
        try:
            if hasattr(self, 'sim_pause_file') and os.path.exists(self.sim_pause_file):
                os.remove(self.sim_pause_file)
        except Exception:
            pass
        self._update_led("stopped")
        # UI 重置由 _terminate_worker 触发或在此处提前部分重置
        self.sim_prog_lbl.setText("正在停止仿真...")


    def toggle_sim_pause(self):
        if not self.worker_process:
            return
        self.sim_paused = not getattr(self, 'sim_paused', False)
        cmd = {"sim_id": getattr(self, 'current_sim_id', ""), "pause": self.sim_paused}
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            pause_file = getattr(self, 'sim_pause_file', os.path.join(APP_DIR, "sim_pause.flag"))
            if self.sim_paused:
                with open(pause_file, 'w', encoding='utf-8') as f:
                    f.write('pause')
            elif os.path.exists(pause_file):
                os.remove(pause_file)
            s.sendto(json.dumps(cmd).encode('utf-8'), ("127.0.0.1", CONTROL_PORT))
            self.btn_pause.setText("▶ 继续" if self.sim_paused else "⏸ 暂停")
            self.sim_prog_lbl.setText("仿真已暂停" if self.sim_paused else "仿真继续运行")
            self.log("[*] 仿真暂停" if self.sim_paused else "[*] 仿真继续", "sys")
        except Exception as e:
            self.log(f"[!] 暂停/继续指令发送失败: {e}", "error")
        finally:
            s.close()


    def _terminate_worker(self):
        if self.worker_process:
            try:
                import subprocess
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.worker_process.pid)], creationflags=0x08000000)
            except: pass


    def update_params(self):
        if not self.worker_process: return
        sample_freq = float(self.freq_e.edit.text() or '50.0')
        cmd = {
            "sim_id": getattr(self, 'current_sim_id', ""),
            "step_size": float(self.step_e.edit.text() or '0.02'), 
            "sim_time": float(self.time_e.edit.text() or '86400.0'), 
            "sim_rate": float(self.rate_e.edit.text() or '1.0'), 
            "sample_freq": sample_freq,
            "yc_inject_freq": min(5.0, sample_freq)
        }
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try: s.sendto(json.dumps(cmd).encode('utf-8'), ("127.0.0.1", CONTROL_PORT))
        except: pass
        finally: s.close()


    def toggle_is_initial(self):
        """Pulse Is_initial during runtime; PointSun is only a pre-simulation option."""
        def do_pulse():
            # 1. 变高并保持一会儿
            self.btn_initial.setText("⚡ 同步中..."); self.btn_initial.setEnabled(False)
            
            # 日志输出同步操作涉及的变量
            self.log("===========================================", "sys")
            self.log("[SYNC] 点击同步按钮，对 Is_initial 变量进行脉冲触发 (1 -> 0)...", "info")
            
            # 发送脉冲开始
            if self.worker_process:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    msg = {"sim_id": getattr(self, 'current_sim_id', ""), "Is_initial": 1.0}
                    s.sendto(json.dumps(msg).encode('utf-8'), ("127.0.0.1", CONTROL_PORT))
                    self.log("  -> Is_initial: 1.0 (已发送)", "info")
                except: pass
                finally: s.close()
            
            # 2. 0.5秒后恢复为低电平
            QTimer.singleShot(500, lambda: [
                self.send_ctrl_signal("Is_initial", 0.0),
                self.log("  -> Is_initial: 0.0 (已恢复)", "info"),
                self.btn_initial.setText("⚡ 同步 (0)"),
                self.btn_initial.setEnabled(True)
            ])
        do_pulse()


    def send_ctrl_signal(self, name, val):
        if self.worker_process:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                msg = {"sim_id": getattr(self, 'current_sim_id', ""), name: val}
                s.sendto(json.dumps(msg).encode('utf-8'), ("127.0.0.1", CONTROL_PORT))
            except: pass
            finally: s.close()

    def _start_injection_listener(self):
        """启动后台 UDP 监听，接收外部变量注入"""
        ip = self.inj_ip_edit.edit.text().strip() or "0.0.0.0"
        try:
            port = int(self.inj_port_edit.edit.text() or "9988")
        except: port = 9988

        self.log(f"[*] _start_injection_listener 入口: ip={ip}, port={port}", "sys")

        signature = (ip, port)
        listener_threads = getattr(self, 'inj_listener_threads', [])
        if (getattr(self, '_injection_listener_signature', None) == signature
                and any(thread.is_alive() for thread in listener_threads)):
            self.log(f"[*] 注入监听已存在且签名一致，跳过重复启动: {ip}:{port}", "sys")
            return

        if hasattr(self, 'inj_stop_events') and self.inj_stop_events:
            for ev in self.inj_stop_events:
                try: ev.set()
                except: pass
        self.inj_stop_events = []

        for thread in listener_threads:
            if thread.is_alive():
                self.log(f"[*] 等待旧注入监听线程退出: {thread.name}", "sys")
                thread.join(timeout=1.2)
        self.inj_listener_threads = []
        self._injection_listener_signature = signature
        
        # Only listen to the explicit PE/manual injection port. Telemetry is bridged
        # by YaoCe_LinkLayer directly to the FMU Worker to keep the UI out of the hot path.
        ports_to_listen = {port}

        def safe_log(msg, tag):
            try:
                self.sig_log.emit(str(msg), tag)
            except:
                pass
                
        def create_listener(listen_port):
            stop_event = threading.Event()
            self.inj_stop_events.append(stop_event)
            
            def loop():
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                except Exception:
                    pass
                sock.settimeout(1.0)
                fwd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                last_log_time = 0
                last_perf_time = time.time()
                recv_count = 0
                fwd_count = 0
                parse_error_count = 0
                last_packet_bytes = 0
                pending_var_cmd = {}
                last_var_forward_time = 0.0
                try:
                    var_forward_freq = max(0.1, float(self.freq_e.edit.text() or "50.0"))
                except Exception:
                    var_forward_freq = 50.0
                var_forward_interval = 1.0 / var_forward_freq

                def forward_to_worker(payload):
                    nonlocal fwd_count
                    if self.worker_process and self.worker_process.poll() is None and payload:
                        msg = {"sim_id": getattr(self, 'current_sim_id', "")}
                        msg.update(payload)
                        fwd_sock.sendto(json.dumps(msg).encode('utf-8'), ("127.0.0.1", CONTROL_PORT))
                        fwd_count += 1
                
                try:
                    safe_log(f"[*] 尝试绑定变量注入监听: {ip}:{listen_port}", "info")
                    sock.bind((ip, listen_port))
                    safe_log(f"[*] 变量注入监听已启动：{ip}:{listen_port}", "info")
                except Exception as e:
                    safe_log(f"[!] 注入监听启动失败 (端口 {listen_port}): {e}", "error")
                    sock.close()
                    fwd_sock.close()
                    return
                
                while not stop_event.is_set():
                    try:
                        data, addr = sock.recvfrom(65535)
                        recv_count += 1
                        last_packet_bytes = len(data)
                        try:
                            raw_data = data.decode('utf-8', errors='ignore').strip()
                            now = time.time()
                            do_log = (now - last_log_time > 1.0)
                            
                            cmd = None
                            cmd_from_protobuf = False
                            try:
                                decoded = base64.b64decode(raw_data)
                                if ddm_pb2 is not None:
                                    pb_data = ddm_pb2.DDMData()
                                    pb_data.ParseFromString(decoded)
                                    cmd = {}
                                    cmd_from_protobuf = True
                                    type_names = getattr(ddm_pb2.DDMData.SimVar, 'Type', None)
                                    for v in pb_data.sim_vars:
                                        if type_names is not None:
                                            if v.type == ddm_pb2.DDMData.SimVar.Type.Value("Bool"):
                                                cmd[v.name] = bool(v.bool_value)
                                            elif v.type == ddm_pb2.DDMData.SimVar.Type.Value("Int"):
                                                cmd[v.name] = int(v.int_value)
                                            elif v.type == ddm_pb2.DDMData.SimVar.Type.Value("String"):
                                                cmd[v.name] = v.string_value
                                            else:
                                                cmd[v.name] = float(v.double_value)
                                        else:
                                            cmd[v.name] = float(v.double_value)
                                    if cmd and do_log:
                                        safe_log(f"[*] [Port {listen_port}] RECV Protobuf: {len(cmd)} vars (Throttled)", "info")
                                        last_log_time = now
                            except:
                                pass
                                
                            if not cmd:
                                try:
                                    cmd = json.loads(raw_data)
                                    if not isinstance(cmd, dict): cmd = None
                                    if cmd and do_log:
                                        safe_log(f"[*] [Port {listen_port}] RECV JSON: {len(cmd)} vars (Throttled)", "info")
                                        last_log_time = now
                                except:
                                    pass
                            
                            if not cmd:
                                parse_error_count += 1
                                if do_log:
                                    safe_log(f"[!] [Port {listen_port}] 数据格式不正确 (非 Base64/Protobuf 且非 JSON)", "error")
                                    last_log_time = now
                                continue
                            
                            if not cmd_from_protobuf:
                                control_keys = {
                                    "sim_id", "exit", "pause", "resume", "sim_rate",
                                    "step_size", "sim_time", "sample_freq", "yc_inject_freq",
                                    "__apply_yc_now",
                                }
                                normalized_cmd = {}
                                for key, value in cmd.items():
                                    key_text = str(key)
                                    if key_text in control_keys or key_text.startswith(("PE.", "YC.")):
                                        normalized_cmd[key_text] = value
                                    else:
                                        normalized_cmd[f"PE.{key_text}"] = value
                                cmd = normalized_cmd

                            if cmd_from_protobuf:
                                source_prefix = "PE." if listen_port == port else "YC."
                                normalized_cmd = {}
                                for k, v in cmd.items():
                                    key = str(k)
                                    normalized_cmd[key if key.startswith(("PE.", "YC.")) else source_prefix + key] = v
                                cmd = normalized_cmd

                            continuous_vars = {str(k): v for k, v in cmd.items() if str(k).startswith(("PE.", "YC."))}
                            control_vars = {str(k): v for k, v in cmd.items() if not str(k).startswith(("PE.", "YC."))}
                            if control_vars:
                                forward_to_worker(control_vars)
                            if continuous_vars:
                                pending_var_cmd.update(continuous_vars)
                            if pending_var_cmd and now - last_var_forward_time >= var_forward_interval:
                                forward_to_worker(pending_var_cmd)
                                pending_var_cmd.clear()
                                last_var_forward_time = now
                            if now - last_perf_time >= 5.0:
                                worker_alive = bool(self.worker_process and self.worker_process.poll() is None)
                                safe_log(f"[PERF][INJ:{listen_port}] recv={recv_count} fwd={fwd_count} pending={len(pending_var_cmd)} worker_alive={worker_alive} parse_err={parse_error_count} last_bytes={last_packet_bytes}", "info")
                                last_perf_time = now
                        except Exception as e:
                            parse_error_count += 1
                            if time.time() - last_log_time > 1.0:
                                safe_log(f"[!] [Port {listen_port}] 注入处理异常: {e}", "error")
                                last_log_time = time.time()
                    except socket.timeout:
                        continue
                    except Exception as e:
                        break
                sock.close()
                fwd_sock.close()
                safe_log(f"[*] [Port {listen_port}] 注入监听线程退出", "sys")
                safe_log(f"[*] [Port {listen_port}] 变量注入监听已停止", "sys")
            
            thread = threading.Thread(target=loop, daemon=True, name=f"pe-injection-{listen_port}")
            self.inj_listener_threads.append(thread)
            self.log(f"[*] 创建注入监听线程: {thread.name} -> {ip}:{listen_port}", "sys")
            thread.start()
            self.log(f"[*] 注入监听线程已启动: {thread.name}", "sys")

        for p in ports_to_listen:
            create_listener(p)

    def run_orbit_precalc(self):
        self._save_gui_config()
        fmu_path = self.orbit_fmu_edit.text().strip()
        fmu_bit = str(get_fmu_arch(fmu_path) or "32")
        if getattr(sys, 'frozen', False):
            exe_name = "OrbitPreCalc32.exe" if fmu_bit == "32" else "OrbitPreCalc64.exe"
            worker_path = os.path.join(APP_DIR, exe_name)
        else:
            worker_path = sys.executable if fmu_bit == "64" else r"C:\Py32\python.exe"
            
        if not os.path.exists(fmu_path):
            self.olog(f"[!] 找不到FMU文件: {fmu_path}", "error"); return

        fmu_path = ensure_ascii_fmu_path(fmu_path, self.olog)

        params = {"Year": int(self.year_e.edit.text() or '2026'), "Mon": int(self.mon_e.edit.text() or '1'), "Day": int(self.day_e.edit.text() or '1'), "Hour": int(self.hour_e.edit.text() or '0'), "Min": int(self.min_e.edit.text() or '0'), "Sec": float(self.sec_e.edit.text() or '0.0'),
            "a_MT": float(self.a_e.edit.text() or '6766.71777'), "e_MT": float(self.ecc_e.edit.text() or '0.0011'), "i_MT": float(self.inc_e.edit.text() or '41.627'), "OMEGA_MT": float(self.om_e.edit.text() or '137.492'), "omega_MT": float(self.w_e.edit.text() or '77.010'), "f_MT": float(self.f_e.edit.text() or '57.552')}
        
        if getattr(sys, 'frozen', False):
            cmd = [worker_path, fmu_path]
        else:
            runner_script = os.path.join(APP_DIR, "orbit_pre_runner.py")
            cmd = [worker_path, runner_script, fmu_path]

        self.orbit_pause_file = os.path.join(APP_DIR, "orbit_pause.flag")
        try:
            if os.path.exists(self.orbit_pause_file): os.remove(self.orbit_pause_file)
        except: pass
            
        cmd.extend(["--params",      json.dumps(params),
                    "--stop_time",   str(float(self.o_dur_e.edit.text() or '86400.0')),
                    "--step_size",   str(float(self.o_step_e.edit.text() or '10.0')),
                    "--sample_freq", str(float(self.o_freq_e.edit.text() or '0.1')),
                    "--sim_rate",    str(float(self.o_rate_e.edit.text() or '0.0')),
                    "--pause_file",  self.orbit_pause_file])

        self.olog(f"[*] 启动轨道计算引擎...", "sys")
        self.olog("[*] 时间输入按北京时间解释；界面六根数角度项按度显示，并按界面数值原样传入 FMU。", "sys")
        self.olog(f"[*] 步长={float(self.o_step_e.edit.text() or '10.0')}s | 频率={float(self.o_freq_e.edit.text() or '0.1')}Hz | 时长={float(self.o_dur_e.edit.text() or '86400.0')}s | 速率={float(self.o_rate_e.edit.text() or '0.0')}x", "sys")
        self.orbit_paused = False
        self.btn_run_orbit.setText("运行中..."); self.btn_run_orbit.setEnabled(False)
        self.btn_pause_orbit.setText("⏸ 暂停"); self.btn_pause_orbit.setEnabled(True)
        self.btn_stop_orbit.setEnabled(True)
        self.orbit_progress.setValue(int(0))
        self.orbit_prog_lbl.setText("正在启动...")
        self.orbit_proc = None

        def run_thread():
            total_t = float(self.o_dur_e.edit.text() or '86400.0')
            try:
                cf = 0x08000000 if os.name == 'nt' else 0
                self.orbit_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0, cwd=APP_DIR, env=self._child_env(), creationflags=cf)
                ready_file = None
                last_ui_update = 0
                last_log_update = 0
                last_native_log_update = 0
                suppressed_native_lines = 0
                for line in iter(self.orbit_proc.stdout.readline, b''):
                    line_str = self._decode_process_line(line).strip()
                    if not line_str: continue
                    
                    # 进度条解析: [Live] [45%] Time: 123.4s | ... (频率限制)
                    now = time.time()
                    if "[Live]" in line_str and (now - last_ui_update > 0.2):
                        pct_match = re.search(r'\[(\d+)%\]', line_str)
                        if pct_match:
                            try:
                                pct_val = int(pct_match.group(1))
                                t_str = line_str.split("Time:")[1].split("s")[0] if "Time:" in line_str else "0.0"
                                t_val = float(t_str)
                                self.sig_orbit_prog.emit(pct_val, f"计算进度: {pct_val}% (已解析 {t_val:.0f}s / 总计 {total_t:.0f}s)")
                                last_ui_update = now
                            except: pass

                    if "[EXPORT_READY]" in line_str:
                        ready_file = line_str.replace("[EXPORT_READY]", "").strip()
                    
                    # 只有关键信息才实时显示，普通 Live 信息 1s 更新一次
                    is_live = "[Live]" in line_str
                    is_structured = self._is_structured_runner_log(line_str)
                    if not is_structured:
                        suppressed_native_lines += 1
                        if now - last_native_log_update > 3.0:
                            self.sig_olog.emit(f"[*] FMU 原生日志正在输出，已折叠 {suppressed_native_lines} 行以保持计算速度。", "sys")
                            suppressed_native_lines = 0
                            last_native_log_update = now
                        continue

                    if suppressed_native_lines and (not is_live or now - last_native_log_update > 3.0):
                        self.sig_olog.emit(f"[*] FMU 原生日志已折叠 {suppressed_native_lines} 行。", "sys")
                        suppressed_native_lines = 0
                        last_native_log_update = now

                    if not is_live or (now - last_log_update > 1.0):
                        tag = "info" if "[OK]" in line_str or "SUCCESS" in line_str else ("error" if "[!]" in line_str or "Error" in line_str or "Fatal" in line_str else "sys")
                        self.sig_olog.emit(line_str, tag)
                        if is_live: last_log_update = now
                self.orbit_proc.stdout.close()
                rc = self.orbit_proc.wait()
                self.sig_orbit_prog.emit(100, f"计算完成: 100% (总时长 {total_t:.0f}s)")

                if ready_file and os.path.exists(ready_file):
                    with open(ready_file, 'r') as f:
                        self.orbit_data = json.load(f)
                    n = len(self.orbit_data)
                    self.sig_export_ready.emit()
                    self.sig_olog.emit(f"[OK] 计算完成，共 {n} 行数据。", "info")
                    try:
                        txt_dir = os.path.join(APP_DIR, "txt")
                        os.makedirs(txt_dir, exist_ok=True)
                        auto_save_p = os.path.join(txt_dir, "Orbit_Pre.txt")
                        # Disabled: this creates a lossy 7-column duplicate of the FMU's 22-column file.
                        # self._save_to_orbit_txt(auto_save_p)
                        self.sig_olog.emit("[*] 已禁用 7 列 Orbit_Pre.txt 自动保存，使用程序根目录的 FMU 原生结果。", "sys")
                    except Exception as e:
                        self.sig_olog.emit(f"[!] 自动保存失败: {e}", "error")
                else:
                    self.sig_olog.emit(f"[!] 计算结束但未找到结果文件 (rc={rc})。", "error")
            except Exception as e:
                self.sig_olog.emit(f"[!] 线程异常: {e}", "error")
            finally:
                self.orbit_proc = None
                self.sig_orbit_done.emit()

        threading.Thread(target=run_thread, daemon=True).start()


    def stop_orbit(self):
        if hasattr(self, 'orbit_proc') and self.orbit_proc:
            try:
                if hasattr(self, 'orbit_pause_file') and os.path.exists(self.orbit_pause_file):
                    try: os.remove(self.orbit_pause_file)
                    except: pass
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.orbit_proc.pid)],
                                creationflags=subprocess.CREATE_NO_WINDOW)
                self.olog("[!] 用户手动停止计算进程。", "error")
            except: pass


    def toggle_orbit_pause(self):
        if not getattr(self, 'orbit_proc', None):
            return
        self.orbit_paused = not getattr(self, 'orbit_paused', False)
        pause_file = getattr(self, 'orbit_pause_file', os.path.join(APP_DIR, "orbit_pause.flag"))
        try:
            if self.orbit_paused:
                with open(pause_file, 'w', encoding='utf-8') as f:
                    f.write('pause')
                self.btn_pause_orbit.setText("▶ 继续")
                self.orbit_prog_lbl.setText("轨道预示已暂停")
                self.olog("[*] 轨道预示暂停", "sys")
            else:
                if os.path.exists(pause_file): os.remove(pause_file)
                self.btn_pause_orbit.setText("⏸ 暂停")
                self.orbit_prog_lbl.setText("轨道预示继续运行")
                self.olog("[*] 轨道预示继续", "sys")
        except Exception as e:
            self.olog(f"[!] 轨道暂停/继续失败: {e}", "error")


    def _save_to_orbit_txt(self, filepath):
        if not self.orbit_data: return
        with open(filepath, 'w') as out:
            # 兼容 FMU 内部 C++ Table 格式
            out.write("#1\ndouble table({},7)\n".format(len(self.orbit_data)))
            for row in self.orbit_data:
                # row[0] 是时间，row[1:] 是 6 根初值
                out.write("\t".join([f"{x:.5f}" for x in row[1:]]) + "\n")


    def export_orbit_txt(self):
        f = QFileDialog.getSaveFileName(self, 'Save', 'Orbit_Pre.txt', 'Text Files (*.txt)')[0]
        if not f: return
        try:
            self._save_to_orbit_txt(f)
            self.log(f"[OK] 导出成功: {f}", "info")
        except Exception as e:
            self.log(f"[!] 导出失败: {e}", "error")

if __name__ == "__main__":
    try:
        with open(os.path.join(APP_DIR, "sys_argv.log"), "w", encoding="utf-8") as f:
            f.write(f"sys.argv={sys.argv}\n")
    except: pass

    if len(sys.argv) > 1 and sys.argv[1] == "--pickcolor":
        initial = sys.argv[2] if len(sys.argv) > 2 else "#f0f2f6"
        title = sys.argv[3] if len(sys.argv) > 3 else "选择颜色"
        app = QApplication(sys.argv[:1])
        app.setStyleSheet("")
        color = QColorDialog.getColor(QColor(initial), None, title)
        if color.isValid():
            print(color.name())
            sys.exit(0)
        sys.exit(1)

    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--worker", action="store_true")
        parser.add_argument("fmu_path")
        parser.add_argument("--ip", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=8889)
        parser.add_argument("--sync_vars", default=None)
        parser.add_argument("--control_port", type=int, default=8898)
        parser.add_argument("--step", type=float, default=0.01)
        parser.add_argument("--rate", type=float, default=1.0)
        parser.add_argument("--freq", type=float, default=0.0)
        parser.add_argument("--time", type=float, default=float("inf"))
        parser.add_argument("--params", default=None)
        parser.add_argument("--sim_id", default=None)
        args = parser.parse_args()
        os.chdir(APP_DIR)
        init_params_dict = None
        if args.params:
            try: init_params_dict = json.loads(args.params)
            except: pass
        try:
            # Keep this dynamic so the GUI executable does not bundle heavy worker-only
            # dependencies (fmpy/numpy). Normal packaged runs use FmuWorker64/32.exe.
            import importlib
            FMUPlayer = importlib.import_module("fmu_player").FMUPlayer
            player = FMUPlayer(args.fmu_path, args.ip, args.port, sim_id=args.sim_id,
                               sync_vars_file=args.sync_vars, control_port=args.control_port)
            ok = player.run(step_size=args.step, sim_time=args.time, sim_rate=args.rate,
                            sample_freq=args.freq, init_params=init_params_dict)
        except Exception as e:
            with open(os.path.join(APP_DIR, "worker_fatal.log"), "w", encoding="utf-8") as f:
                f.write(f"Worker Fatal Error ({datetime.now()}): {e}\n")
            ok = False
        sys.exit(0 if ok else 2)

    elif len(sys.argv) > 1 and sys.argv[1] == "--yaoceworker":
        log_file  = os.path.join(APP_DIR, "yaoce_run.log")
        try:
            with open(log_file, "w", encoding="utf-8") as f: f.write("")
        except: pass
        import builtins
        class FileOut:
            def __init__(self, prefix=""): self.p = prefix
            def write(self, text):
                if not text: return
                try:
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write((self.p + text) if (text.strip() and self.p) else text)
                except: pass
            def flush(self): pass
        
        my_out = FileOut()
        sys.stdout = my_out
        sys.stderr = FileOut("[!ERR] ")
        def _my_print(*args, **kwargs):
            try: my_out.write(" ".join(map(str, args)) + "\n")
            except: pass
        builtins.print = _my_print
        
        yaoce_cfg_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(APP_DIR, "yaocetest")
        if APP_DIR not in sys.path: sys.path.append(APP_DIR)
        
        try:
            try:
                from yaocetest.main import YaoCeLinkLayerApp
            except ImportError:
                if yaoce_cfg_dir not in sys.path: sys.path.append(yaoce_cfg_dir)
                from main import YaoCeLinkLayerApp
                
            print(f"[SYS] YaoCe Worker Started. Config Dir: {yaoce_cfg_dir}")
            app_inst = YaoCeLinkLayerApp(yaoce_cfg_dir)
            print(f"[SYS] App instantiated.")
            app_inst.start()
        except Exception as e:
            print(f"[!] YaoCe Worker Fatal Error: {e}")
            import traceback
            print(traceback.format_exc())
        sys.exit(0)

    else:
        # 强制单实例运行 (FmuSolver)
        mutex_name = "Local\\FmuSolver_Global_Mutex"
        import ctypes
        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, False, mutex_name)
        if kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
            hwnd = ctypes.windll.user32.FindWindowW(None, "FmuSolver")
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 5) # SW_SHOW
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            sys.exit(0)

        app = QApplication(sys.argv)
        window = FmuSolverGUI()
        window.setWindowTitle("FmuSolver") # 必须设置，以便单实例检测查找
        window.show()
        sys.exit(app.exec())
