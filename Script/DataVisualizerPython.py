import sys
import socket
import threading
import base64
import json
import os
import argparse
import time
import queue
import gc
import numpy as np
import ctypes
from ctypes import wintypes
import ddm_pb2
import datetime
import traceback

def is_process_alive(pid):
    try:
        pid = int(pid)
    except Exception:
        return True
    if pid <= 0 or pid == os.getpid():
        return True
    if sys.platform == 'win32':
        try:
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

# 强制 Windows 任务栏显示独立图标
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("FmuSolver.DataVisualizer.V1")
except: pass

try:
    from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                                 QWidget, QHeaderView, QTableWidget, QTableWidgetItem, 
                                 QLabel, QFrame, QSplitter, QPushButton, QCheckBox, QInputDialog, QMenu, QColorDialog,
                                 QSpinBox, QComboBox, QGridLayout, QSizeGrip, QListView, QListWidget, QDockWidget, QFileDialog, QMessageBox)
    from PySide6.QtCore import Qt, QTimer, Signal, QFileSystemWatcher, QPoint, QEvent, QObject, QRect, QSize, QByteArray
    from PySide6.QtGui import QColor, QFont, QPalette, QCursor, QIcon, QPainter, QPainterPath, QPen
    QT_VERSION = 6
except ImportError:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                               QWidget, QHeaderView, QTableWidget, QTableWidgetItem, 
                               QLabel, QFrame, QSplitter, QPushButton, QCheckBox, QInputDialog, QMenu, QColorDialog,
                               QSpinBox, QComboBox, QGridLayout, QListView, QDockWidget, QFileDialog, QMessageBox)
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal as Signal, QFileSystemWatcher, QPoint, QEvent, QObject, QRect, QSize, QByteArray
    from PyQt5.QtGui import QColor, QFont, QPalette, QCursor, QIcon, QPainter, QPainterPath, QPen
    QT_VERSION = 5
import pyqtgraph as pg
pg.setConfigOptions(antialias=True)

# ─── Windows Acrylic Blur API ───
class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p), ("SizeOfData", ctypes.c_size_t)]
class ACCENT_POLICY(ctypes.Structure):
    _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int), ("GradientColor", ctypes.c_int), ("AnimationId", ctypes.c_int)]

def set_blur_behind(hwnd):
    accent = ACCENT_POLICY()
    accent.AccentState = 3 
    accent.GradientColor = 0x00FFFFFF
    data = WINDOWCOMPOSITIONATTRIBDATA()
    data.Attribute = 19 
    data.SizeOfData = ctypes.sizeof(accent)
    data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
    try: ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.pointer(data))
    except: pass

def lbl(text, obj=None):
    l = QLabel(text)
    if obj: l.setObjectName(obj)
    return l

class PlotDockWidget(QDockWidget):
    closed = Signal(str)

    def __init__(self, title, key, parent=None):
        super().__init__(title, parent)
        self.dock_key = key

    def closeEvent(self, event):
        self.closed.emit(self.dock_key)
        super().closeEvent(event)

class DockTitleBar(QWidget):
    def __init__(self, title, dock, parent=None):
        super().__init__(parent)
        self.dock = dock
        self.setObjectName("DockTitleBar")
        self.current_point_size = 12
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 6, 8, 4)
        self.layout.setSpacing(8)

        self.left_spacer = QWidget()
        self.left_spacer.setFixedSize(24, 24)
        self.layout.addWidget(self.left_spacer, 0, Qt.AlignVCenter)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("DockTitleLabel")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(False)
        self.layout.addWidget(self.title_label, 1)

        self.btn_close = QPushButton("×")
        self.btn_close.setObjectName("DockCloseButton")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("关闭绘图窗口")
        self.btn_close.clicked.connect(self.dock.close)
        self.layout.addWidget(self.btn_close, 0, Qt.AlignRight | Qt.AlignVCenter)

        self.setTitleSize(self.current_point_size)

    def setTitle(self, title):
        self.title_label.setText(title)

    def setTitleSize(self, point_size):
        self.current_point_size = point_size
        font = self.title_label.font()
        font.setPointSize(point_size)
        font.setBold(True)
        self.title_label.setFont(font)
        metrics = self.title_label.fontMetrics()
        title_height = metrics.height()
        bar_height = max(38, title_height + 18)
        button_size = max(24, min(32, point_size + 8))
        self.setFixedHeight(bar_height)
        top_margin = max(6, int((bar_height - title_height) / 2) - 2)
        bottom_margin = max(4, bar_height - title_height - top_margin)
        self.layout.setContentsMargins(10, top_margin, 8, bottom_margin)
        self.left_spacer.setFixedSize(button_size, button_size)
        self.btn_close.setFixedSize(button_size, button_size)

class PlotPanel(QFrame):
    def __init__(self, title, closable=False, on_close=None, parent=None):
        super().__init__(parent)
        self.setObjectName("PlotPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.title_bar_widget = DockTitleBar(title, self)
        if not closable:
            self.title_bar_widget.btn_close.hide()
            self.title_bar_widget.left_spacer.hide()
        elif on_close is not None:
            self.title_bar_widget.btn_close.clicked.disconnect()
            self.title_bar_widget.btn_close.clicked.connect(on_close)
        layout.addWidget(self.title_bar_widget)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        layout.addWidget(self.content, 1)

    def set_title_bar_visible(self, visible):
        self.title_bar_widget.setVisible(visible)
        self.title_bar_widget.btn_close.setVisible(visible)
        self.title_bar_widget.left_spacer.setVisible(visible)

    def set_plot_widget(self, plot_widget):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            old_widget = item.widget()
            if old_widget is not None:
                old_widget.setParent(None)
                old_widget.deleteLater()
        self.content_layout.addWidget(plot_widget)
        self.set_title_bar_visible(True)
        self.show()

    def clear_plot_widget(self):
        placeholder = QWidget()
        self.set_plot_widget(placeholder)
        self.set_title_bar_visible(False)
        self.hide()

class TitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self._drag_pos = None
        self.setObjectName("TitleBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(36)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(5)
        self.btn_sidebar = QPushButton("≡")
        self.btn_sidebar.setObjectName("SidebarBtn")
        self.btn_sidebar.setToolTip("显示/隐藏配置面板")
        self.btn_sidebar.setFixedSize(30, 30)
        self.btn_sidebar.clicked.connect(self.parent.toggle_sidebar)
        lay.addWidget(self.btn_sidebar)
        
        self.brand_lbl = QLabel("FmuSolver - Data Visualizer")
        self.brand_lbl.setObjectName("BrandLabel")
        lay.addWidget(self.brand_lbl)
        lay.addStretch()
        lay.addSpacing(10)
        
        # All controls on the RIGHT (Order from left to right: min → max → close)
        self.btn_min = QPushButton()
        self.btn_min.setObjectName("ControlBtn")
        self.btn_min.setFixedSize(14, 14); self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.setToolTip("最小化")
        self.btn_min.setStyleSheet("QPushButton { background: #FFBD2E; border-radius: 7px; border: 1px solid rgba(0,0,0,0.1); min-width: 14px; max-width: 14px; min-height: 14px; max-height: 14px; } QPushButton:hover { background: #E0A628; }")
        self.btn_min.clicked.connect(self.parent.showMinimized)
        
        self.btn_max = QPushButton()
        self.btn_max.setObjectName("ControlBtn")
        self.btn_max.setFixedSize(14, 14); self.btn_max.setCursor(Qt.PointingHandCursor)
        self.btn_max.setToolTip("最大化/还原")
        self.btn_max.setStyleSheet("QPushButton { background: #28C840; border-radius: 7px; border: 1px solid rgba(0,0,0,0.1); min-width: 14px; max-width: 14px; min-height: 14px; max-height: 14px; } QPushButton:hover { background: #24B338; }")
        self.btn_max.clicked.connect(self.parent.toggle_maximize)
        
        self.btn_close = QPushButton()
        self.btn_close.setObjectName("ControlBtn")
        self.btn_close.setFixedSize(14, 14); self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("关闭")
        self.btn_close.setStyleSheet("QPushButton { background: #FF5F56; border-radius: 7px; border: 1px solid rgba(0,0,0,0.1); min-width: 14px; max-width: 14px; min-height: 14px; max-height: 14px; } QPushButton:hover { background: #FF3B30; }")
        self.btn_close.clicked.connect(self.parent.close)
        
        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_max)
        lay.addWidget(self.btn_close)

    def mousePressEvent(self, event):
        # Keep for safety or non-windows dragging
        if event.button() == Qt.LeftButton: self._drag_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event): self._drag_pos = None

class TimeAxisItem(pg.AxisItem):
    def __init__(self, visualizer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.visualizer = visualizer

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            if self.visualizer.base_datetime is not None:
                dt = self.visualizer.base_datetime + datetime.timedelta(seconds=(v - self.visualizer.base_sim_time))
                strings.append(f"{dt.year}-{dt.month:02d}-{dt.day:02d}\n{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}")
            else:
                strings.append(f"{v:.1f}s")
        return strings

class PlotViewBox(pg.ViewBox):
    def __init__(self, visualizer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.visualizer = visualizer

    def mouseDragEvent(self, ev, axis=None):
        if ev.button() == Qt.MiddleButton:
            if ev.isStart():
                self.visualizer.chk_autoscroll.setChecked(False)
                self.setCursor(QCursor(Qt.ClosedHandCursor))
            elif ev.isFinish():
                self.unsetCursor()
            ev.accept()
            delta = ev.pos() - ev.lastPos()
            tr = self.childGroup.transform()
            x_scale = tr.m11() if tr.m11() != 0 else 1.0
            y_scale = tr.m22() if tr.m22() != 0 else 1.0
            self.translateBy(x=-delta.x() / x_scale, y=delta.y() / y_scale)
            return
        super().mouseDragEvent(ev, axis=axis)

APP_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))

class ProfessionalVisualizer(QMainWindow):
    data_received = Signal(object)

    def make_curve_pen(self, style):
        pen = QPen(QColor(style["color"]))
        pen.setWidthF(float(style["width"]))
        pen.setCosmetic(True)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        return pen

    def __init__(self, port=12345):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("FmuSolver - Data Visualizer")
        self.setWindowIcon(QIcon(os.path.join(APP_DIR, "fmusolver.ico")))
        self.resize(1280, 800)
        self.setMinimumSize(980, 640)
        
        self.port = port
        self.vars_config = []
        self.max_points = int(os.environ.get("FMUSOLVER_VIZ_MAX_POINTS", "12000"))
        self.current_idx = 0
        self.times = np.zeros(self.max_points)
        self.data_store = {} 
        self.accumulate_enabled = False
        self.accumulate_max_render_points = int(os.environ.get("FMUSOLVER_VIZ_ACC_RENDER_POINTS", "1000"))
        self.accumulate_update_stride = 10
        self.accumulate_bucket_seconds = float(os.environ.get("FMUSOLVER_VIZ_ACC_BUCKET_SEC", "1.0"))
        self.accumulate_hard_limit = int(os.environ.get("FMUSOLVER_VIZ_ACC_LIMIT", "8000"))
        self.realtime_max_render_points = int(os.environ.get("FMUSOLVER_VIZ_REALTIME_RENDER_POINTS", "1000"))
        self.max_runtime_variables = int(os.environ.get("FMUSOLVER_VIZ_MAX_RUNTIME_VARS", "500"))
        self.max_packets_per_ui_tick = int(os.environ.get("FMUSOLVER_VIZ_MAX_PACKETS_PER_TICK", "3"))
        self.packet_queue = queue.Queue(maxsize=int(os.environ.get("FMUSOLVER_VIZ_PACKET_QUEUE_MAX", "20")))
        self.memory_soft_limit_mb = int(os.environ.get("FMUSOLVER_VIZ_MEMORY_SOFT_LIMIT_MB", "900"))
        self.trend_times = []
        self.trend_store = {}
        self.trend_bucket_start = None
        self.trend_bucket_end = None
        self.trend_bucket_values = {}
        self.trend_bucket_last_values = {}
        self.latest_values = {}
        self.last_displayed_strs = {} 
        self.last_curve_update_idx = {}
        self.last_view_update = {}
        self.last_y_range = {}
        self.last_ui_idx = -1
        self.max_dock_updates_per_tick = 2
        self.rx_packet_count = 0
        self.rx_error_count = 0
        self.rx_drop_count = 0
        self.rx_var_count_total = 0
        self.process_packet_count = 0
        self.process_var_count_total = 0
        self.ui_tick_count = 0
        self.ui_curve_updates = 0
        self.ui_skipped_docks = 0
        self.perf_log_file = os.path.join(APP_DIR, "visualizer_perf.log")
        self.last_perf_log_wall = time.time()
        self.last_gc_wall = time.time()
        self.last_memory_guard_wall = time.time()
        try:
            with open(self.perf_log_file, "a", encoding="utf-8") as f:
                f.write(
                    f"\n[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SESSION][VIZ] "
                    f"pid={os.getpid()} port={self.port} queue={self.packet_queue.maxsize} "
                    f"max_packets_per_tick={self.max_packets_per_ui_tick} app_dir={APP_DIR}\n"
                )
        except Exception:
            pass
        
        self.docks = {}        
        self.plot_widgets = {} 
        self.curves = {}       
        self.crosshairs = {}   
        self.dock_order = []
        self._restoring_preset = False
        self._session_memory_pause = 0
        self._startup_layout_ready = False
        self.central_plot_name = "Main Plot"
        self.legacy_default_dock_names = {self.central_plot_name}
        
        self.var_styles = {}   
        self.vars_desc = {}    
        self.ordered_tags = []
        self.base_datetime = None
        self.base_sim_time = 0
        
        self.sync_state_file = os.path.join(APP_DIR, "viz_sync_state.json")
        self.ui_settings_file = os.path.join(APP_DIR, "viz_ui_settings.json")
        self._drag_pos = None
        
        self.load_config()
        self.central_widget = QWidget()
        self.central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setDockOptions(
            QMainWindow.AllowNestedDocks |
            QMainWindow.AllowTabbedDocks |
            QMainWindow.AnimatedDocks |
            QMainWindow.GroupedDragging
        )
        
        self.setup_ui()
        self.setup_network()
        self.watcher = QFileSystemWatcher() # 必须在 apply_theme 前初始化
        
        self.apply_theme_from_config()
        set_blur_behind(self.winId())
        
        # Follow launcher theme (Watcher + Polling Fallback)
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.apply_theme_from_config)
        self.poll_timer.start(2000) # 2秒轮询一次，作为 Watcher 的兜底
        self.parent_pid = os.environ.get("FMUSOLVER_PARENT_PID", "")
        if self.parent_pid:
            self.parent_watch_timer = QTimer(self)
            self.parent_watch_timer.timeout.connect(self.check_parent_process)
            self.parent_watch_timer.start(1000)
        
        cfg_path = self.find_config_path()
        if cfg_path:
            try:
                self.watcher.addPath(cfg_path)
                self.watcher.addPath(os.path.dirname(cfg_path))
            except: pass
        self.watcher.fileChanged.connect(self.apply_theme_from_config)
        self.watcher.directoryChanged.connect(self.apply_theme_from_config)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(50) 

    def check_parent_process(self):
        if self.parent_pid and not is_process_alive(self.parent_pid):
            try:
                with open(self.perf_log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SESSION][VIZ] Parent {self.parent_pid} gone; exiting.\n")
            except Exception:
                pass
            self.running = False
            self.close()

    def find_config_path(self):
        paths = [
            os.path.join(APP_DIR, "gui_config.json"),
            os.path.join(os.path.dirname(APP_DIR), "gui_config.json"),
            "gui_config.json"
        ]
        for p in paths:
            if os.path.exists(p): return os.path.abspath(p)
        return None

    def apply_theme_from_config(self):
        cfg_path = self.find_config_path()
        bg_c, text_c = QColor(240, 242, 246), None
        status_text = "🎨 主题同步: 未找到配置"
        
        if cfg_path:
            try:
                # 性能优化：仅在文件修改时间变化时重新加载
                mtime = os.path.getmtime(cfg_path)
                if hasattr(self, '_last_theme_mtime') and self._last_theme_mtime == mtime:
                    return
                self._last_theme_mtime = mtime
                
                if cfg_path not in self.watcher.files():
                    try: self.watcher.addPath(cfg_path)
                    except: pass
                    
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    c = json.load(f)
                    raw_bg = c.get("bg_color", c.get("bg"))
                    raw_text = c.get("text_color", c.get("text"))
                    if raw_bg: bg_c = QColor(raw_bg)
                    if raw_text: text_c = QColor(raw_text)
                print(f"[ThemeSync] Loaded from {cfg_path}: bg={bg_c.name()}, text={text_c.name() if text_c else 'None'}")
            except Exception as e: 
                print(f"[ThemeSync] Error loading config: {e}")
            
        print(f"[ThemeSync] Applying theme: bg={bg_c.name()}, text={text_c.name() if text_c else 'None'}")
        self.apply_theme(bg_c, text_c)

    def load_config(self):
        paths = [os.path.join(APP_DIR, "sync_fields.json"), os.path.join(APP_DIR, "..", "sync_fields.json"), "sync_fields.json"]
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        raw_data = json.load(f)
                    parsed_vars = []
                    for item in raw_data:
                        # 核心：如果设置了 sync=False，则完全忽略该变量
                        if isinstance(item, dict) and not item.get("sync", True):
                            continue
                            
                        if isinstance(item, dict):
                            # 如果是标准的 JSON 格式，直接信任 name 字段，不再进行二次正则拆分
                            # 这样可以保持 [1], [2] 等索引不被丢失
                            name = item.get("name", "")
                            desc = item.get("desc") or item.get("description") or ""
                            parsed_vars.append({"name": name, "desc": desc})
                        elif isinstance(item, str):
                            # 仅对老旧字符串行模式进行拆分逻辑
                            name, desc, count = item, "", 1
                            if "Real " in item:
                                parts = item.split("Real ")[1].split("=")
                                name = parts[0].strip()
                                if "\"" in item:
                                    desc = item.split("\"")[1].split("\"")[0]
                            elif "=" in item:
                                name = item.split("=")[0].strip()
                                
                            import re
                            m = re.search(r'(?:output\s+)?(?:(Real|Integer|Boolean|String)\s+)?([a-zA-Z0-9_\.]+)(?:\[(\d+)\])?', name)
                            if m:
                                base_name = m.group(2)
                                count = int(m.group(3)) if m.group(3) else 1
                                if count > 1:
                                    for i in range(1, count + 1):
                                        parsed_vars.append({
                                            "name": f"{base_name}[{i}]",
                                            "desc": f"{desc} ({i}/{count})" if desc else f"[{i}]"
                                        })
                                else:
                                    parsed_vars.append({"name": base_name, "desc": desc})
                            else:
                                parsed_vars.append({"name": name, "desc": desc})
                    
                    self.vars_config = parsed_vars
                    for i, v in enumerate(self.vars_config):
                        name = v['name']
                        self.ordered_tags.append(name)
                        self.data_store[name] = np.full(self.max_points, np.nan)
                        self.trend_store[name] = []
                        self.var_styles[name] = {"color": pg.intColor(i, hues=max(10, len(self.vars_config))), "width": 2}
                        self.vars_desc[name] = v.get('desc') or ""
                    return
                except Exception as e:
                    print(f"Config load error: {e}")

    def apply_theme(self, base_color, text_color=None):
        r, g, b = base_color.red(), base_color.green(), base_color.blue()
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        is_dark = brightness < 128
        text_c = text_color.name() if text_color else ("#FFFFFF" if is_dark else "#15181E")

        print(f"[ThemeApply] base_color={base_color.name()}, is_dark={is_dark}, text_c={text_c}")

        accent = "#5AC8FA" if is_dark else "#0A84FF"
        shell_alpha = 205
        content_alpha = 150
        card_alpha = 224
        subcard_alpha = 205
        shell_r, shell_g, shell_b = r, g, b
        if is_dark:
            card_r, card_g, card_b = min(r + 16, 255), min(g + 16, 255), min(b + 16, 255)
            subcard_r, subcard_g, subcard_b = min(r + 24, 255), min(g + 24, 255), min(b + 24, 255)
        else:
            card_r, card_g, card_b = min(r + 10, 255), min(g + 10, 255), min(b + 10, 255)
            subcard_r, subcard_g, subcard_b = min(r + 18, 255), min(g + 18, 255), min(b + 18, 255)

        main_bg = f"rgba({shell_r}, {shell_g}, {shell_b}, {shell_alpha})"
        content_bg = f"rgba({shell_r}, {shell_g}, {shell_b}, {content_alpha})"
        card_bg = f"rgba({card_r}, {card_g}, {card_b}, {card_alpha})"
        subcard_bg = f"rgba({subcard_r}, {subcard_g}, {subcard_b}, {subcard_alpha})"
        solid_card_bg = f"rgb({card_r}, {card_g}, {card_b})"
        border_soft = "rgba(255, 255, 255, 34)" if is_dark else "rgba(255, 255, 255, 132)"
        border_strong = "rgba(255, 255, 255, 54)" if is_dark else "rgba(205, 210, 220, 235)"
        input_bg = "rgba(255, 255, 255, 18)" if is_dark else "rgba(0, 0, 0, 13)"
        btn_bg = subcard_bg
        btn_hover = "rgba(255, 255, 255, 54)" if is_dark else "rgba(255, 255, 255, 240)"
        btn_pressed = "rgba(255, 255, 255, 28)" if is_dark else "rgba(232, 235, 240, 245)"
        muted_text = "rgba(235, 235, 245, 0.72)" if is_dark else "#6B7280"

        self.plot_bg = QColor(card_r, card_g, card_b)
        self.plot_grid = "rgba(255,255,255,55)" if is_dark else "rgba(15,23,42,35)"
        self.plot_axis_text = QColor(text_c)
        self.plot_axis_pen = QColor(border_strong)
        self.plot_crosshair_pen = QColor(accent)
        self.plot_label_fill = pg.mkBrush(card_r, card_g, card_b, 230)
        self.plot_label_border = pg.mkPen(QColor(border_soft))
        for pw in self.plot_widgets.values():
            pw.setBackground(self.plot_bg)
            pw.showGrid(x=True, y=True, alpha=0.15 if is_dark else 0.1)
            plot_item = pw.getPlotItem()
            for axis_name in ('left', 'bottom'):
                axis = plot_item.getAxis(axis_name)
                axis.setTextPen(self.plot_axis_text)
                axis.setPen(self.plot_axis_pen)
            if plot_item.legend is not None:
                plot_item.legend.setLabelTextColor(self.plot_axis_text)

        for dock_name, crosshair in self.crosshairs.items():
            vline, label = crosshair
            vline.setPen(pg.mkPen(self.plot_crosshair_pen, width=1, style=Qt.DashLine))
            label.setColor(self.plot_axis_text)
            label.fill = self.plot_label_fill
            label.border = self.plot_label_border

        self.current_card_bg = QColor(card_r, card_g, card_b, 235)
        self.current_text_c = QColor(text_c)
        self.current_border_c = QColor(255, 255, 255, 48) if is_dark else QColor(210, 214, 224, 230)
        self.dock_theme_qss = f"""
        QDockWidget {{ background: transparent; titlebar-close-icon: none; titlebar-normal-icon: none; border: none; }}
        QWidget#DockTitleBar {{
            background: {card_bg};
            border: 1px solid {border_soft};
            border-bottom: none;
            border-top-left-radius: 14px;
            border-top-right-radius: 14px;
        }}
        QLabel#DockTitleLabel {{ color: {text_c}; font-weight: 800; padding: 0; margin: 0; }}
        QPushButton#DockCloseButton {{
            background: rgba(15, 23, 42, 0.05);
            color: {muted_text};
            border: 1px solid {border_soft};
            border-radius: 12px;
            padding: 0;
            font-size: 15px;
            font-weight: 700;
            min-width: 24px;
            max-width: 24px;
            min-height: 24px;
            max-height: 24px;
        }}
        QPushButton#DockCloseButton:hover {{
            background: rgba(255, 95, 86, 0.14);
            color: #FF5F56;
            border: 1px solid rgba(255, 95, 86, 0.28);
        }}
        QPushButton#DockCloseButton:pressed {{ background: rgba(255, 95, 86, 0.22); }}
        """
        
        for d in self.docks.values():
            try:
                if hasattr(d, 'label'):
                    d.label.update()
            except: pass
            if isinstance(d, QDockWidget):
                self.apply_dock_theme(d)

        qss = f"""
        QMainWindow {{
            background: transparent;
            color: {text_c};
            font-family: 'SF Pro Display', 'Inter', 'PingFang SC', 'Microsoft YaHei UI', 'Segoe UI', sans-serif;
            font-size: 13px;
        }}
        #CentralWidget {{
            background: {main_bg};
            border-radius: 12px;
            border: 1px solid {border_soft};
        }}
        QWidget#ContentArea {{
            background: {content_bg};
            border-bottom-left-radius: 12px;
            border-bottom-right-radius: 12px;
        }}
        QWidget#TitleBar {{
            background: transparent;
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            border-bottom: 1px solid {border_soft};
        }}
        QLabel#BrandLabel {{ color: {text_c}; font-size: 14px; font-weight: 800; }}
        QLabel#Title {{ color: {text_c}; font-size: 12px; font-weight: 800; }}
        QLabel#Caption {{ color: {muted_text}; font-size: 11px; font-weight: 600; }}
        QLabel#StatusPill {{
            color: {accent};
            font-size: 11px;
            font-weight: 800;
            background: rgba(10, 132, 255, 20);
            border: 1px solid rgba(10, 132, 255, 30);
            border-radius: 11px;
            padding: 4px 10px;
        }}

        QMainWindow::separator {{ background: transparent; width: 4px; height: 4px; }}
        QMainWindow::separator:hover {{ background: rgba(10,132,255,48); }}
        QDockWidget {{ background: transparent; titlebar-close-icon: none; titlebar-normal-icon: none; border: none; }}
        QDockWidget::title {{
            text-align: left;
            background: {card_bg};
            color: {text_c};
            border: 1px solid {border_soft};
            border-bottom: none;
            border-top-left-radius: 14px;
            border-top-right-radius: 14px;
            padding: 10px 14px;
            font-size: 12px;
            font-weight: 800;
        }}
        QWidget#DockTitleBar {{
            background: {card_bg};
            border: 1px solid {border_soft};
            border-bottom: none;
            border-top-left-radius: 14px;
            border-top-right-radius: 14px;
        }}
        QLabel#DockTitleLabel {{ color: {text_c}; font-weight: 800; padding: 0; margin: 0; }}
        QPushButton#DockCloseButton {{
            background: rgba(15, 23, 42, 0.05);
            color: {muted_text};
            border: 1px solid {border_soft};
            border-radius: 12px;
            padding: 0;
            font-size: 15px;
            font-weight: 700;
            min-width: 24px;
            max-width: 24px;
            min-height: 24px;
            max-height: 24px;
        }}
        QPushButton#DockCloseButton:hover {{
            background: rgba(255, 95, 86, 0.14);
            color: #FF5F56;
            border: 1px solid rgba(255, 95, 86, 0.28);
        }}
        QPushButton#DockCloseButton:pressed {{ background: rgba(255, 95, 86, 0.22); }}

        QFrame#LeftPanel, QFrame#SubPanel {{ background: {card_bg}; border: 1px solid {border_soft}; border-radius: 14px; }}
        QFrame#PanelInset {{ background: {subcard_bg}; border: 1px solid {border_soft}; border-radius: 12px; }}
        QFrame#LeftPanel {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {card_bg},
                stop:0.55 {subcard_bg},
                stop:1 {card_bg});
            border: 1px solid {border_soft};
        }}
        QFrame#SubPanel {{
            background: {subcard_bg};
            border: 1px solid {border_soft};
        }}
        QPushButton#SidebarBtn {{ 
            background: transparent; 
            font-size: 22px; 
            border: none; 
            color: {text_c}; 
            border-radius: 15px; 
            padding: 0px; 
            min-height: 30px; 
            min-width: 30px; 
            max-height: 30px; 
            max-width: 30px; 
        }}
        QPushButton#SidebarBtn:hover {{ background: rgba(0,0,0,0.1); }}
        QPushButton {{ background: {btn_bg}; color: {text_c}; border: 1px solid {border_soft}; border-radius: 16px; padding: 0 14px; font-weight: 700; font-size: 12px; min-height: 32px; max-height: 32px; }}
        QPushButton:hover {{ background: {btn_hover}; border: 1px solid {border_strong}; }}
        QPushButton:pressed {{ background: {btn_pressed}; }}
        QPushButton#PrimaryButton {{ background: {accent}; color: white; border: 1px solid rgba(10,132,255,160); }}
        QPushButton#PrimaryButton:hover {{ background: #2591FF; }}
        QPushButton#ControlBtn {{ padding: 0; border-radius: 50%; min-width: 14px; max-width: 14px; min-height: 14px; max-height: 14px; }}

        QTableWidget, QListWidget {{ background: transparent; border: none; color: {text_c}; selection-background-color: rgba(10,132,255,40); selection-color: {text_c}; outline: none; alternate-background-color: rgba(255,255,255,0.30); }}
        QTableWidget::item, QListWidget::item {{ padding: 7px 8px; border-radius: 10px; border-bottom: 1px solid {border_soft}; }}
        QTableWidget::item:selected, QListWidget::item:selected {{ background: rgba(10,132,255,0.08); }}
        QHeaderView::section {{ background: transparent; color: {muted_text}; font-size: 11px; font-weight: 800; border: none; border-bottom: 1px solid {border_soft}; padding: 6px 4px; }}
        QTableCornerButton::section {{ background: transparent; border: none; }}

        QCheckBox {{ color: {text_c}; font-weight: 700; spacing: 8px; }}
        QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; background: {input_bg}; border: 1px solid {border_strong}; }}
        QCheckBox::indicator:checked {{ background: {accent}; border: 1px solid {accent}; }}
        QSpinBox, QComboBox {{ background: {input_bg}; color: {text_c}; border: 1px solid {border_soft}; border-radius: 10px; padding: 2px 8px; min-height: 28px; }}
        QSpinBox::up-button, QSpinBox::down-button {{
            subcontrol-origin: padding;
            width: 18px;
            border: none;
            background: transparent;
            margin-right: 2px;
        }}
        QSpinBox::up-arrow, QSpinBox::down-arrow {{ width: 8px; height: 8px; }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QListView#ComboView {{ background: {solid_card_bg}; color: {text_c}; border: 1px solid {border_strong}; selection-background-color: rgba(10, 132, 255, 60); show-decoration-selected: 1; outline: none; border-radius: 10px; }}
        QListView#ComboView::item {{ padding: 6px 8px; color: {text_c}; background: transparent; }}

        QScrollBar:vertical {{ border: none; background: transparent; width: 8px; }}
        QScrollBar::handle:vertical {{ background: rgba(160,168,180,0.72); min-height: 30px; border-radius: 4px; }}
        QSplitter::handle {{ background: transparent; }}
        QSplitter::handle:horizontal {{ width: 4px; margin: 6px 0; border-radius: 2px; background: rgba(255,255,255,18); }}
        QSplitter::handle:horizontal:hover {{ background: rgba(10,132,255,42); }}
        QSplitter::handle:vertical {{ height: 4px; margin: 0 6px; border-radius: 2px; background: rgba(255,255,255,18); }}
        QSplitter::handle:vertical:hover {{ background: rgba(10,132,255,42); }}
        """
        self.setStyleSheet(qss)

    def setup_ui(self):
        vlay = self.main_layout
        
        self.title_bar = TitleBar(self); vlay.addWidget(self.title_bar)
        
        content_area = QWidget(); content_area.setObjectName("ContentArea"); vlay.addWidget(content_area, 1)
        main_layout = QHBoxLayout(content_area); main_layout.setContentsMargins(12, 8, 12, 12); main_layout.setSpacing(10)
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(4)
        self.main_splitter.splitterMoved.connect(lambda *_: self.save_ui_settings())
        
        self.left_panel = QFrame(); self.left_panel.setObjectName("LeftPanel")
        self.left_panel.setMinimumWidth(0)
        self.left_panel.setMaximumWidth(520)
        self.last_sidebar_width = 320
        left_layout = QVBoxLayout(self.left_panel); left_layout.setContentsMargins(14, 14, 14, 14); left_layout.setSpacing(10)

        panel_header = QHBoxLayout(); panel_header.setContentsMargins(0, 0, 0, 0)
        panel_header.addStretch()
        self.lbl_active_dock = QLabel("未选中窗口")
        self.lbl_active_dock.setObjectName("StatusPill")
        panel_header.addWidget(self.lbl_active_dock)
        left_layout.addLayout(panel_header)
        
        ctrl_row = QHBoxLayout(); ctrl_row.setSpacing(6)
        add_dock_btn = QPushButton("+ 新建窗口"); add_dock_btn.setObjectName("PrimaryButton")
        add_dock_btn.clicked.connect(self.create_new_dock)
        ctrl_row.addWidget(add_dock_btn)
        export_word_btn = QPushButton("导出 Word")
        export_word_btn.clicked.connect(self.export_charts_to_word)
        ctrl_row.addWidget(export_word_btn)
        self.chk_autoscroll = QCheckBox("Realtime"); self.chk_autoscroll.setChecked(True)
        self.chk_autoscroll.toggled.connect(self.on_realtime_toggled)
        ctrl_row.addWidget(self.chk_autoscroll)
        left_layout.addLayout(ctrl_row)

        trend_row = QHBoxLayout(); trend_row.setSpacing(6)
        trend_row.addStretch()
        self.chk_accumulate = QCheckBox("累积趋势")
        self.chk_accumulate.setChecked(False)
        self.chk_accumulate.toggled.connect(self.on_accumulate_toggled)
        trend_row.addWidget(self.chk_accumulate)
        left_layout.addLayout(trend_row)
        
        # Compact Settings Area
        settings_box = QFrame(); settings_box.setObjectName("PanelInset")
        slay = QGridLayout(settings_box); slay.setContentsMargins(10, 10, 10, 10); slay.setSpacing(6)
        
        slay.addWidget(QLabel("Title:"), 0, 0)
        self.title_size_spin = QSpinBox(); self.title_size_spin.setRange(8, 30); self.title_size_spin.setValue(13)
        self.title_size_spin.valueChanged.connect(self.update_all_labels); slay.addWidget(self.title_size_spin, 0, 1)
        
        slay.addWidget(QLabel("Mode:"), 1, 0)
        self.name_mode_combo = QComboBox(); self.name_mode_combo.addItems(["Tag", "Desc", "Both"])
        v = QListView(); v.setObjectName("ComboView")
        self.name_mode_combo.setView(v)
        if v.window(): v.window().setAttribute(Qt.WA_TranslucentBackground, False)
        self.name_mode_combo.currentIndexChanged.connect(self.update_all_labels); slay.addWidget(self.name_mode_combo, 1, 1)
        
        slay.addWidget(QLabel("Span (s):"), 2, 0)
        self.span_spin = QSpinBox(); self.span_spin.setRange(1, 3600); self.span_spin.setValue(60)
        slay.addWidget(self.span_spin, 2, 1)
        
        left_layout.addWidget(settings_box)
        
        # 使用 QSplitter 让变量表格和预设列表可以上下拖动调整高度
        self.left_splitter = QSplitter(Qt.Vertical)
        self.left_splitter.setChildrenCollapsible(False)
        self.left_splitter.setHandleWidth(4)
        self.left_splitter.splitterMoved.connect(lambda *_: self.save_ui_settings())
        
        # 上半部分：变量表格容器
        self.table = QTableWidget(len(self.vars_config), 3)
        self.table.setHorizontalHeaderLabels(["S", "Name", "Value"])
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 34); self.table.setColumnWidth(1, 160); self.table.setColumnWidth(2, 92)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_menu)
        
        self.table_container = QFrame(); self.table_container.setObjectName("SubPanel")
        table_vlay = QVBoxLayout(self.table_container); table_vlay.setContentsMargins(10,10,10,10); table_vlay.setSpacing(8)
        table_vlay.addWidget(lbl("变量列表", obj="Title"))
        table_vlay.addWidget(self.table)
        self.left_splitter.addWidget(self.table_container)
        
        # 下半部分：预设管理容器
        self.preset_container = QFrame(); self.preset_container.setObjectName("SubPanel")
        preset_vlay = QVBoxLayout(self.preset_container); preset_vlay.setContentsMargins(10,10,10,10); preset_vlay.setSpacing(8)
        preset_vlay.addWidget(lbl("看板预设", obj="Title"))
        self.preset_list = QListWidget()
        self.preset_list.setObjectName("PresetList")
        self.preset_list.itemClicked.connect(self.on_preset_clicked)
        preset_vlay.addWidget(self.preset_list)
        
        pre_btns = QHBoxLayout()
        b_save = QPushButton("保存当前")
        b_del = QPushButton("删除预设")
        b_save.clicked.connect(self.save_preset_dialog)
        b_del.clicked.connect(self.delete_preset)
        pre_btns.addWidget(b_save); pre_btns.addWidget(b_del)
        preset_vlay.addLayout(pre_btns)
        
        self.left_splitter.addWidget(self.preset_container)
        self.left_splitter.setStretchFactor(0, 3) # 表格占更多空间
        self.left_splitter.setStretchFactor(1, 1)
        
        # 将 splitter 添加到左侧面板布局
        left_layout.addWidget(self.left_splitter)
        
        self.main_splitter.addWidget(self.left_panel)
        self.dock_background = QFrame()
        self.dock_background.setObjectName("PanelInset")
        dock_background_layout = QVBoxLayout(self.dock_background)
        dock_background_layout.setContentsMargins(4, 4, 4, 4)
        dock_background_layout.setSpacing(0)
        self.dock_host = QMainWindow()
        self.dock_host.setDockOptions(
            QMainWindow.AllowNestedDocks |
            QMainWindow.AllowTabbedDocks |
            QMainWindow.AnimatedDocks |
            QMainWindow.GroupedDragging
        )
        self.dock_host.setDocumentMode(True)
        self.dock_canvas = QWidget()
        self.dock_canvas.setObjectName("DockCanvas")
        self.dock_host.setCentralWidget(self.dock_canvas)
        old_central = self.dock_host.takeCentralWidget()
        if old_central is not None:
            old_central.hide()
            old_central.deleteLater()
        self.dock_host.setMinimumWidth(420)
        dock_background_layout.addWidget(self.dock_host)
        self.main_splitter.addWidget(self.dock_background)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        main_layout.addWidget(self.main_splitter)
        
        self.load_sync_state()
        for i, tag in enumerate(self.ordered_tags):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            
            # 仅设置初始状态，由 LastSession 统一负责恢复具体 Dock 关联
            saved_state = self.sync_states.get(tag, False)
            chk.setCheckState(Qt.Checked if saved_state else Qt.Unchecked)
            
            self.table.setItem(i, 0, chk)
            self.table.setItem(i, 1, QTableWidgetItem(self.get_display_name(tag)))
            self.table.setItem(i, 2, QTableWidgetItem("0.0000"))
        
        self.table.itemChanged.connect(self.on_table_item_changed)

        self.load_presets()
        self.load_ui_settings()
        # 初始加载默认或上一次的布局
        QTimer.singleShot(500, self.auto_load_last_layout)

    def register_runtime_variable(self, tag, desc=""):
        """Add variables received at runtime to the dashboard only, without touching sync_fields.json."""
        if not tag or tag in self.data_store:
            return
        if len([v for v in self.vars_config if v.get("runtime")]) >= self.max_runtime_variables:
            if not hasattr(self, '_runtime_var_limit_warned'):
                self._runtime_var_limit_warned = True
                try:
                    with open(self.perf_log_file, "a", encoding="utf-8") as f:
                        f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [WARN][VIZ] Runtime variable limit reached: {self.max_runtime_variables}. New variables will be ignored for stability.\n")
                except Exception:
                    pass
            return
        row = self.table.rowCount()
        self.table.blockSignals(True)
        self.table.insertRow(row)
        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        chk.setCheckState(Qt.Unchecked)
        self.table.setItem(row, 0, chk)
        self.table.setItem(row, 1, QTableWidgetItem(self.get_display_name(tag)))
        self.table.setItem(row, 2, QTableWidgetItem("0.0000"))
        self.table.blockSignals(False)

        self.ordered_tags.append(tag)
        self.vars_config.append({"name": tag, "desc": desc, "runtime": True})
        self.data_store[tag] = np.full(self.max_points, np.nan)
        self.trend_store[tag] = []
        self.var_styles[tag] = {"color": pg.intColor(len(self.ordered_tags) - 1, hues=max(10, len(self.ordered_tags))), "width": 2}
        self.vars_desc[tag] = desc

    def auto_load_last_layout(self):
        if "LastSession" in self.presets:
            self.load_preset("LastSession")
        else:
            self.refresh_preset_list()
        QTimer.singleShot(240, self.finish_startup_layout_restore)

    def finish_startup_layout_restore(self):
        self._startup_layout_ready = True

    def pause_session_memory(self):
        self._session_memory_pause += 1

    def resume_session_memory(self):
        self._session_memory_pause = max(0, self._session_memory_pause - 1)

    def schedule_session_memory_resume(self, delay=180, save_after=False):
        def release():
            self.resume_session_memory()
            if save_after:
                self.remember_last_session()
        QTimer.singleShot(delay, release)

    def load_presets(self):
        self.presets_file = os.path.join(APP_DIR, "viz_presets.json")
        self.presets = {}
        if os.path.exists(self.presets_file):
            try:
                with open(self.presets_file, 'r', encoding='utf-8') as f:
                    self.presets = json.load(f)
            except: pass
        migrated = False
        for preset_name, preset_data in list(self.presets.items()):
            if not isinstance(preset_data, dict):
                continue
            if "layout" in preset_data:
                preset_data.pop("layout", None)
                migrated = True
            dock_vars = preset_data.get("dock_vars") or {}
            if isinstance(dock_vars, dict):
                preset_data["dock_vars"] = {name: value for name, value in dock_vars.items() if name not in self.legacy_default_dock_names or value}
                dock_vars = preset_data["dock_vars"]
            if "dock_order" not in preset_data:
                preset_data["dock_order"] = list(dock_vars.keys())
                migrated = True
            if "layout_state" not in preset_data:
                preset_data["layout_state"] = ""
                migrated = True
            if "dock_geometry" not in preset_data:
                preset_data["dock_geometry"] = {}
                migrated = True
            elif isinstance(preset_data["dock_geometry"], dict) and "__layout__" in preset_data["dock_geometry"]:
                del preset_data["dock_geometry"]["__layout__"]
                migrated = True
            if "active_dock" not in preset_data:
                preset_data["active_dock"] = preset_data["dock_order"][0] if preset_data["dock_order"] else None
                migrated = True

            if self.migrate_legacy_default_dock(preset_data):
                migrated = True
        if migrated:
            self.save_presets_to_file()
        self.refresh_preset_list()

    def migrate_legacy_default_dock(self, preset_data):
        changed = False
        dock_order = preset_data.get("dock_order")
        if not isinstance(dock_order, list):
            dock_order = []
        dock_vars = preset_data.get("dock_vars")
        if not isinstance(dock_vars, dict):
            dock_vars = {}
        dock_geometry = preset_data.get("dock_geometry")
        if not isinstance(dock_geometry, dict):
            dock_geometry = {}

        removable_names = []
        for name in list(dock_order):
            if name not in self.legacy_default_dock_names:
                continue
            var_list = dock_vars.get(name, [])
            if var_list:
                continue
            removable_names.append(name)

        if not removable_names:
            return False

        dock_order = [name for name in dock_order if name not in removable_names]
        for name in removable_names:
            dock_vars.pop(name, None)
            dock_geometry.pop(name, None)
            changed = True

        proportions = dock_geometry.get("__proportions__")
        if isinstance(proportions, dict):
            items = proportions.get("items")
            if isinstance(items, dict):
                for name in removable_names:
                    if name in items:
                        items.pop(name, None)
                        changed = True
                if not items:
                    dock_geometry.pop("__proportions__", None)
                    changed = True

        active_dock = preset_data.get("active_dock")
        if active_dock in removable_names:
            preset_data["active_dock"] = dock_order[0] if dock_order else None
            changed = True

        preset_data["dock_order"] = dock_order
        preset_data["dock_vars"] = dock_vars
        preset_data["dock_geometry"] = dock_geometry
        return changed

    def refresh_preset_list(self):
        self.preset_list.clear()
        for name in self.presets:
            if name == "LastSession": continue
            self.preset_list.addItem(name)

    def save_preset_dialog(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "保存预设", "请输入预设名称:")
        if ok and name.strip():
            self.save_preset(name.strip())

    def serialize_dock_layout(self):
        try:
            return bytes(self.dock_host.saveState().toBase64()).decode('ascii')
        except Exception:
            return ""

    def serialize_dock_geometry(self):
        geometry = {}
        non_floating = []
        for name, dock in self.docks.items():
            if not isinstance(dock, QDockWidget):
                continue
            info = {
                "floating": bool(dock.isFloating()),
                "x": int(dock.x()),
                "y": int(dock.y()),
                "w": int(dock.width()),
                "h": int(dock.height()),
            }
            geometry[name] = info
            if not info["floating"] and dock.isVisible():
                non_floating.append((name, info))

        min_x = None
        min_y = None
        max_x = None
        max_y = None
        if non_floating:
            for _, info in non_floating:
                right = info["x"] + info["w"]
                bottom = info["y"] + info["h"]
                min_x = info["x"] if min_x is None else min(min_x, info["x"])
                min_y = info["y"] if min_y is None else min(min_y, info["y"])
                max_x = right if max_x is None else max(max_x, right)
                max_y = bottom if max_y is None else max(max_y, bottom)

            total_w = max(1, max_x - min_x)
            total_h = max(1, max_y - min_y)
            ratio_items = {}
            for name, info in non_floating:
                ratio_items[name] = {
                    "x_ratio": (info["x"] - min_x) / total_w,
                    "y_ratio": (info["y"] - min_y) / total_h,
                    "w_ratio": info["w"] / total_w,
                    "h_ratio": info["h"] / total_h,
                }

            geometry["__proportions__"] = {
                "bounds": {
                    "x": min_x,
                    "y": min_y,
                    "w": total_w,
                    "h": total_h,
                },
                "items": ratio_items,
            }
        return geometry

    def collect_layout_groups(self, docks, orientation):
        groups = []
        if not docks:
            return groups

        rects = []
        for dock in docks:
            geo = dock.geometry()
            rects.append({
                "dock": dock,
                "x": geo.x(),
                "y": geo.y(),
                "w": max(1, geo.width()),
                "h": max(1, geo.height()),
            })

        if orientation == Qt.Horizontal:
            rects.sort(key=lambda item: (item["y"], item["x"]))
            threshold = max(28, int(self.dock_host.height() * 0.08))
            for item in rects:
                center = item["y"] + item["h"] / 2.0
                if not groups:
                    groups.append({"center": center, "items": [item]})
                    continue
                last = groups[-1]
                overlap = min(item["y"] + item["h"], max(i["y"] + i["h"] for i in last["items"])) - max(item["y"], min(i["y"] for i in last["items"]))
                same_band = overlap > min(item["h"], min(i["h"] for i in last["items"])) * 0.35
                if same_band or abs(center - last["center"]) <= threshold:
                    last["items"].append(item)
                    last["center"] = sum(i["y"] + i["h"] / 2.0 for i in last["items"]) / len(last["items"])
                else:
                    groups.append({"center": center, "items": [item]})
            return [sorted(group["items"], key=lambda item: item["x"]) for group in groups]

        rects.sort(key=lambda item: (item["x"], item["y"]))
        threshold = max(28, int(self.dock_host.width() * 0.08))
        for item in rects:
            center = item["x"] + item["w"] / 2.0
            if not groups:
                groups.append({"center": center, "items": [item]})
                continue
            last = groups[-1]
            overlap = min(item["x"] + item["w"], max(i["x"] + i["w"] for i in last["items"])) - max(item["x"], min(i["x"] for i in last["items"]))
            same_band = overlap > min(item["w"], min(i["w"] for i in last["items"])) * 0.35
            if same_band or abs(center - last["center"]) <= threshold:
                last["items"].append(item)
                last["center"] = sum(i["x"] + i["w"] / 2.0 for i in last["items"]) / len(last["items"])
            else:
                groups.append({"center": center, "items": [item]})
        return [sorted(group["items"], key=lambda item: item["y"]) for group in groups]

    def restore_dock_proportions(self, proportion_data):
        if not isinstance(proportion_data, dict):
            return False
        item_data = proportion_data.get("items", {})
        if not isinstance(item_data, dict) or not item_data:
            return False

        active_docks = []
        for name, dock in self.docks.items():
            if not isinstance(dock, QDockWidget):
                continue
            if dock.isFloating() or not dock.isVisible() or name not in item_data:
                continue
            active_docks.append(dock)

        if not active_docks:
            return False

        changed = False
        horizontal_groups = self.collect_layout_groups(active_docks, Qt.Horizontal)
        for group in horizontal_groups:
            if len(group) < 2:
                continue
            docks = [item["dock"] for item in group]
            widths = []
            valid = True
            for item in group:
                ratios = item_data.get(item["dock"].dock_key, {})
                ratio = float(ratios.get("w_ratio", 0.0))
                if ratio <= 0:
                    valid = False
                    break
                widths.append(max(220, int(ratio * max(1, self.dock_host.width()))))
            if valid:
                try:
                    self.dock_host.resizeDocks(docks, widths, Qt.Horizontal)
                    changed = True
                except Exception:
                    pass

        vertical_groups = self.collect_layout_groups(active_docks, Qt.Vertical)
        for group in vertical_groups:
            if len(group) < 2:
                continue
            docks = [item["dock"] for item in group]
            heights = []
            valid = True
            for item in group:
                ratios = item_data.get(item["dock"].dock_key, {})
                ratio = float(ratios.get("h_ratio", 0.0))
                if ratio <= 0:
                    valid = False
                    break
                heights.append(max(180, int(ratio * max(1, self.dock_host.height()))))
            if valid:
                try:
                    self.dock_host.resizeDocks(docks, heights, Qt.Vertical)
                    changed = True
                except Exception:
                    pass
        return changed

    def restore_dock_layout(self, layout_state):
        if not layout_state:
            return False
        try:
            raw = QByteArray.fromBase64(layout_state.encode('ascii'))
            return self.dock_host.restoreState(raw)
        except Exception:
            return False

    def restore_dock_geometry(self, geometry):
        if not isinstance(geometry, dict):
            return
        self.restore_dock_proportions(geometry.get("__proportions__", {}))

        for name, info in geometry.items():
            if name.startswith("__"):
                continue
            dock = self.docks.get(name)
            if not isinstance(dock, QDockWidget):
                continue
            try:
                floating = bool(info.get("floating", False))
                if dock.isFloating() != floating:
                    dock.setFloating(floating)
                w = max(320, int(info.get("w", dock.width())))
                h = max(240, int(info.get("h", dock.height())))
                dock.resize(w, h)
                if floating:
                    dock.move(int(info.get("x", dock.x())), int(info.get("y", dock.y())))
            except Exception:
                pass

    def remember_last_session(self):
        if self._restoring_preset or self._session_memory_pause > 0 or not self._startup_layout_ready or not hasattr(self, 'presets'):
            return
        self.save_preset("LastSession", refresh_list=False)

    def save_preset(self, name, refresh_list=True):
        # 记录布局和变量配置
        dock_data = {}
        for d_name, d_obj in self.docks.items():
            active_vars = []
            for tag in self.ordered_tags:
                if tag in self.curves and d_name in self.curves[tag]:
                    active_vars.append(tag)
            dock_data[d_name] = active_vars
        
        preset = {
            "dock_order": [dock_name for dock_name in self.dock_order if dock_name in self.docks],
            "dock_vars": dock_data,
            "layout_state": self.serialize_dock_layout(),
            "dock_geometry": self.serialize_dock_geometry(),
            "active_dock": self.active_dock_name if getattr(self, 'active_dock_name', None) in self.docks else (self.dock_order[0] if self.dock_order else None)
        }
        self.presets[name] = preset
        self.save_presets_to_file()
        if refresh_list and name != "LastSession":
            self.refresh_preset_list()

    def save_presets_to_file(self):
        try:
            with open(self.presets_file, 'w', encoding='utf-8') as f:
                json.dump(self.presets, f, ensure_ascii=False, indent=2)
        except: pass

    def on_preset_clicked(self, item):
        self.load_preset(item.text())

    def clear_all_docks_for_restore(self):
        for d_name in list(self.docks.keys()):
            dock = self.docks.get(d_name)
            if not isinstance(dock, QDockWidget):
                continue
            try:
                dock.closed.disconnect()
            except Exception:
                pass
            try:
                dock.topLevelChanged.disconnect()
            except Exception:
                pass
            try:
                self.dock_host.removeDockWidget(dock)
            except Exception:
                pass
            try:
                dock.hide()
                dock.setParent(None)
                dock.deleteLater()
            except Exception:
                pass

    def load_preset(self, name):
        if name not in self.presets: return
        data = self.presets[name]
        self._restoring_preset = True
        self.pause_session_memory()

        try:
            # 1. 清理现有布局。这里不能用 close()，否则旧 dock 的关闭信号会在稍后误伤同名新 dock。
            self.clear_all_docks_for_restore()
            self.docks = {}
            self.plot_widgets = {}
            self.crosshairs = {}
            self.dock_order = []
            self.active_dock_name = None
            self.curves = {}

            # 2. 重新创建 Dock 容器
            dock_vars = data.get("dock_vars", {})
            saved_order = data.get("dock_order") or list(dock_vars.keys()) or []
            saved_order = [d_name for d_name in saved_order if d_name not in self.legacy_default_dock_names or dock_vars.get(d_name)]

            for d_name in saved_order:
                self.create_dock_internal(d_name)

            # 3. 恢复变量勾选和曲线绘制
            all_active = set()
            for vlist in dock_vars.values():
                all_active.update(vlist)

            self.table.blockSignals(True)
            for i, tag in enumerate(self.ordered_tags):
                is_active = tag in all_active
                self.table.item(i, 0).setCheckState(Qt.Checked if is_active else Qt.Unchecked)
            self.table.blockSignals(False)

            for d_name, tags in dock_vars.items():
                for tag in tags:
                    if tag in self.ordered_tags:
                        self.toggle_curve_in_specific_dock(tag, Qt.Checked, d_name)

            restored = self.restore_dock_layout(data.get("layout_state", ""))
            dock_geometry = data.get("dock_geometry", {})
            if not self.docks:
                dock_geometry = {}
                restored = False
            if not restored and self.docks:
                QTimer.singleShot(0, self.normalize_dock_sizes)
            elif self.docks and not dock_geometry:
                QTimer.singleShot(0, self.normalize_dock_sizes)
            if self.docks and dock_geometry:
                QTimer.singleShot(0, lambda geom=dock_geometry: self.restore_dock_geometry(geom))
                QTimer.singleShot(60, lambda geom=dock_geometry: self.restore_dock_geometry(geom))
                QTimer.singleShot(140, lambda geom=dock_geometry: self.restore_dock_geometry(geom))

            active_name = data.get("active_dock")
            if active_name in self.docks:
                self.set_active_dock(active_name)
            elif self.docks:
                self.set_active_dock(next(iter(self.docks.keys())))
            else:
                self.lbl_active_dock.setText("未选中窗口")
        finally:
            self._restoring_preset = False
            self.schedule_session_memory_resume(delay=220, save_after=False)

    def toggle_curve_in_specific_dock(self, tag, state, dock_name):
        if dock_name not in self.docks: return
        if state == Qt.Checked or state == 2:
            if tag not in self.curves: self.curves[tag] = {}
            if dock_name not in self.curves[tag]:
                pw = self.plot_widgets[dock_name]
                c = pw.plot(pen=pg.mkPen(self.var_styles[tag]["color"], width=self.var_styles[tag]["width"]), name=tag)
                self.curves[tag][dock_name] = c
        else:
            if tag in self.curves and dock_name in self.curves[tag]:
                self.plot_widgets[dock_name].removeItem(self.curves[tag][dock_name])
                del self.curves[tag][dock_name]

    def delete_preset(self):
        item = self.preset_list.currentItem()
        if item:
            name = item.text()
            if name in self.presets:
                del self.presets[name]
                self.save_presets_to_file()
                self.refresh_preset_list()

    def toggle_maximize(self):
        if self.isMaximized(): self.showNormal()
        else: self.showMaximized()

    def nativeEvent(self, eventType, message):
        if eventType == "windows_generic_MSG":
            msg = wintypes.MSG.from_address(message.__int__())
            if msg.message == 0x0084: # WM_NCHITTEST
                pos = self.mapFromGlobal(QCursor.pos())
                lx, ly = pos.x(), pos.y()
                
                # 1. Exclusion for control buttons
                child = self.childAt(lx, ly)
                # Use type name comparison to avoid naming conflicts
                child_is_button = child and type(child).__name__ == "QPushButton"
                parent_is_button = child and child.parentWidget() and type(child.parentWidget()).__name__ == "QPushButton"
                if child_is_button or parent_is_button:
                    return False
                
                # 2. Resizing borders (8px)
                bw = 8
                w, h = self.width(), self.height()
                if lx < bw:
                    if ly < bw: return True, 13
                    if ly > h - bw: return True, 16
                    return True, 10
                if lx > w - bw:
                    if ly < bw: return True, 14
                    if ly > h - bw: return True, 17
                    return True, 11
                if ly < bw: return True, 12
                if ly > h - bw: return True, 15
                
                # 3. Title bar (36px height) - Enables Aero Snap
                if ly < 36:
                    return True, 2
                    
        return super().nativeEvent(eventType, message)

    def on_table_item_changed(self, item):
        if item.column() == 0:
            row = item.row()
            tag = self.ordered_tags[row]
            state = item.checkState()
            self.toggle_curve_in_active_dock(tag, state)
            
            # 保存记忆
            self.sync_states[tag] = (state == Qt.Checked or state == 2)
            self.save_sync_state()
            self.remember_last_session()
            
    def load_sync_state(self):
        self.sync_states = {}
        if os.path.exists(self.sync_state_file):
            try:
                with open(self.sync_state_file, 'r', encoding='utf-8') as f:
                    self.sync_states = json.load(f)
            except: pass

    def save_sync_state(self):
        try:
            with open(self.sync_state_file, 'w', encoding='utf-8') as f:
                json.dump(self.sync_states, f)
        except: pass
            
    def closeEvent(self, event):
        # 退出前保存最后一次布局记忆
        try:
            self.save_preset("LastSession")
        except: pass
        self.running = False
        self.sock.close()
        event.accept()

    def save_ui_settings(self):
        if hasattr(self, 'main_splitter') and self.left_panel.isVisible():
            sizes = self.main_splitter.sizes()
            if sizes and sizes[0] > 40:
                self.last_sidebar_width = sizes[0]
        s = {
            "title_size": self.title_size_spin.value(),
            "name_mode": self.name_mode_combo.currentIndex(),
            "span": self.span_spin.value(),
            "accumulate_enabled": self.chk_accumulate.isChecked() if hasattr(self, 'chk_accumulate') else False,
            "sidebar_visible": self.left_panel.isVisible(),
            "last_sidebar_width": self.last_sidebar_width,
            "main_splitter": self.main_splitter.sizes() if hasattr(self, 'main_splitter') else [],
            "left_splitter": self.left_splitter.sizes() if hasattr(self, 'left_splitter') else []
        }
        try:
            with open(self.ui_settings_file, 'w', encoding='utf-8') as f:
                json.dump(s, f)
        except: pass
        self.remember_last_session()

    def load_ui_settings(self):
        if not os.path.exists(self.ui_settings_file):
            QTimer.singleShot(0, lambda: self.main_splitter.setSizes([320, 960]))
            QTimer.singleShot(0, lambda: self.left_splitter.setSizes([480, 220]))
            return

        try:
            with open(self.ui_settings_file, 'r', encoding='utf-8') as f:
                s = json.load(f)
        except Exception:
            return

        self.title_size_spin.setValue(int(s.get("title_size", self.title_size_spin.value())))
        self.name_mode_combo.setCurrentIndex(int(s.get("name_mode", self.name_mode_combo.currentIndex())))
        self.span_spin.setValue(int(s.get("span", self.span_spin.value())))
        if hasattr(self, 'chk_accumulate'):
            self.chk_accumulate.setChecked(bool(s.get("accumulate_enabled", False)))
        sidebar_visible = bool(s.get("sidebar_visible", True))
        self.left_panel.setVisible(sidebar_visible)
        self.last_sidebar_width = int(s.get("last_sidebar_width", 320))

        main_sizes = s.get("main_splitter") or [320, 960]
        left_sizes = s.get("left_splitter") or [480, 220]
        if not sidebar_visible:
            main_sizes = [0, max(1, self.width())]
        QTimer.singleShot(0, lambda: self.main_splitter.setSizes(main_sizes))
        QTimer.singleShot(0, lambda: self.left_splitter.setSizes(left_sizes))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self._drag_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if self._drag_pos:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event): self._drag_pos = None
        
        
        

    def toggle_sidebar(self):
        is_visible = self.left_panel.isVisible()
        if is_visible:
            current_sizes = self.main_splitter.sizes()
            if current_sizes and current_sizes[0] > 40:
                self.last_sidebar_width = current_sizes[0]
            self.left_panel.setMinimumWidth(0)
            self.left_panel.setMaximumWidth(0)
            self.left_panel.setFixedWidth(0)
            self.left_panel.setVisible(False)
            total = max(1, self.main_splitter.width())
            self.main_splitter.setSizes([0, total])
            QTimer.singleShot(0, lambda: self.main_splitter.setSizes([0, max(1, self.main_splitter.width())]))
        else:
            self.left_panel.setMinimumWidth(0)
            self.left_panel.setMaximumWidth(520)
            self.left_panel.setFixedWidth(max(260, min(self.last_sidebar_width, 520)))
            self.left_panel.setVisible(True)
            restored = max(260, min(self.last_sidebar_width, 520))
            total = max(1, self.main_splitter.width())
            self.main_splitter.setSizes([restored, max(1, total - restored)])
            QTimer.singleShot(0, lambda r=restored: self.main_splitter.setSizes([r, max(1, self.main_splitter.width() - r)]))
        self.save_ui_settings()
        # 强制刷新布局
        if self.centralWidget() and self.centralWidget().layout():
            self.centralWidget().layout().activate()
        
    def on_realtime_toggled(self, checked):
        if checked and hasattr(self, 'chk_accumulate') and self.chk_accumulate.isChecked():
            self.chk_accumulate.blockSignals(True)
            self.chk_accumulate.setChecked(False)
            self.chk_accumulate.blockSignals(False)
            self.accumulate_enabled = False
            self.last_curve_update_idx.clear()
            if hasattr(self, 'timer'):
                self.timer.setInterval(100)
        self.save_ui_settings()
        if checked:
            for pw in self.plot_widgets.values():
                pw.getViewBox().enableAutoRange(axis=pg.ViewBox.YAxis)

    def on_accumulate_toggled(self, checked):
        self.accumulate_enabled = bool(checked)
        if hasattr(self, 'chk_accumulate'):
            self.chk_accumulate.setText("累积趋势" if checked else "累积趋势")
        self.last_curve_update_idx.clear()
        if hasattr(self, 'timer'):
            self.timer.setInterval(250 if checked else 100)
        if checked:
            if hasattr(self, 'chk_autoscroll') and self.chk_autoscroll.isChecked():
                self.chk_autoscroll.blockSignals(True)
                self.chk_autoscroll.setChecked(False)
                self.chk_autoscroll.blockSignals(False)
            self.trend_bucket_start = None
            self.trend_bucket_end = None
            self.trend_bucket_values = {}
            self.trend_bucket_last_values = {}
        else:
            self.flush_trend_bucket()
            self.trend_times = []
            self.trend_store = {tag: [] for tag in self.ordered_tags}
            self.trend_bucket_start = None
            self.trend_bucket_end = None
            self.trend_bucket_values = {}
            self.trend_bucket_last_values = {}
        self.save_ui_settings()

    def get_plotted_tags(self):
        tags = set()
        for tag, dock_map in self.curves.items():
            if dock_map:
                tags.add(tag)
        return tags

    def trim_accumulate_buffers(self):
        if len(self.trend_times) <= self.accumulate_hard_limit:
            return
        overflow = len(self.trend_times) - self.accumulate_hard_limit
        if overflow <= 0:
            return
        del self.trend_times[:overflow]
        for tag in self.trend_store:
            del self.trend_store[tag][:overflow]

    def flush_trend_bucket(self):
        if self.trend_bucket_start is None or self.trend_bucket_end is None:
            return
        if not self.trend_bucket_values:
            return

        bucket_time = self.trend_bucket_end
        self.trend_times.append(bucket_time)
        active_tags = self.get_plotted_tags() or set(self.ordered_tags[:min(len(self.ordered_tags), 80)])
        for tag in active_tags:
            self.trend_store.setdefault(tag, [])
            values = self.trend_bucket_values.get(tag, [])
            if values:
                self.trend_store[tag].append(float(values[-1]))
            else:
                self.trend_store[tag].append(self.trend_bucket_last_values.get(tag, np.nan))
        target_len = len(self.trend_times)
        for tag in list(self.trend_store.keys()):
            if tag not in active_tags:
                self.trend_store[tag] = []
            elif len(self.trend_store[tag]) < target_len:
                self.trend_store[tag].extend([np.nan] * (target_len - len(self.trend_store[tag])))

        self.trend_bucket_start = None
        self.trend_bucket_end = None
        self.trend_bucket_values = {}
        self.trim_accumulate_buffers()

    def append_trend_sample(self, t, var_map):
        if self.trend_bucket_start is None:
            self.trend_bucket_start = t
            self.trend_bucket_end = t
            self.trend_bucket_values = {}
        elif (t - self.trend_bucket_start) >= self.accumulate_bucket_seconds:
            self.flush_trend_bucket()
            self.trend_bucket_start = t
            self.trend_bucket_end = t
            self.trend_bucket_values = {}
        else:
            self.trend_bucket_end = t

        active_tags = self.get_plotted_tags()
        if not active_tags:
            return
        for tag in active_tags:
            if tag in var_map:
                value = var_map[tag]
                self.trend_bucket_values.setdefault(tag, []).append(value)
                self.trend_bucket_last_values[tag] = value

    def sanitize_active_series(self, t_data, y_data):
        t_arr = np.asarray(t_data, dtype=float)
        if t_arr.size == 0:
            return np.asarray([], dtype=float), {tag: np.asarray([], dtype=float) for tag in y_data}

        min_len = min([t_arr.size] + [len(values) for values in y_data.values()]) if y_data else t_arr.size
        t_arr = t_arr[:min_len]
        y_arrs = {tag: np.asarray(values, dtype=float)[:min_len] for tag, values in y_data.items()}
        finite_time = np.isfinite(t_arr)
        if not finite_time.any():
            return np.asarray([], dtype=float), {tag: np.asarray([], dtype=float) for tag in y_data}

        t_arr = t_arr[finite_time]
        y_arrs = {tag: values[finite_time] for tag, values in y_arrs.items()}

        # If simulation time restarts, keep only the newest monotonic segment.
        if t_arr.size > 1:
            reset_steps = np.where(np.diff(t_arr) < -1e-9)[0]
            if reset_steps.size:
                start = int(reset_steps[-1]) + 1
                t_arr = t_arr[start:]
                y_arrs = {tag: values[start:] for tag, values in y_arrs.items()}

        if t_arr.size > 1:
            keep = np.concatenate(([True], np.diff(t_arr) > 1e-9))
            t_arr = t_arr[keep]
            y_arrs = {tag: values[keep] for tag, values in y_arrs.items()}

        return t_arr, y_arrs

    def get_active_series(self, active_tags=None):
        if active_tags is None:
            active_tags = list(self.data_store.keys())
        else:
            active_tags = [tag for tag in active_tags if tag in self.data_store]
        if self.accumulate_enabled and self.trend_times:
            self.flush_trend_bucket()
            t_data = np.asarray(self.trend_times, dtype=float)
            return self.sanitize_active_series(t_data, {tag: self.trend_store.get(tag, []) for tag in active_tags})

        valid_len = min(self.current_idx, self.max_points)
        wrapped_idx = None
        if self.current_idx > self.max_points:
            wrapped_idx = self.current_idx % self.max_points
            t_data = np.concatenate((self.times[wrapped_idx:], self.times[:wrapped_idx]))
        else:
            t_data = self.times[:valid_len]

        y_data = {}
        for tag in active_tags:
            if wrapped_idx is not None:
                y_data[tag] = np.concatenate((self.data_store[tag][wrapped_idx:], self.data_store[tag][:wrapped_idx]))
            else:
                y_data[tag] = self.data_store[tag][:valid_len]
        return self.sanitize_active_series(t_data, y_data)

    def build_realtime_plot_data(self, x_data, y_data, max_points):
        x_arr = np.asarray(x_data, dtype=float)
        y_arr = np.asarray(y_data, dtype=float)
        finite_mask = np.isfinite(x_arr) & np.isfinite(y_arr)
        if not finite_mask.any():
            return np.asarray([], dtype=float), np.asarray([], dtype=float)

        x_arr = x_arr[finite_mask]
        y_arr = y_arr[finite_mask]
        total = len(x_arr)
        target = max(16, int(max_points))
        if total <= target:
            return x_arr, y_arr

        sampled_idx = np.linspace(0, total - 1, target, dtype=int)
        sampled_idx = np.asarray(sorted(set(sampled_idx.tolist() + [total - 1])), dtype=int)
        return x_arr[sampled_idx], y_arr[sampled_idx]

    def build_trend_plot_data(self, x_data, y_data, max_points):
        x_arr = np.asarray(x_data, dtype=float)
        y_arr = np.asarray(y_data, dtype=float)
        finite_mask = np.isfinite(x_arr) & np.isfinite(y_arr)
        if not finite_mask.any():
            return np.asarray([], dtype=float), np.asarray([], dtype=float)

        x_arr = x_arr[finite_mask]
        y_arr = y_arr[finite_mask]
        total = len(x_arr)
        if total <= max_points:
            return x_arr, y_arr

        target = max(8, int(max_points))
        bucket_count = max(1, (target - 2) // 4)
        edges = np.linspace(1, total - 1, bucket_count + 1, dtype=int)
        sampled_idx = [0]

        for i in range(bucket_count):
            start = int(edges[i])
            end = int(edges[i + 1])
            if end <= start:
                continue

            segment = y_arr[start:end]
            if segment.size == 0:
                continue

            local_min = start + int(np.argmin(segment))
            local_max = start + int(np.argmax(segment))
            candidates = sorted({start, local_min, local_max, end - 1})
            sampled_idx.extend(candidates)

        sampled_idx.append(total - 1)
        sampled_idx = np.asarray(sorted(set(idx for idx in sampled_idx if 0 <= idx < total)), dtype=int)

        if sampled_idx.size > target:
            keep = np.linspace(0, sampled_idx.size - 1, target, dtype=int)
            sampled_idx = sampled_idx[keep]
            sampled_idx = np.asarray(sorted(set(sampled_idx.tolist() + [0, total - 1])), dtype=int)

        return x_arr[sampled_idx], y_arr[sampled_idx]
            
    def get_display_name(self, tag):
        desc = self.vars_desc.get(tag, "")
        mode = self.name_mode_combo.currentIndex()
        if mode == 0 or not desc:
            return tag
        elif mode == 1:
            return desc
        else:
            return f"{tag} ({desc})"

    def update_all_labels(self):
        for i, tag in enumerate(self.ordered_tags):
            self.table.item(i, 1).setText(self.get_display_name(tag))
            
        self.save_ui_settings()
        title_size = self.title_size_spin.value()
        for dock_name, dock in self.docks.items():
            if dock and hasattr(dock, 'title_bar_widget'):
                dock.title_bar_widget.setTitle(dock_name)
                dock.title_bar_widget.setTitleSize(title_size)
                dock.title_bar_widget.updateGeometry()
                dock.title_bar_widget.update()
            elif dock and isinstance(dock, QDockWidget) and dock.titleBarWidget() is not None:
                dock.titleBarWidget().setTitleSize(title_size)
                dock.titleBarWidget().updateGeometry()
                dock.titleBarWidget().update()
        for dock_name, pw in self.plot_widgets.items():
            if pw.plotItem.legend is not None:
                pw.plotItem.legend.clear()
                for tag in self.curves:
                    if dock_name in self.curves[tag]:
                        pw.plotItem.legend.addItem(self.curves[tag][dock_name], self.get_display_name(tag))

    def set_active_dock(self, name):
        if name in self.docks:
            self.active_dock_name = name
            self.lbl_active_dock.setText(name)
            # 当切换窗口时，同步刷新左侧变量勾选状态
            self.refresh_table_checkboxes()
            for dock_name, dock in self.docks.items():
                try:
                    if hasattr(dock, 'label'):
                        dock.label.update()
                except Exception:
                    pass

    def refresh_table_checkboxes(self):
        """根据当前激活的 Dock，刷新左侧表格的勾选状态"""
        if not hasattr(self, 'active_dock_name') or not self.active_dock_name:
            return
        
        dock_name = self.active_dock_name
        self.table.blockSignals(True)
        for i, tag in enumerate(self.ordered_tags):
            # 检查该变量是否在当前激活的 Dock 中绘制
            item = self.table.item(i, 0)
            if item:
                is_active = (tag in self.curves and dock_name in self.curves[tag])
                item.setCheckState(Qt.Checked if is_active else Qt.Unchecked)
        self.table.blockSignals(False)

    def show_table_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item: return
        row = item.row()
        tag = self.table.item(row, 1).text()
        
        menu = QMenu(self)
        action_color = menu.addAction("🎨 修改线条颜色")
        action_width = menu.addAction("📏 修改线条粗细")
        
        action = menu.exec_(self.table.viewport().mapToGlobal(pos)) if QT_VERSION == 5 else menu.exec(self.table.viewport().mapToGlobal(pos))
        
        if action == action_color:
            color = QColorDialog.getColor(self.var_styles[tag]["color"], self, "选择颜色")
            if color.isValid():
                self.var_styles[tag]["color"] = color
                self.update_curve_styles(tag)
        elif action == action_width:
            width, ok = QInputDialog.getInt(self, "线条粗细", "输入线条粗细 (1-10):", self.var_styles[tag]["width"], 1, 10, 1)
            if ok:
                self.var_styles[tag]["width"] = width
                self.update_curve_styles(tag)

    def update_curve_styles(self, tag):
        if tag in self.curves:
            style = self.var_styles[tag]
            for dock_name, curveItem in self.curves[tag].items():
                curveItem.setPen(self.make_curve_pen(style))

    def export_charts_to_word(self):
        if not self.plot_widgets:
            QMessageBox.information(self, "导出 Word", "当前没有可导出的图表窗口。")
            return

        default_name = datetime.datetime.now().strftime("FmuSolver_Charts_%Y%m%d_%H%M%S.docx")
        out_path = QFileDialog.getSaveFileName(self, "导出图表到 Word", os.path.join(APP_DIR, default_name), "Word Document (*.docx)")[0]
        if not out_path:
            return
        if not out_path.lower().endswith(".docx"):
            out_path += ".docx"

        try:
            from docx import Document
            from docx.shared import Inches
        except Exception as e:
            QMessageBox.critical(self, "导出 Word", f"缺少 python-docx 组件，无法导出 Word: {e}")
            return

        export_dir = os.path.join(APP_DIR, "chart_exports")
        os.makedirs(export_dir, exist_ok=True)

        doc = Document()
        doc.add_heading("FmuSolver 看板图表导出", 0)
        doc.add_paragraph(datetime.datetime.now().strftime("导出时间: %Y-%m-%d %H:%M:%S"))

        exported = 0
        for dock_name in self.dock_order:
            pw = self.plot_widgets.get(dock_name)
            if pw is None or not pw.isVisible():
                continue

            doc.add_heading(str(dock_name), level=1)
            curve_names = [tag for tag, dock_map in self.curves.items() if dock_name in dock_map]
            if curve_names:
                doc.add_paragraph("曲线: " + ", ".join(self.get_display_name(tag) for tag in curve_names))
                latest_lines = []
                for tag in curve_names:
                    if tag in self.latest_values:
                        latest_lines.append(f"{self.get_display_name(tag)} = {self.latest_values[tag]:.6g}")
                if latest_lines:
                    doc.add_paragraph("最新值: " + "; ".join(latest_lines))

            QApplication.processEvents()
            image_path = os.path.join(export_dir, f"chart_{exported + 1}.png")
            pixmap = pw.grab()
            pixmap.save(image_path, "PNG")
            doc.add_picture(image_path, width=Inches(6.7))
            exported += 1

        if exported == 0:
            QMessageBox.information(self, "导出 Word", "当前没有可见图表可导出。")
            return

        doc.save(out_path)
        QMessageBox.information(self, "导出 Word", f"已导出 {exported} 个图表到:\n{out_path}")

    def update_dock_y_range(self, dock_name, view_box, y_arrays):
        finite_chunks = []
        for arr in y_arrays:
            if arr is None:
                continue
            arr = np.asarray(arr, dtype=float)
            arr = arr[np.isfinite(arr)]
            if arr.size:
                finite_chunks.append(arr)

        if not finite_chunks:
            return

        y_min = min(float(arr.min()) for arr in finite_chunks)
        y_max = max(float(arr.max()) for arr in finite_chunks)
        if not np.isfinite(y_min) or not np.isfinite(y_max):
            return

        span = y_max - y_min
        pad = max(0.08, abs(y_max) * 0.02, abs(y_min) * 0.02) if span <= 1e-9 else max(0.05, span * 0.08)
        target_min = y_min - pad
        target_max = y_max + pad

        last_range = self.last_y_range.get(dock_name)
        if last_range is None:
            view_box.setYRange(target_min, target_max, padding=0.0)
            self.last_y_range[dock_name] = (target_min, target_max)
            return

        last_min, last_max = last_range
        last_span = max(1e-9, last_max - last_min)
        target_span = max(1e-9, target_max - target_min)
        changed = (
            target_min < last_min or
            target_max > last_max or
            abs(target_min - last_min) > last_span * 0.12 or
            abs(target_max - last_max) > last_span * 0.12 or
            abs(target_span - last_span) > last_span * 0.18
        )
        if changed:
            view_box.setYRange(target_min, target_max, padding=0.0)
            self.last_y_range[dock_name] = (target_min, target_max)

    def get_preferred_dock_placement(self, name):
        existing = [dock_name for dock_name in self.dock_order if dock_name in self.docks and dock_name != name]
        if not existing:
            return Qt.LeftDockWidgetArea, None, Qt.Horizontal
        if len(existing) == 1:
            return Qt.RightDockWidgetArea, existing[0], Qt.Horizontal
        if len(existing) == 2:
            return Qt.BottomDockWidgetArea, existing[0], Qt.Vertical
        return Qt.RightDockWidgetArea, existing[-1], Qt.Horizontal

    def normalize_dock_sizes(self):
        visible_docks = [
            self.docks[name] for name in self.dock_order
            if name in self.docks and self.docks[name].isVisible()
        ]
        if not visible_docks:
            return

        if len(visible_docks) == 1:
            horizontal_sizes = [max(420, self.dock_host.width())]
            vertical_sizes = [max(320, self.dock_host.height())]
        else:
            columns = min(2, len(visible_docks))
            rows = (len(visible_docks) + columns - 1) // columns
            horizontal_sizes = [max(320, int(self.dock_host.width() / columns))] * len(visible_docks)
            vertical_sizes = [max(240, int(self.dock_host.height() / rows))] * len(visible_docks)
        try:
            self.dock_host.resizeDocks(visible_docks, horizontal_sizes, Qt.Horizontal)
            self.dock_host.resizeDocks(visible_docks, vertical_sizes, Qt.Vertical)
        except Exception:
            pass

    def create_new_dock(self):
        name, ok = QInputDialog.getText(self, "新建看图组", "请输入分组名称:")
        if ok and name:
            self.create_dock_internal(name)
            self.set_active_dock(name)
            self.remember_last_session()

    def apply_dock_theme(self, dock):
        if dock is None:
            return
        try:
            dock.setStyleSheet(getattr(self, 'dock_theme_qss', ''))
            if hasattr(dock, 'title_bar_widget') and dock.title_bar_widget is not None:
                dock.title_bar_widget.setStyleSheet(getattr(self, 'dock_theme_qss', ''))
                dock.title_bar_widget.setAttribute(Qt.WA_StyledBackground, True)
                dock.title_bar_widget.update()
            dock.update()
        except Exception:
            pass

    def on_dock_top_level_changed(self, name):
        dock = self.docks.get(name)
        self.apply_dock_theme(dock)
        self.set_active_dock(name)

    def create_dock_internal(self, name, position=None):
        if name in self.docks: return
        self.pause_session_memory()
        dock = PlotDockWidget(name, name, self.dock_host)
        dock.setObjectName(f"Dock_{name}")
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        dock.setMinimumSize(320, 240)
        dock.title_bar_widget = DockTitleBar(name, dock)
        dock.setTitleBarWidget(dock.title_bar_widget)
        dock.title_bar_widget.setTitleSize(self.title_size_spin.value())
        self.apply_dock_theme(dock)
            
        time_axis = TimeAxisItem(self, orientation='bottom')
        time_axis.setHeight(50) # 预留更多空间给两行时间
        view_box = PlotViewBox(self)
        plot_widget = pg.PlotWidget(viewBox=view_box, axisItems={'bottom': time_axis})
        # 彻底移除 PlotWidget 内部标题，防止双重显示
        plot_widget.getPlotItem().setTitle(None)
        plot_widget.setMinimumSize(280, 200)

        bg = getattr(self, 'plot_bg', "#FFFFFF")
        plot_widget.setBackground(bg)
        plot_widget.showGrid(x=True, y=True, alpha=0.1)
        plot_widget.setClipToView(True)
        plot_widget.setDownsampling(auto=False)
        plot_widget.addLegend()
        for axis_name in ('left', 'bottom'):
            axis = plot_widget.getPlotItem().getAxis(axis_name)
            if hasattr(self, 'plot_axis_text'):
                axis.setTextPen(self.plot_axis_text)
            if hasattr(self, 'plot_axis_pen'):
                axis.setPen(self.plot_axis_pen)
        if plot_widget.plotItem.legend is not None and hasattr(self, 'plot_axis_text'):
            plot_widget.plotItem.legend.setLabelTextColor(self.plot_axis_text)
        plot_widget.setContentsMargins(5, 5, 5, 10)
        plot_widget.getPlotItem().getViewBox().setMouseMode(pg.ViewBox.RectMode)
        plot_widget.getPlotItem().getViewBox().setDefaultPadding(0.02)
        plot_widget.getPlotItem().getViewBox().disableAutoRange()
        plot_widget.getPlotItem().hideButtons()
        plot_widget.getPlotItem().setMenuEnabled(False)
        plot_widget.getPlotItem().getAxis('left').setWidth(72)
        plot_widget.getPlotItem().getAxis('bottom').setStyle(tickTextOffset=8)
        
        # 十字光标功能 (CursorLine & CursorLabel)
        vLine = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#f59e0b', width=1, style=Qt.DashLine))
        label = pg.TextItem(text="", color=getattr(self, 'plot_axis_text', QColor('white')), fill=getattr(self, 'plot_label_fill', pg.mkBrush(0,0,0,150)), border=getattr(self, 'plot_label_border', None))
        plot_widget.addItem(vLine, ignoreBounds=True)
        plot_widget.addItem(label, ignoreBounds=True)
        vLine.setVisible(False)
        label.setVisible(False)
        
        # 鼠标移动事件处理
        def mouseMoved(evt):
            pos = evt
            if plot_widget.sceneBoundingRect().contains(pos):
                mousePoint = plot_widget.plotItem.vb.mapSceneToView(pos)
                # Use the same sanitized series as the renderer to avoid cursor drift after wraparound.
                t_array, y_store = self.get_active_series()
                    
                if len(t_array) > 0:
                    index = (np.abs(t_array - mousePoint.x())).argmin()
                    if index >= 0:
                        vLine.setPos(mousePoint.x())
                        vLine.setVisible(True)
                        
                        if self.base_datetime is not None:
                            dt = self.base_datetime + datetime.timedelta(seconds=(t_array[index] - self.base_sim_time))
                            text = f"时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        else:
                            text = f"时间: {t_array[index]:.2f}s\n"
                        
                        has_data = False
                        for tag in self.curves:
                            if name in self.curves[tag]:
                                y_array = y_store.get(tag)
                                if y_array is None or index >= len(y_array) or not np.isfinite(y_array[index]):
                                    continue
                                val = y_array[index]
                                text += f"{self.get_display_name(tag)}: {val:.4f}\n"
                                has_data = True
                        
                        if has_data:
                            label.setText(text)
                            label.setPos(mousePoint.x(), mousePoint.y())
                            label.setVisible(True)
                        else:
                            label.setVisible(False)
            else:
                vLine.setVisible(False)
                label.setVisible(False)

        plot_widget.scene().sigMouseMoved.connect(mouseMoved)
        
        # 增加鼠标离开自动隐藏逻辑 (EventFilter 方案)
        class LeaveFilter(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Leave:
                    vLine.setVisible(False)
                    label.setVisible(False)
                return False
        
        self.leave_filter = LeaveFilter(self)
        plot_widget.installEventFilter(self.leave_filter)
        
        # 用户手动拖拽或缩放时，自动取消画面跟随
        plot_widget.getViewBox().sigRangeChangedManually.connect(lambda: self.chk_autoscroll.setChecked(False))
        
        # 点击激活窗口机制
        def mouseClicked(evt):
            self.set_active_dock(name)
        plot_widget.scene().sigMouseClicked.connect(mouseClicked)
        
        dock.setWidget(plot_widget)
        self.docks[name] = dock
        self.plot_widgets[name] = plot_widget
        self.crosshairs[name] = (vLine, label)
        if name not in self.dock_order:
            self.dock_order.append(name)
        self.save_ui_settings()

        dock.closed.connect(self.on_dock_closed)
        dock.topLevelChanged.connect(lambda _floating, dock_name=name: self.on_dock_top_level_changed(dock_name))

        area, target_name, orientation = self.get_preferred_dock_placement(name)
        if target_name and target_name in self.docks and isinstance(self.docks[target_name], QDockWidget):
            self.dock_host.addDockWidget(area, dock)
            self.dock_host.splitDockWidget(self.docks[target_name], dock, orientation)
        else:
            self.dock_host.addDockWidget(area, dock)

        dock.show()
        dock.raise_()
        self.dock_host.repaint()
        QTimer.singleShot(0, self.normalize_dock_sizes)
        QTimer.singleShot(50, self.normalize_dock_sizes)
        QTimer.singleShot(50, lambda: self.set_active_dock(name))
        self.schedule_session_memory_resume(delay=180, save_after=True)
        
        # 如果是第一个窗口，自动激活
        if not hasattr(self, 'active_dock_name') or not self.active_dock_name:
            self.set_active_dock(name)

    def on_dock_closed(self, name):
        if name not in self.docks:
            return
        # 清理对应的曲线
        for tag in list(self.curves.keys()):
            if name in self.curves[tag]:
                del self.curves[tag][name]
        del self.plot_widgets[name]
        del self.docks[name]
        del self.crosshairs[name]
        self.dock_order = [dock_name for dock_name in self.dock_order if dock_name != name]
        
        if hasattr(self, 'active_dock_name') and self.active_dock_name == name:
            self.active_dock_name = None
            self.lbl_active_dock.setText("未选中窗口")
            if len(self.plot_widgets) > 0:
                self.set_active_dock(list(self.plot_widgets.keys())[0])
        self.save_ui_settings()
        self.remember_last_session()

    def toggle_curve_in_active_dock(self, tag, state):
        if not hasattr(self, 'active_dock_name') or self.active_dock_name not in self.plot_widgets:
            if len(self.plot_widgets) > 0:
                self.active_dock_name = list(self.plot_widgets.keys())[0]
            else:
                return # 无可用看图组
                
        dock_name = self.active_dock_name
        pw = self.plot_widgets[dock_name]
        
        if tag not in self.curves:
            self.curves[tag] = {}
            
        if state == Qt.Checked or state == 2: # Qt5 is 2, PyQt6 is Qt.CheckState.Checked
            if dock_name not in self.curves[tag]:
                style = self.var_styles[tag]
                curve = pw.plot(
                    pen=self.make_curve_pen(style),
                    name=self.get_display_name(tag),
                    autoDownsample=False,
                    skipFiniteCheck=True,
                    connect='finite',
                    antialias=True,
                )
                self.curves[tag][dock_name] = curve
        else:
            if dock_name in self.curves[tag]:
                pw.removeItem(self.curves[tag][dock_name])
                del self.curves[tag][dock_name]
        self.remember_last_session()

    def setup_network(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind(('0.0.0.0', self.port))
            print(f"Listening on {self.port}")
        except Exception as e:
            print(f"Bind error: {e}")
            
        self.running = True
        self.thread = threading.Thread(target=self.receive_loop, daemon=True)
        self.thread.start()
        self.data_received.connect(self.process_data)

    def receive_loop(self):
        while self.running:
            try:
                data, _ = self.sock.recvfrom(65535)
                decoded = base64.b64decode(data)
                pb_data = ddm_pb2.DDMData()
                pb_data.ParseFromString(decoded)
                self.rx_packet_count += 1
                self.rx_var_count_total += len(pb_data.sim_vars)
                try:
                    self.packet_queue.put_nowait(pb_data)
                except queue.Full:
                    self.rx_drop_count += 1
                    try:
                        self.packet_queue.get_nowait()
                    except Exception:
                        pass
                    try:
                        self.packet_queue.put_nowait(pb_data)
                    except Exception:
                        pass
            except Exception:
                self.rx_error_count += 1

    def drain_packet_queue(self):
        processed = 0
        while processed < self.max_packets_per_ui_tick:
            try:
                pb_data = self.packet_queue.get_nowait()
            except queue.Empty:
                break
            self.process_data(pb_data)
            processed += 1
        return processed

    def write_perf_log(self, ui_elapsed_ms=0.0):
        now = time.time()
        if now - self.last_perf_log_wall < 5.0:
            return
        pending = self.packet_queue.qsize()
        avg_rx_vars = self.rx_var_count_total / max(1, self.rx_packet_count)
        avg_proc_vars = self.process_var_count_total / max(1, self.process_packet_count)
        line = (
            f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [PERF][VIZ] "
            f"rx={self.rx_packet_count} rx_err={self.rx_error_count} rx_drop={self.rx_drop_count} processed={self.process_packet_count} "
            f"queue={pending}/{self.packet_queue.maxsize} avg_rx_vars={avg_rx_vars:.1f} avg_proc_vars={avg_proc_vars:.1f} "
            f"ui_ticks={self.ui_tick_count} curve_updates={self.ui_curve_updates} skipped_docks={self.ui_skipped_docks} "
            f"last_ui_ms={ui_elapsed_ms:.2f} docks={len(self.plot_widgets)} vars={len(self.data_store)} idx={self.current_idx}\n"
        )
        try:
            with open(self.perf_log_file, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass
        self.last_perf_log_wall = now

    def get_process_memory_mb(self):
        if sys.platform != 'win32':
            return 0.0
        try:
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong),
                    ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t),
                ]
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            psapi = ctypes.WinDLL('psapi')
            if psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                return counters.WorkingSetSize / (1024 * 1024)
        except Exception:
            return 0.0
        return 0.0

    def memory_guard(self):
        now = time.time()
        if now - self.last_memory_guard_wall < 10.0:
            return
        self.last_memory_guard_wall = now
        mem_mb = self.get_process_memory_mb()
        if not mem_mb or mem_mb < self.memory_soft_limit_mb:
            return
        self.realtime_max_render_points = max(300, int(self.realtime_max_render_points * 0.75))
        self.accumulate_max_render_points = max(300, int(self.accumulate_max_render_points * 0.75))
        self.max_packets_per_ui_tick = 1
        while self.packet_queue.qsize() > 2:
            try:
                self.packet_queue.get_nowait()
                self.rx_drop_count += 1
            except Exception:
                break
        if len(self.trend_times) > max(1000, self.accumulate_hard_limit // 2):
            keep = max(1000, self.accumulate_hard_limit // 2)
            overflow = len(self.trend_times) - keep
            del self.trend_times[:overflow]
            for tag in self.trend_store:
                del self.trend_store[tag][:overflow]
        gc.collect()
        try:
            with open(self.perf_log_file, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [WARN][VIZ] Memory guard activated: working_set={mem_mb:.1f}MB realtime_points={self.realtime_max_render_points} trend_points={self.accumulate_max_render_points}\n")
        except Exception:
            pass

    def process_data(self, pb_data):
        t = pb_data.sim_time
        self.process_packet_count += 1
        self.process_var_count_total += len(pb_data.sim_vars)
        
        # 环形写入
        idx = self.current_idx % self.max_points
        self.times[idx] = t
        
        var_map = {}
        for v in pb_data.sim_vars:
            try:
                if v.type == ddm_pb2.DDMData.SimVar.Type.Value("Bool"):
                    var_map[v.name] = 1.0 if v.bool_value else 0.0
                elif v.type == ddm_pb2.DDMData.SimVar.Type.Value("Int"):
                    var_map[v.name] = float(v.int_value)
                elif v.type == ddm_pb2.DDMData.SimVar.Type.Value("String"):
                    try:
                        var_map[v.name] = float(v.string_value)
                    except Exception:
                        continue
                else:
                    var_map[v.name] = float(v.double_value)
            except Exception:
                continue
        if self.accumulate_enabled:
            self.append_trend_sample(t, var_map)
        
        # 解析绝对时间基准
        if self.base_datetime is None and 'Year' in var_map:
            try:
                y, m, d = int(var_map['Year']), int(var_map['Mon']), int(var_map['Day'])
                h, minute, s = int(var_map['Hour']), int(var_map['Min']), int(var_map['Sec'])
                if y > 1900:
                    self.base_sim_time = t
                    self.base_datetime = datetime.datetime(y, m, d, h, minute, s)
            except: pass

        for name in var_map:
            if name not in self.data_store:
                self.register_runtime_variable(name)

        for name in self.data_store:
            if name in var_map:
                val = var_map[name]
                self.data_store[name][idx] = val
                self.latest_values[name] = val
                
        self.current_idx += 1

    def update_ui(self):
        ui_start = time.perf_counter()
        self.drain_packet_queue()
        if self.current_idx == 0:
            self.write_perf_log(0.0)
            return
        if self.current_idx == self.last_ui_idx:
            self.write_perf_log(0.0)
            return
        self.last_ui_idx = self.current_idx
        self.ui_tick_count += 1
        
        # 1. 极致性能优化：仅更新数值发生变化的表格单元格 (Dirty Check)
        for i in range(self.table.rowCount()):
            tag = self.ordered_tags[i]
            if tag in self.latest_values:
                val_str = f"{self.latest_values[tag]:.4f}"
                if self.last_displayed_strs.get(tag) != val_str:
                    self.table.item(i, 2).setText(val_str)
                    self.last_displayed_strs[tag] = val_str
                
        updated_docks = 0
        dock_names = list(self.plot_widgets.keys())
        dock_count = len(dock_names)
        if dock_count == 0:
            self.write_perf_log((time.perf_counter() - ui_start) * 1000.0)
            return
        visible_dock_curves = {}
        active_tags = set()
        for dock_name in dock_names:
            pw = self.plot_widgets.get(dock_name)
            if pw is None or not pw.isVisible():
                continue
            dock_curves = [tag for tag, dock_map in self.curves.items() if dock_name in dock_map and tag in self.data_store]
            if dock_curves:
                visible_dock_curves[dock_name] = dock_curves
                active_tags.update(dock_curves)
        if not active_tags:
            self.write_perf_log((time.perf_counter() - ui_start) * 1000.0)
            return

        # 2. 更新图表曲线，只准备当前可见曲线的数据，避免全量变量产生大量临时数组。
        t_data, y_store = self.get_active_series(active_tags)
        if len(t_data) == 0:
            self.write_perf_log((time.perf_counter() - ui_start) * 1000.0)
            return
        latest_time = t_data[-1]
        start_offset = self.current_idx % dock_count

        for dock_index in range(dock_count):
            dock_name = dock_names[(start_offset + dock_index) % dock_count]
            pw = self.plot_widgets.get(dock_name)
            if pw is None:
                continue
            if not pw.isVisible():
                continue
            vb = pw.getViewBox()
            dock_curves = visible_dock_curves.get(dock_name, [])
            if not dock_curves:
                continue

            if not self.accumulate_enabled and updated_docks >= self.max_dock_updates_per_tick:
                self.ui_skipped_docks += 1
                continue

            if self.accumulate_enabled and (self.current_idx % self.accumulate_update_stride) != 0:
                self.ui_skipped_docks += 1
                continue
            
            # 1. 工业级滚动引擎：维持固定视口宽度
            if self.chk_autoscroll.isChecked() and not self.accumulate_enabled:
                window_width = float(self.span_spin.value())
                target_min = max(0, latest_time - window_width)
                last_min, last_max = self.last_view_update.get(dock_name, (None, None))
                update_threshold = max(0.015, window_width * 0.0025)
                if last_min is None or abs(target_min - last_min) >= update_threshold or abs(latest_time - (last_max or 0)) >= update_threshold:
                    vb.setXRange(target_min, latest_time, padding=0.01)
                    self.last_view_update[dock_name] = (target_min, latest_time)
            elif self.accumulate_enabled:
                if len(t_data) > 1:
                    left = float(t_data[0])
                    right = float(t_data[-1])
                    last_min, last_max = self.last_view_update.get(dock_name, (None, None))
                    if last_min is None or abs(left - last_min) >= 0.05 or abs(right - (last_max or 0)) >= 0.05:
                        vb.setXRange(left, right, padding=0.01)
                        self.last_view_update[dock_name] = (left, right)
                
            # 2. 获取当前的 X 轴实际可视范围
            x_min, x_max = vb.viewRange()[0]

            # 3. 视口数据剔除
            start_idx = np.searchsorted(t_data, x_min)
            end_idx = np.searchsorted(t_data, x_max, side='right')
            start_idx = max(0, int(start_idx) - 1)
            end_idx = min(len(t_data), int(end_idx) + 1)

            t_slice = t_data[start_idx:end_idx]
            t_plot = t_slice
            if len(t_plot) == 0:
                continue
            rendered_y_arrays = []
            
            for tag in dock_curves:
                if tag not in self.data_store:
                    continue

                update_key = (dock_name, tag)
                if self.chk_autoscroll.isChecked() and not self.accumulate_enabled and self.last_curve_update_idx.get(update_key) == self.current_idx:
                    continue

                y_full = y_store.get(tag)
                if y_full is None or len(y_full) == 0:
                    continue

                y_slice = y_full[start_idx:end_idx]
                if self.accumulate_enabled:
                    t_plot_render, y_plot = self.build_trend_plot_data(t_slice, y_slice, self.accumulate_max_render_points)
                    if len(t_plot_render) == 0 or len(y_plot) == 0:
                        continue
                    self.curves[tag][dock_name].setData(x=t_plot_render, y=y_plot, connect='finite')
                    rendered_y_arrays.append(y_plot)
                else:
                    t_plot_render, y_plot = self.build_realtime_plot_data(t_slice, y_slice, self.realtime_max_render_points)
                    if len(t_plot_render) == 0 or len(y_plot) == 0:
                        continue
                    self.curves[tag][dock_name].setData(x=t_plot_render, y=y_plot, connect='finite')
                    rendered_y_arrays.append(y_plot)
                self.last_curve_update_idx[update_key] = self.current_idx

            self.update_dock_y_range(dock_name, vb, rendered_y_arrays)
            if rendered_y_arrays:
                updated_docks += 1
                self.ui_curve_updates += len(rendered_y_arrays)

        self.write_perf_log((time.perf_counter() - ui_start) * 1000.0)
        if time.time() - self.last_gc_wall > 30.0:
            gc.collect()
            self.last_gc_wall = time.time()
        self.memory_guard()

if __name__ == "__main__":
    # 强制单实例运行 (DataVisualizer)
    mutex_name = "Local\\FmuSolver_DataVisualizer_Mutex"
    import ctypes
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    if kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
        hwnd = ctypes.windll.user32.FindWindowW(None, "FmuSolver - Data Visualizer")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 5) # SW_SHOW
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        sys.exit(0)

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=22345)
    args = parser.parse_args()
    
    try:
        app = QApplication(sys.argv)
        window = ProfessionalVisualizer(port=args.port)
        window.show()
        sys.exit(app.exec_() if QT_VERSION == 5 else app.exec())
    except Exception:
        try:
            with open(os.path.join(APP_DIR, "visualizer_fatal.log"), "a", encoding="utf-8") as f:
                f.write(f"\n--- Visualizer Fatal {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                f.write(traceback.format_exc())
        except Exception:
            pass
        raise
