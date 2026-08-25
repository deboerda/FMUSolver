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
                                 QLabel, QFrame, QSplitter, QPushButton, QCheckBox, QInputDialog, QMenu, QColorDialog, QGraphicsTextItem, QGraphicsRectItem,
                                 QSpinBox, QComboBox, QGridLayout, QSizeGrip, QListView, QListWidget, QDockWidget, QFileDialog, QMessageBox, QLineEdit)
    from PySide6.QtCore import Qt, QTimer, Signal, QFileSystemWatcher, QPoint, QEvent, QObject, QRect, QSize, QByteArray
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtGui import QColor, QFont, QPalette, QCursor, QIcon, QPainter, QPainterPath, QPen, QBrush
    QT_VERSION = 6
except ImportError:
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                               QWidget, QHeaderView, QTableWidget, QTableWidgetItem, 
                               QLabel, QFrame, QSplitter, QPushButton, QCheckBox, QInputDialog, QMenu, QColorDialog, QGraphicsTextItem, QGraphicsRectItem,
                               QSpinBox, QComboBox, QGridLayout, QListView, QListWidget, QDockWidget, QFileDialog, QMessageBox, QLineEdit)
    from PyQt5.QtCore import Qt, QTimer, pyqtSignal as Signal, QFileSystemWatcher, QPoint, QEvent, QObject, QRect, QSize, QByteArray
    from PyQt5.QtNetwork import QLocalServer, QLocalSocket
    from PyQt5.QtGui import QColor, QFont, QPalette, QCursor, QIcon, QPainter, QPainterPath, QPen, QBrush
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


class EditableTitleLabel(QLabel):
    """双击可编辑标题的 QLabel 子类"""
    titleChanged = Signal(str)

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._edit = None
        self._saved_text = ""
        self.setToolTip("双击编辑标题")

    def mouseDoubleClickEvent(self, event):
        """双击进入编辑模式"""
        if self._edit is not None:
            return
        self._saved_text = self.text()
        self.setText("")  # 隐藏原文字，避免透过半透明编辑框可见
        self._edit = QLineEdit(self._saved_text, self)
        self._edit.setAlignment(self.alignment())
        self._edit.setFont(self.font())
        self._edit.setFrame(False)
        self._edit.setStyleSheet("background: transparent; border: none; padding: 0px; color: inherit;")
        self._edit.setGeometry(self.rect())
        self._edit.selectAll()
        self._edit.setFocus()
        self._edit.editingFinished.connect(self._finish_edit)
        self._edit.show()
        self._edit.raise_()

    def _finish_edit(self):
        """完成编辑，恢复 QLabel"""
        if self._edit is None:
            return
        new_text = self._edit.text().strip()
        self._edit.deleteLater()
        self._edit = None
        if new_text:
            self.setText(new_text)
            self.titleChanged.emit(new_text)
        else:
            self.setText(self._saved_text)  # 恢复原标题

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._edit is not None:
            self._edit.setGeometry(self.rect())

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

        self.title_label = EditableTitleLabel(title)
        self.title_label.setObjectName("DockTitleLabel")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setWordWrap(False)
        self.title_label.titleChanged.connect(self._on_title_changed)
        self.layout.addWidget(self.title_label, 1)

        self.btn_close = QPushButton("×")
        self.btn_close.setObjectName("DockCloseButton")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("关闭绘图窗口")
        self.btn_close.clicked.connect(self.dock.close)
        self.layout.addWidget(self.btn_close, 0, Qt.AlignRight | Qt.AlignVCenter)

        self.setTitleSize(self.current_point_size)

    def _on_title_changed(self, new_title):
        """标题编辑完成后同步更新 dock 窗口标题并保存"""
        if hasattr(self.dock, 'setWindowTitle'):
            self.dock.setWindowTitle(new_title)
        try:
            # 沿父链查找主窗口（浮动 dock 时 self.window() 返回的是浮动窗口）
            main_win = self.dock
            while main_win is not None:
                if hasattr(main_win, 'save_preset'):
                    break
                main_win = main_win.parent()
            if main_win is None:
                main_win = self.window()
            if main_win is not None and hasattr(main_win, 'save_preset'):
                preset_name = getattr(main_win, 'current_preset_name', 'LastSession') or 'LastSession'
                main_win.save_preset(preset_name, refresh_list=False)
                if preset_name != 'LastSession':
                    main_win.save_preset('LastSession', refresh_list=False)
        except:
            pass

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
        self.btn_sidebar.setCheckable(True)
        self.btn_sidebar.setChecked(True)
        self.btn_sidebar.clicked.connect(self.parent.toggle_sidebar)
        lay.addWidget(self.btn_sidebar)
        
        self.brand_lbl = QLabel("FmuSolver - Data Visualizer")
        self.brand_lbl.setObjectName("BrandLabel")
        lay.addWidget(self.brand_lbl)
        self.version_lbl = QLabel(APP_VERSION)
        self.version_lbl.setObjectName("VersionBadge")
        self.version_lbl.setToolTip(f"Data Visualizer version {APP_VERSION}")
        lay.addWidget(self.version_lbl)
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
        
        lay.addWidget(self.btn_max)
        lay.addWidget(self.btn_min)

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
        axis_width = self.width()
        # A narrow dock still receives the default number of ticks from
        # pyqtgraph. Keep only every second/third label so the two-line date
        # text has enough horizontal room instead of drawing over its neighbor.
        label_step = 3 if 0 < axis_width < 320 else (2 if 0 < axis_width < 460 else 1)
        for index, v in enumerate(values):
            if label_step > 1 and index % label_step:
                strings.append("")
                continue
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
DEFAULT_CURVE_WIDTH = 1
SELECTED_CURVE_MIN_WIDTH = 2
CURVE_COLOR_PALETTE = (
    "#0000ff",  # 蓝色
    "#ff0000",  # 红色
    "#008000",  # 绿色
    "#ff00ff",  # 粉色
    "#00A6C8",  # 青色
    "#ffc125",  # 金色
    "#aa00ff",  # 紫色
    "#802a2a",  # 棕色
)

def load_app_version():
    candidates = [
        os.path.join(APP_DIR, "build_version.json"),
        os.path.join(os.path.dirname(APP_DIR), "Script", "build_version.json"),
    ]
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as f:
                version = str(json.load(f).get("version", "")).strip()
                if version:
                    return version
        except Exception:
            pass
    return "dev"

APP_VERSION = load_app_version()

class ProfessionalVisualizer(QMainWindow):
    data_received = Signal(object)

    def make_curve_pen(self, style, selected=False):
        pen = QPen(QColor(style["color"]))
        width = float(style["width"])
        if selected:
            width = max(SELECTED_CURVE_MIN_WIDTH, width)
        pen.setWidthF(width)
        pen.setCosmetic(True)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        return pen

    def make_gap_pen(self, style):
        color = QColor(style["color"])
        color.setAlpha(150)
        pen = QPen(color)
        pen.setWidthF(max(1.0, float(style["width"])))
        pen.setStyle(Qt.DashLine)
        pen.setCosmetic(True)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        return pen

    def default_curve_style(self, tag, index=0):
        # Assign colors by display/order index so curves are predictable and
        # follow the configured high-contrast palette.  The palette repeats
        # when more curves are added than available colors.
        color = CURVE_COLOR_PALETTE[int(index) % len(CURVE_COLOR_PALETTE)]
        return {"color": QColor(color), "width": DEFAULT_CURVE_WIDTH}

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
        # Keep a history for variables that are received but are not currently
        # part of the dashboard.  This lets a variable added mid-simulation
        # reuse samples collected since t=0 instead of starting at click time.
        self.background_data_store = {}
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
        self.data_revision = 0
        self.last_ui_revision = -1
        self.last_end_marker_time = None
        self.force_curve_update_revision = -1
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
        self.gap_curves = {}
        self.selected_curve_tag = None
        self.selected_curve_dock = None
        self.crosshairs = {}
        self.cursor_states = {}
        self.cursor_updaters = {}
        self.dock_order = []
        self._restoring_preset = False
        self._session_memory_pause = 0
        self._startup_layout_ready = False
        self.central_plot_name = "Main Plot"
        self.legacy_default_dock_names = {self.central_plot_name}
        
        self.var_styles = {}   
        self.vars_desc = {}    
        self.ordered_tags = []
        # The variable list can contain hundreds of rows.  Build its model
        # during construction, but defer the expensive QTableWidget item
        # creation until after the first window paint.
        self._variable_table_ready = False
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
        self.setup_activation_server()
        self.watcher = QFileSystemWatcher() # 必须在 apply_theme 前初始化
        
        # Applying the large stylesheet and enabling Windows composition are
        # both noticeably expensive on cold start.  Defer them together until
        # the first event-loop turn; the native window can paint immediately.
        QTimer.singleShot(0, self.apply_theme_from_config)
        QTimer.singleShot(0, lambda: set_blur_behind(self.winId()))
        
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

    def setup_activation_server(self):
        """Listen for a local ``show`` command from the launcher.

        A Qt-local socket is more reliable than searching by window title:
        the launcher can wake a hidden/minimized dashboard even while the
        native HWND is being created, and the dashboard performs activation
        on its own GUI thread.
        """
        self.activation_server_name = f"FmuSolver_DataVisualizer_{int(self.port)}"
        self.activation_server = QLocalServer(self)
        try:
            QLocalServer.removeServer(self.activation_server_name)
        except Exception:
            pass
        if not self.activation_server.listen(self.activation_server_name):
            # A stale endpoint can survive an unclean exit; remove and retry
            # once before falling back to the existing Win32 path.
            try:
                QLocalServer.removeServer(self.activation_server_name)
                self.activation_server.listen(self.activation_server_name)
            except Exception:
                pass
        self.activation_server.newConnection.connect(self._accept_activation_connection)

    def _accept_activation_connection(self):
        while self.activation_server.hasPendingConnections():
            socket = self.activation_server.nextPendingConnection()
            socket.readyRead.connect(lambda s=socket: self._read_activation_command(s))
            socket.disconnected.connect(socket.deleteLater)
            if socket.bytesAvailable():
                self._read_activation_command(socket)

    def _read_activation_command(self, socket):
        try:
            command = bytes(socket.readAll()).decode("utf-8", errors="ignore").strip().lower()
        except Exception:
            command = ""
        if command in ("show", "activate", "restore"):
            try:
                self.showNormal()
                self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
                self.show()
                self.raise_()
                self.activateWindow()
                self.update()
            except Exception:
                pass
        try:
            socket.disconnectFromServer()
        except Exception:
            pass

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
                        self.var_styles[name] = self.default_curve_style(name, i)
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
        QLabel#VersionBadge {{ color: {muted_text}; background: transparent; border: none; padding: 1px 0 0 2px; font-size: 10px; font-weight: 700; }}
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
        QPushButton#SidebarBtn:pressed {{ background: rgba(0,122,255,52); padding-top: 2px; }}
        QPushButton#SidebarBtn:checked {{ background: rgba(0,122,255,62); border: 1px solid rgba(0,122,255,96); }}
        QPushButton {{ background: {btn_bg}; color: {text_c}; border: 1px solid {border_soft}; border-radius: 16px; padding: 0 14px; font-weight: 700; font-size: 12px; min-height: 32px; max-height: 32px; }}
        QPushButton:hover {{ background: {btn_hover}; border: 1px solid {border_strong}; }}
        QPushButton:pressed {{ background: {btn_pressed}; border: 1px solid rgba(10,132,255,130); padding-top: 2px; padding-left: 15px; padding-right: 13px; }}
        QPushButton:checked {{ background: rgba(10,132,255,46); border: 1px solid rgba(10,132,255,122); color: {text_c}; }}
        QPushButton:checked:hover {{ background: rgba(10,132,255,62); }}
        QPushButton#PrimaryButton {{ background: {accent}; color: white; border: 1px solid rgba(10,132,255,160); }}
        QPushButton#PrimaryButton:hover {{ background: #2591FF; }}
        QPushButton#PrimaryButton:pressed {{ background: #0066D6; border: 1px solid rgba(0,74,173,220); padding-top: 2px; padding-left: 15px; padding-right: 13px; }}
        QPushButton#PrimaryButton:checked {{ background: #0057C2; color: white; border: 1px solid rgba(0,74,173,255); }}
        QPushButton#ExportButton {{ background: #34C759; color: white; border: 1px solid rgba(30, 150, 65, 190); }}
        QPushButton#ExportButton:hover {{ background: #42D968; border: 1px solid rgba(30, 150, 65, 230); }}
        QPushButton#ExportButton:pressed {{ background: #248A3D; border: 1px solid rgba(20, 105, 45, 235); padding-top: 2px; padding-left: 15px; padding-right: 13px; }}
        QPushButton#CollapsibleHeader {{ background: {subcard_bg}; color: {text_c}; border: 1px solid {border_soft}; border-radius: 12px; text-align: left; padding: 0 12px; }}
        QPushButton#CollapsibleHeader:hover {{ background: {btn_hover}; border: 1px solid {border_strong}; }}
        QPushButton#CollapsibleHeader:checked {{ background: rgba(10,132,255,32); border: 1px solid rgba(10,132,255,90); }}
        QPushButton#ControlBtn {{ padding: 0; border-radius: 50%; min-width: 14px; max-width: 14px; min-height: 14px; max-height: 14px; }}

        QTableWidget, QListWidget {{ background: transparent; border: none; color: {text_c}; selection-background-color: rgba(10,132,255,40); selection-color: {text_c}; outline: none; alternate-background-color: rgba(255,255,255,0.30); }}
        QTableWidget::item, QListWidget::item {{ padding: 7px 8px; border-radius: 10px; border-bottom: 1px solid {border_soft}; }}
        QTableWidget::item:selected {{ background: rgba(10,132,255,52); color: {accent}; border: 1px solid rgba(10,132,255,82); }}
        QListWidget::item:selected {{ background: rgba(10,132,255,36); }}
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
        export_word_btn.setObjectName("ExportButton")
        export_word_btn.clicked.connect(self.export_charts_to_word)
        ctrl_row.addWidget(export_word_btn)
        left_layout.addLayout(ctrl_row)

        self.plot_settings_toggle = QPushButton("绘图设置  ▸")
        self.plot_settings_toggle.setObjectName("CollapsibleHeader")
        self.plot_settings_toggle.setCheckable(True)
        self.plot_settings_toggle.setChecked(False)
        self.plot_settings_toggle.toggled.connect(self.set_plot_settings_expanded)
        left_layout.addWidget(self.plot_settings_toggle)

        self.plot_settings_panel = QFrame(); self.plot_settings_panel.setObjectName("PanelInset")
        settings_layout = QVBoxLayout(self.plot_settings_panel)
        settings_layout.setContentsMargins(10, 10, 10, 10)
        settings_layout.setSpacing(8)

        mode_row = QHBoxLayout(); mode_row.setSpacing(12)
        self.chk_autoscroll = QCheckBox("Realtime"); self.chk_autoscroll.setChecked(True)
        self.chk_autoscroll.toggled.connect(self.on_realtime_toggled)
        mode_row.addWidget(self.chk_autoscroll)
        mode_row.addStretch()
        self.chk_accumulate = QCheckBox("累积趋势")
        self.chk_accumulate.setChecked(False)
        self.chk_accumulate.toggled.connect(self.on_accumulate_toggled)
        mode_row.addWidget(self.chk_accumulate)
        settings_layout.addLayout(mode_row)
        
        slay = QGridLayout(); slay.setContentsMargins(0, 0, 0, 0); slay.setSpacing(6)
        
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

        slay.addWidget(QLabel("游标时间:"), 3, 0)
        self.cursor_time_combo = QComboBox(); self.cursor_time_combo.addItems(["模型时间", "实际计时"])
        cv = QListView(); cv.setObjectName("ComboView")
        self.cursor_time_combo.setView(cv)
        if cv.window(): cv.window().setAttribute(Qt.WA_TranslucentBackground, False)
        self.cursor_time_combo.currentIndexChanged.connect(self.on_cursor_time_mode_changed)
        slay.addWidget(self.cursor_time_combo, 3, 1)
        settings_layout.addLayout(slay)
        self.plot_settings_panel.setVisible(False)
        left_layout.addWidget(self.plot_settings_panel)
        
        # 使用 QSplitter 让变量表格和预设列表可以上下拖动调整高度
        self.left_splitter = QSplitter(Qt.Vertical)
        self.left_splitter.setChildrenCollapsible(False)
        self.left_splitter.setHandleWidth(4)
        self.left_splitter.splitterMoved.connect(lambda *_: self.save_ui_settings())
        
        # 上半部分：变量表格容器
        # Keep the table empty for the initial paint.  Populating 700+ rows
        # synchronously here makes the dashboard appear frozen on startup.
        self.table = QTableWidget(0, 3)
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
        self.table.itemClicked.connect(self.on_variable_item_clicked)
        
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
        # Run after the event loop starts, so the dashboard can paint its
        # frame before creating all variable-row widgets.
        # A short delay gives Qt one paint cycle before allocating the row
        # widgets; on a cold start this makes the dashboard responsive much
        # earlier while the table fills almost immediately afterwards.
        QTimer.singleShot(50, self._populate_variable_table)

        self.current_preset_name = "LastSession"
        self.load_presets()
        self.load_ui_settings()
        # 初始加载默认或上一次的布局
        QTimer.singleShot(500, self.auto_load_last_layout)

    def _populate_variable_table(self):
        """Create the variable rows after the first dashboard paint."""
        if self._variable_table_ready:
            return
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(len(self.ordered_tags))
            for i, tag in enumerate(self.ordered_tags):
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)

                # 仅设置初始状态，由 LastSession 统一负责恢复具体 Dock 关联
                saved_state = self.sync_states.get(tag, False)
                chk.setCheckState(Qt.Checked if saved_state else Qt.Unchecked)

                self.table.setItem(i, 0, chk)
                name_item = QTableWidgetItem(self.get_display_name(tag))
                name_item.setData(Qt.UserRole, tag)
                self.table.setItem(i, 1, name_item)
                self.table.setItem(i, 2, QTableWidgetItem("0.0000"))
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
        self._variable_table_ready = True
        self.table.itemChanged.connect(self.on_table_item_changed)

    def _append_runtime_variable_model(self, tag, desc=""):
        """Register a runtime variable without requiring table widgets."""
        self.ordered_tags.append(tag)
        self.vars_config.append({"name": tag, "desc": desc, "runtime": True})
        history = self.background_data_store.pop(tag, None)
        self.data_store[tag] = history if history is not None else np.full(self.max_points, np.nan)
        self.trend_store[tag] = []
        self.var_styles[tag] = self.default_curve_style(tag, len(self.ordered_tags) - 1)
        self.vars_desc[tag] = desc

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
        # Packets may arrive while the deferred table is still being built.
        # Keep the data model complete and let _populate_variable_table add
        # the corresponding row in one batch.
        if not self._variable_table_ready:
            self._append_runtime_variable_model(tag, desc)
            return
        row = self.table.rowCount()
        self.table.blockSignals(True)
        self.table.insertRow(row)
        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        chk.setCheckState(Qt.Unchecked)
        self.table.setItem(row, 0, chk)
        name_item = QTableWidgetItem(self.get_display_name(tag))
        name_item.setData(Qt.UserRole, tag)
        self.table.setItem(row, 1, name_item)
        self.table.setItem(row, 2, QTableWidgetItem("0.0000"))
        self.table.blockSignals(False)

        self._append_runtime_variable_model(tag, desc)

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
        
        dock_titles = {}
        for d_name, d_obj in self.docks.items():
            if hasattr(d_obj, 'title_bar_widget') and hasattr(d_obj.title_bar_widget, 'title_label'):
                t = d_obj.title_bar_widget.title_label.text()
                if t and t != d_name:
                    dock_titles[d_name] = t

        preset = {
            "dock_order": [dock_name for dock_name in self.dock_order if dock_name in self.docks],
            "dock_vars": dock_data,
            "dock_titles": dock_titles,
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
        self.current_preset_name = name
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
            self.gap_curves = {}
            # Newly restored curve items must render immediately, even when the
            # data revision has not changed since the previous preset.
            self.last_curve_update_idx.clear()
            self.last_view_update.clear()
            self.last_y_range.clear()
            self.selected_curve_tag = None
            self.selected_curve_dock = None

            # 2. 重新创建 Dock 容器
            dock_vars = data.get("dock_vars", {})
            saved_order = data.get("dock_order") or list(dock_vars.keys()) or []
            saved_order = [d_name for d_name in saved_order if d_name not in self.legacy_default_dock_names or dock_vars.get(d_name)]

            for d_name in saved_order:
                self.create_dock_internal(d_name)

            # 2.5 恢复自定义标题
            dock_titles = data.get("dock_titles", {})
            for d_name, custom_title in dock_titles.items():
                if d_name in self.docks:
                    dock = self.docks[d_name]
                    if hasattr(dock, 'title_bar_widget') and hasattr(dock.title_bar_widget, 'title_label'):
                        dock.title_bar_widget.title_label.setText(custom_title)

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
            # A single non-floating dock can retain the old saved width and
            # leave the dock host's central area blank after restore. Refill
            # the available canvas once the dock layout has settled.
            if len(self.docks) == 1 and not next(iter(self.docks.values())).isFloating():
                QTimer.singleShot(220, self.normalize_dock_sizes)
                QTimer.singleShot(420, self.normalize_dock_sizes)

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
                # The curve may have been removed and re-added at the same
                # data revision. Invalidate the old marker so its history is
                # rendered immediately instead of waiting for new samples.
                self.last_curve_update_idx.pop((dock_name, tag), None)
                pw = self.plot_widgets[dock_name]
                selected = tag == self.selected_curve_tag and dock_name == self.selected_curve_dock
                c = pw.plot(
                    pen=self.make_curve_pen(self.var_styles[tag], selected=selected),
                    name=self.get_display_name(tag),
                    autoDownsample=False,
                    skipFiniteCheck=True,
                    connect='finite',
                    antialias=True,
                )
                self.curves[tag][dock_name] = c
                self.configure_curve_selection(c, tag, dock_name)
                self.create_gap_curve(tag, dock_name)
                self.request_curve_refresh()
                self.render_curve_history(tag, dock_name)
        else:
            if tag in self.curves and dock_name in self.curves[tag]:
                self.plot_widgets[dock_name].removeItem(self.curves[tag][dock_name])
                del self.curves[tag][dock_name]
                self.remove_gap_curve(tag, dock_name)
                if tag == self.selected_curve_tag and dock_name == self.selected_curve_dock:
                    self.selected_curve_dock = None

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

    def request_curve_refresh(self):
        """Invalidate the UI revision so a newly added curve renders all history immediately."""
        self.last_ui_revision = -1
        self.force_curve_update_revision = self.data_revision

    def render_curve_history(self, tag, dock_name):
        """Paint a newly added curve immediately, without waiting for a new packet."""
        curve = self.curves.get(tag, {}).get(dock_name)
        if curve is None or self.current_idx <= 0 or tag not in self.data_store:
            return
        try:
            t_data, y_store = self.get_active_series({tag})
            y_data = y_store.get(tag)
            if y_data is None or len(t_data) == 0:
                return
            t_plot, y_plot = (
                self.build_trend_plot_data(t_data, y_data, self.accumulate_max_render_points)
                if self.accumulate_enabled else
                self.build_realtime_plot_data(t_data, y_data, self.realtime_max_render_points)
            )
            if len(t_plot) == 0:
                return
            curve.setData(x=t_plot, y=y_plot, connect='finite')
            self.update_dock_y_range(dock_name, self.plot_widgets[dock_name].getViewBox(), [y_plot])
        except Exception:
            pass
            
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
        try:
            if hasattr(self, "activation_server"):
                self.activation_server.close()
        except Exception:
            pass
        event.accept()

    def save_ui_settings(self):
        if hasattr(self, 'main_splitter') and self.left_panel.isVisible():
            sizes = self.main_splitter.sizes()
            if sizes and sizes[0] > 40:
                self.last_sidebar_width = sizes[0]
        s = {
            "title_size": self.title_size_spin.value(),
            "name_mode": self.name_mode_combo.currentIndex(),
            "cursor_time_mode": self.cursor_time_combo.currentIndex() if hasattr(self, 'cursor_time_combo') else 0,
            "span": self.span_spin.value(),
            "accumulate_enabled": self.chk_accumulate.isChecked() if hasattr(self, 'chk_accumulate') else False,
            "plot_settings_expanded": self.plot_settings_toggle.isChecked() if hasattr(self, 'plot_settings_toggle') else False,
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
        if hasattr(self, 'cursor_time_combo'):
            self.cursor_time_combo.setCurrentIndex(max(0, min(1, int(s.get("cursor_time_mode", self.cursor_time_combo.currentIndex())))))
        self.span_spin.setValue(int(s.get("span", self.span_spin.value())))
        if hasattr(self, 'chk_accumulate'):
            self.chk_accumulate.setChecked(bool(s.get("accumulate_enabled", False)))
        if hasattr(self, 'plot_settings_toggle'):
            expanded = bool(s.get("plot_settings_expanded", False))
            self.plot_settings_toggle.blockSignals(True)
            self.plot_settings_toggle.setChecked(expanded)
            self.plot_settings_toggle.blockSignals(False)
            self.set_plot_settings_expanded(expanded, save=False)
        sidebar_visible = bool(s.get("sidebar_visible", True))
        self.left_panel.setVisible(sidebar_visible)
        self.last_sidebar_width = int(s.get("last_sidebar_width", 320))

        main_sizes = s.get("main_splitter") or [320, 960]
        left_sizes = s.get("left_splitter") or [480, 220]
        if not sidebar_visible:
            main_sizes = [0, max(1, self.width())]
        QTimer.singleShot(0, lambda: self.main_splitter.setSizes(main_sizes))
        QTimer.singleShot(0, lambda: self.left_splitter.setSizes(left_sizes))

    def set_plot_settings_expanded(self, expanded, save=True):
        expanded = bool(expanded)
        if hasattr(self, 'plot_settings_panel'):
            self.plot_settings_panel.setVisible(expanded)
        if hasattr(self, 'plot_settings_toggle'):
            self.plot_settings_toggle.setText("绘图设置  ▾" if expanded else "绘图设置  ▸")
        if save and hasattr(self, 'left_splitter'):
            self.save_ui_settings()

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
            self.title_bar.btn_sidebar.setChecked(False)
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
            self.title_bar.btn_sidebar.setChecked(True)
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
        history_len = len(self.trend_times)
        active_tags = self.get_plotted_tags() or set(self.ordered_tags[:min(len(self.ordered_tags), 80)])
        for tag in active_tags:
            self.trend_store.setdefault(tag, [])
            if len(self.trend_store[tag]) < history_len:
                missing = history_len - len(self.trend_store[tag])
                self.trend_store[tag][0:0] = [np.nan] * missing
            elif len(self.trend_store[tag]) > history_len:
                self.trend_store[tag] = self.trend_store[tag][-history_len:] if history_len else []
            values = self.trend_bucket_values.get(tag, [])
            if values:
                self.trend_store[tag].append(float(values[-1]))
            else:
                self.trend_store[tag].append(self.trend_bucket_last_values.get(tag, np.nan))
        self.trend_times.append(bucket_time)
        for tag in list(self.trend_store.keys()):
            if tag not in active_tags:
                self.trend_store[tag] = []

        self.trend_bucket_start = None
        self.trend_bucket_end = None
        self.trend_bucket_values = {}
        self.trim_accumulate_buffers()

    def append_trend_sample(self, t, var_map):
        if self.trend_times and abs(float(self.trend_times[-1]) - float(t)) <= 1e-9:
            active_tags = self.get_plotted_tags() or set(var_map.keys())
            for tag, value in var_map.items():
                if tag in active_tags:
                    values = self.trend_store.setdefault(tag, [])
                    if len(values) < len(self.trend_times):
                        values[0:0] = [np.nan] * (len(self.trend_times) - len(values))
                    if values:
                        values[-1] = float(value)
                self.trend_bucket_last_values[tag] = value
            return

        # The exact FMU initialization snapshot is a real boundary sample. Keep it
        # outside the accumulation bucket so its timestamp cannot move to ~1 second.
        if abs(float(t)) <= 1e-9 and not self.trend_times and var_map:
            active_tags = self.get_plotted_tags() or set(var_map.keys())
            for tag in active_tags:
                self.trend_store.setdefault(tag, [])
                value = var_map.get(tag, np.nan)
                self.trend_store[tag].append(float(value) if np.isfinite(value) else np.nan)
            self.trend_times.append(0.0)
            self.trend_bucket_last_values.update(var_map)
            self.trend_bucket_start = None
            self.trend_bucket_end = None
            self.trend_bucket_values = {}
            return

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

    def append_trend_boundary(self, t):
        self.flush_trend_bucket()
        if self.trend_times and abs(float(self.trend_times[-1]) - float(t)) <= 1e-9:
            return
        active_tags = self.get_plotted_tags() or set(self.ordered_tags[:min(len(self.ordered_tags), 80)])
        if not active_tags:
            return
        history_len = len(self.trend_times)
        for tag in active_tags:
            self.trend_store.setdefault(tag, [])
            if len(self.trend_store[tag]) < history_len:
                missing = history_len - len(self.trend_store[tag])
                self.trend_store[tag][0:0] = [np.nan] * missing
            elif len(self.trend_store[tag]) > history_len:
                self.trend_store[tag] = self.trend_store[tag][-history_len:] if history_len else []
            if tag in self.trend_bucket_last_values:
                value = self.trend_bucket_last_values[tag]
            elif tag in self.latest_values:
                value = self.latest_values[tag]
            elif self.trend_store[tag]:
                value = self.trend_store[tag][-1]
            else:
                value = np.nan
            self.trend_store[tag].append(float(value) if np.isfinite(value) else np.nan)
        self.trend_times.append(t)
        self.trend_bucket_start = None
        self.trend_bucket_end = None
        self.trend_bucket_values = {}
        self.trim_accumulate_buffers()

    def sanitize_active_series(self, t_data, y_data):
        t_arr = np.asarray(t_data, dtype=float)
        if t_arr.size == 0:
            return np.asarray([], dtype=float), {tag: np.asarray([], dtype=float) for tag in y_data}

        y_arrs = {}
        for tag, values in y_data.items():
            values_arr = np.asarray(values, dtype=float)
            if values_arr.size < t_arr.size:
                values_arr = np.concatenate((np.full(t_arr.size - values_arr.size, np.nan), values_arr))
            elif values_arr.size > t_arr.size:
                values_arr = values_arr[-t_arr.size:]
            y_arrs[tag] = values_arr
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
            for tag in active_tags:
                if len(self.trend_store.get(tag, [])) < len(self.trend_times):
                    self.backfill_trend_history(tag)
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

    def backfill_trend_history(self, tag):
        """Rebuild an accumulated curve from raw samples when it is added late."""
        if tag not in self.data_store or not self.trend_times or self.current_idx <= 0:
            return
        valid_len = min(self.current_idx, self.max_points)
        if self.current_idx > self.max_points:
            start = self.current_idx % self.max_points
            raw_t = np.concatenate((self.times[start:], self.times[:start]))
            raw_y = np.concatenate((self.data_store[tag][start:], self.data_store[tag][:start]))
        else:
            raw_t = self.times[:valid_len]
            raw_y = self.data_store[tag][:valid_len]
        finite = np.isfinite(raw_t)
        raw_t = np.asarray(raw_t[finite], dtype=float)
        raw_y = np.asarray(raw_y[finite], dtype=float)
        if raw_t.size == 0:
            self.trend_store[tag] = [np.nan] * len(self.trend_times)
            return
        # Use the last raw sample at or before each accumulated timestamp.
        positions = np.searchsorted(raw_t, np.asarray(self.trend_times, dtype=float), side="right") - 1
        values = np.full(len(self.trend_times), np.nan, dtype=float)
        valid = positions >= 0
        values[valid] = raw_y[np.clip(positions[valid], 0, len(raw_y) - 1)]
        self.trend_store[tag] = values.tolist()

    def build_realtime_plot_data(self, x_data, y_data, max_points):
        x_arr = np.asarray(x_data, dtype=float)
        y_arr = np.asarray(y_data, dtype=float)
        finite_time = np.isfinite(x_arr)
        if not finite_time.any():
            return np.asarray([], dtype=float), np.asarray([], dtype=float)

        x_arr = x_arr[finite_time]
        y_arr = y_arr[finite_time]
        if not np.isfinite(y_arr).any():
            return np.asarray([], dtype=float), np.asarray([], dtype=float)
        total = len(x_arr)
        target = max(16, int(max_points))
        if total <= target:
            return x_arr, y_arr

        sampled_idx = np.linspace(0, total - 1, target, dtype=int)
        transitions = np.where(np.diff(np.isfinite(y_arr).astype(np.int8)) != 0)[0]
        gap_edges = []
        for transition in transitions:
            gap_edges.extend([int(transition), int(transition) + 1])
        sampled_idx = np.asarray(sorted(set(sampled_idx.tolist() + gap_edges + [0, total - 1])), dtype=int)
        return x_arr[sampled_idx], y_arr[sampled_idx]

    def build_trend_plot_data(self, x_data, y_data, max_points):
        x_arr = np.asarray(x_data, dtype=float)
        y_arr = np.asarray(y_data, dtype=float)
        finite_time = np.isfinite(x_arr)
        if not finite_time.any():
            return np.asarray([], dtype=float), np.asarray([], dtype=float)

        x_arr = x_arr[finite_time]
        y_arr = y_arr[finite_time]
        if not np.isfinite(y_arr).any():
            return np.asarray([], dtype=float), np.asarray([], dtype=float)
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
            finite_segment = np.flatnonzero(np.isfinite(segment))
            if finite_segment.size == 0:
                sampled_idx.extend([start, end - 1])
                continue

            finite_values = segment[finite_segment]
            local_min = start + int(finite_segment[int(np.argmin(finite_values))])
            local_max = start + int(finite_segment[int(np.argmax(finite_values))])
            candidates = sorted({start, local_min, local_max, end - 1})
            sampled_idx.extend(candidates)

        sampled_idx.append(total - 1)
        sampled_idx = np.asarray(sorted(set(idx for idx in sampled_idx if 0 <= idx < total)), dtype=int)

        if sampled_idx.size > target:
            keep = np.linspace(0, sampled_idx.size - 1, target, dtype=int)
            sampled_idx = sampled_idx[keep]
            sampled_idx = np.asarray(sorted(set(sampled_idx.tolist() + [0, total - 1])), dtype=int)

        transitions = np.where(np.diff(np.isfinite(y_arr).astype(np.int8)) != 0)[0]
        gap_edges = []
        for transition in transitions:
            gap_edges.extend([int(transition), int(transition) + 1])
        if gap_edges:
            sampled_idx = np.asarray(sorted(set(sampled_idx.tolist() + gap_edges)), dtype=int)

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
                if hasattr(dock.title_bar_widget, 'title_label'):
                    cur = dock.title_bar_widget.title_label.text()
                    if not cur or cur == dock_name:
                        dock.title_bar_widget.title_label.setText(dock_name)
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

    def on_cursor_time_mode_changed(self, *_):
        self.save_ui_settings()
        for dock_name, enabled in list(self.cursor_states.items()):
            if not enabled:
                continue
            updater = self.cursor_updaters.get(dock_name)
            cursor_line = self.crosshairs.get(dock_name, (None, None))[0]
            if updater and cursor_line is not None:
                try:
                    updater(float(cursor_line.value()))
                except Exception:
                    pass

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
        name_item = self.table.item(row, 1)
        if not name_item:
            return
        tag = name_item.data(Qt.UserRole) or name_item.text()
        if tag not in self.var_styles:
            return
        
        self.show_curve_style_menu(tag, self.table.viewport().mapToGlobal(pos))

    def show_curve_style_menu(self, tag, global_pos):
        if tag not in self.var_styles:
            return
        menu = QMenu(self)
        action_color = menu.addAction("🎨 修改线条颜色")
        action_width = menu.addAction("📏 修改线条粗细")
        
        action = menu.exec_(global_pos) if QT_VERSION == 5 else menu.exec(global_pos)
        
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
                selected = tag == self.selected_curve_tag and dock_name == self.selected_curve_dock
                curveItem.setPen(self.make_curve_pen(style, selected=selected))
                try:
                    curveItem.setCurveClickable(True, width=max(8, int(style["width"]) + 6))
                except Exception:
                    pass
            for gap_item in self.gap_curves.get(tag, {}).values():
                gap_item.setPen(self.make_gap_pen(style))

    def create_gap_curve(self, tag, dock_name):
        if dock_name not in self.plot_widgets or tag not in self.var_styles:
            return None
        self.gap_curves.setdefault(tag, {})
        if dock_name in self.gap_curves[tag]:
            return self.gap_curves[tag][dock_name]
        gap_item = self.plot_widgets[dock_name].plot(
            pen=self.make_gap_pen(self.var_styles[tag]),
            name=None,
            autoDownsample=False,
            skipFiniteCheck=True,
            connect='finite',
            antialias=True,
        )
        gap_item.setZValue(20.0)
        self.gap_curves[tag][dock_name] = gap_item
        return gap_item

    def remove_gap_curve(self, tag, dock_name):
        gap_item = self.gap_curves.get(tag, {}).pop(dock_name, None)
        if gap_item is not None and dock_name in self.plot_widgets:
            self.plot_widgets[dock_name].removeItem(gap_item)
        if tag in self.gap_curves and not self.gap_curves[tag]:
            del self.gap_curves[tag]

    def build_gap_bridge_data(self, x_data, y_data):
        x_arr = np.asarray(x_data, dtype=float)
        y_arr = np.asarray(y_data, dtype=float)
        count = min(x_arr.size, y_arr.size)
        if count < 3:
            return np.asarray([], dtype=float), np.asarray([], dtype=float)
        x_arr = x_arr[:count]
        y_arr = y_arr[:count]
        finite = np.isfinite(x_arr) & np.isfinite(y_arr)
        gap_x = []
        gap_y = []
        index = 1
        while index < count - 1:
            if finite[index]:
                index += 1
                continue
            gap_start = index
            while index < count and not finite[index]:
                index += 1
            left_index = gap_start - 1
            right_index = index
            if left_index >= 0 and right_index < count and finite[left_index] and finite[right_index]:
                gap_x.extend([x_arr[left_index], x_arr[right_index], np.nan])
                gap_y.extend([y_arr[left_index], y_arr[right_index], np.nan])
        return np.asarray(gap_x, dtype=float), np.asarray(gap_y, dtype=float)

    def configure_curve_selection(self, curve_item, tag, dock_name):
        try:
            curve_item.setCurveClickable(True, width=max(8, int(self.var_styles[tag]["width"]) + 6))
            curve_item.sigClicked.connect(
                lambda _item, event, selected_tag=tag, selected_dock=dock_name: self.on_curve_clicked(
                    event, selected_tag, selected_dock
                )
            )
        except Exception:
            pass

    def on_curve_clicked(self, event, tag, dock_name):
        if event.button() == Qt.RightButton:
            self.show_curve_style_menu(tag, QCursor.pos())
            event.accept()
            return
        if event.button() != Qt.LeftButton:
            return
        if tag == self.selected_curve_tag and dock_name == self.selected_curve_dock:
            self.clear_curve_selection()
        else:
            self.select_curve_variable(tag, dock_name)
        event.accept()

    def clear_curve_selection(self):
        self.selected_curve_tag = None
        self.selected_curve_dock = None
        for curve_tag, dock_curves in self.curves.items():
            style = self.var_styles.get(curve_tag)
            if not style:
                continue
            for curve_item in dock_curves.values():
                curve_item.setPen(self.make_curve_pen(style, selected=False))
                curve_item.setZValue(0.0)
        self.table.clearSelection()

    def on_variable_item_clicked(self, item):
        row = item.row()
        if not 0 <= row < len(self.ordered_tags):
            return
        tag = self.ordered_tags[row]
        dock_name = self.active_dock_name if getattr(self, 'active_dock_name', None) in self.plot_widgets else None
        self.select_curve_variable(tag, dock_name, select_table=False)

    def select_curve_variable(self, tag, dock_name=None, select_table=True):
        if tag not in self.ordered_tags:
            return

        if dock_name not in self.curves.get(tag, {}):
            active_dock = getattr(self, 'active_dock_name', None)
            if active_dock in self.curves.get(tag, {}):
                dock_name = active_dock
            elif self.curves.get(tag):
                dock_name = next(iter(self.curves[tag]))
            else:
                dock_name = None

        if dock_name in self.docks:
            self.set_active_dock(dock_name)

        self.selected_curve_tag = tag
        self.selected_curve_dock = dock_name

        for curve_tag, dock_curves in self.curves.items():
            style = self.var_styles.get(curve_tag)
            if not style:
                continue
            for current_dock, curve_item in dock_curves.items():
                selected = curve_tag == tag and current_dock == dock_name
                curve_item.setPen(self.make_curve_pen(style, selected=selected))
                curve_item.setZValue(100.0 if selected else 0.0)

        if select_table:
            row = self.ordered_tags.index(tag)
            self.table.blockSignals(True)
            try:
                self.table.selectRow(row)
                name_item = self.table.item(row, 1)
                if name_item is not None:
                    self.table.setCurrentItem(name_item)
                    self.table.scrollToItem(name_item)
            finally:
                self.table.blockSignals(False)

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
        plot_widget.getPlotItem().getViewBox().setMouseMode(pg.ViewBox.PanMode)
        plot_widget.getPlotItem().getViewBox().setDefaultPadding(0.02)
        plot_widget.getPlotItem().getViewBox().disableAutoRange()
        plot_widget.getPlotItem().hideButtons()
        plot_widget.getPlotItem().setMenuEnabled(False)
        plot_widget.getPlotItem().getAxis('left').setWidth(72)
        plot_widget.getPlotItem().getAxis('bottom').setStyle(tickTextOffset=8)
        
        # 可拖动曲线游标：右键开启；点击定位；拖动竖线查看同一时刻曲线交点值。
        vLine = pg.InfiniteLine(angle=90, movable=True, pen=pg.mkPen('#f59e0b', width=1, style=Qt.DashLine), hoverPen=pg.mkPen('#f97316', width=2))
        time_bg = QGraphicsRectItem()
        time_bg.setBrush(QBrush(QColor(255, 255, 255, 218)))
        time_bg.setPen(QPen(QColor('#94a3b8')))
        time_label = QGraphicsTextItem("")
        time_label.setDefaultTextColor(getattr(self, 'plot_axis_text', QColor('white')))
        value_labels = {}
        vLine.setZValue(1000)
        time_bg.setZValue(1001)
        time_label.setZValue(1002)
        plot_widget.addItem(vLine, ignoreBounds=True)
        plot_widget.scene().addItem(time_bg)
        plot_widget.scene().addItem(time_label)
        vLine.setVisible(False)
        time_bg.setVisible(False)
        time_label.setVisible(False)
        
        def set_cursor_visible(visible):
            vLine.setVisible(visible)
            time_bg.setVisible(visible)
            time_label.setVisible(visible)
            for item in value_labels.values():
                item.setVisible(visible)

        def update_cursor(cursor_x=None):
            if not self.cursor_states.get(name, False):
                set_cursor_visible(False)
                return
            active_tags = [tag for tag, dock_map in self.curves.items() if name in dock_map and tag in self.data_store]
            t_array, y_store = self.get_active_series(active_tags)
            if len(t_array) == 0:
                set_cursor_visible(False)
                return
            if cursor_x is None:
                x_min, x_max = plot_widget.getViewBox().viewRange()[0]
                visible_idx = np.where((t_array >= float(x_min)) & (t_array <= float(x_max)))[0]
                if visible_idx.size:
                    cursor_x = float(t_array[int(visible_idx[visible_idx.size // 2])])
                else:
                    cursor_x = (float(x_min) + float(x_max)) / 2.0
            index = int((np.abs(t_array - cursor_x)).argmin())
            cursor_x = float(t_array[index])
            try:
                vLine.blockSignals(True)
                vLine.setPos(cursor_x)
            finally:
                vLine.blockSignals(False)
            vLine.setVisible(True)

            cursor_time_mode = self.cursor_time_combo.currentIndex() if hasattr(self, 'cursor_time_combo') else 0
            if cursor_time_mode == 1:
                # 实际计时显示仿真从 0s 开始后的经过时间；不能减第一帧时间。
                # 第一帧通常是 step=0.02s，若减掉它，20s 终点会误显示为 19.98s。
                elapsed_sec = max(0.0, cursor_x)
                hh = int(elapsed_sec // 3600)
                mm = int((elapsed_sec % 3600) // 60)
                ss = elapsed_sec % 60
                time_text = f"{hh:02d}:{mm:02d}:{ss:05.2f}"
            elif self.base_datetime is not None:
                dt = self.base_datetime + datetime.timedelta(seconds=(cursor_x - self.base_sim_time))
                time_text = dt.strftime('%H:%M:%S')
            else:
                time_text = f"{cursor_x:.2f}"

            visible_tags = set()
            label_rows = []
            for tag in self.curves:
                if name in self.curves[tag]:
                    y_array = y_store.get(tag)
                    if y_array is None or index >= len(y_array) or not np.isfinite(y_array[index]):
                        continue
                    value = float(y_array[index])
                    visible_tags.add(tag)
                    if tag not in value_labels:
                        color = self.var_styles.get(tag, {}).get("color", QColor("#2563eb"))
                        value_label = pg.TextItem(
                            text="",
                            color=QColor(color),
                            fill=pg.mkBrush(255, 255, 255, 210),
                            border=pg.mkPen(QColor(color), width=1),
                            anchor=(0, 0.5),
                        )
                        value_label.setZValue(1002)
                        plot_widget.addItem(value_label, ignoreBounds=True)
                        value_labels[tag] = value_label
                    value_labels[tag].setText(f"{value:.10g}")
                    value_labels[tag].setVisible(True)
                    label_rows.append((tag, value))

            for tag, item in value_labels.items():
                if tag not in visible_tags:
                    item.setVisible(False)

            x_min, x_max = plot_widget.getViewBox().viewRange()[0]
            y_min, y_max = plot_widget.getViewBox().viewRange()[1]
            vb = plot_widget.getViewBox()
            view_scene_rect = vb.sceneBoundingRect()
            cursor_scene = vb.mapViewToScene(pg.Point(cursor_x, y_min))
            if label_rows:
                view_height = max(1.0, vb.sceneBoundingRect().height())
                data_per_px = (float(y_max) - float(y_min)) / view_height if y_max != y_min else 1.0
                view_width = max(1.0, view_scene_rect.width())
                data_per_px_x = (float(x_max) - float(x_min)) / view_width if x_max != x_min else 1.0
                min_gap = data_per_px * 22.0
                top_pad = data_per_px * 14.0
                bottom_pad = data_per_px * 14.0
                lower_bound = float(y_min) + bottom_pad
                upper_bound = float(y_max) - top_pad
                max_label_width = max(value_labels[tag].boundingRect().width() for tag, _ in label_rows)
                show_labels_on_left = (view_scene_rect.right() - cursor_scene.x()) < (max_label_width + 12.0)
                label_anchor = (1, 0.5) if show_labels_on_left else (0, 0.5)
                label_x = cursor_x + (-4.0 if show_labels_on_left else 4.0) * data_per_px_x

                arranged = []
                for tag, value in sorted(label_rows, key=lambda item: item[1]):
                    y_pos = min(max(float(value), lower_bound), upper_bound)
                    if arranged and y_pos - arranged[-1][1] < min_gap:
                        y_pos = arranged[-1][1] + min_gap
                    arranged.append((tag, y_pos))

                overflow = arranged[-1][1] - upper_bound if arranged else 0.0
                if overflow > 0:
                    arranged = [(tag, y_pos - overflow) for tag, y_pos in arranged]
                    adjusted = []
                    for tag, y_pos in arranged:
                        y_pos = max(y_pos, lower_bound)
                        if adjusted and y_pos - adjusted[-1][1] < min_gap:
                            y_pos = adjusted[-1][1] + min_gap
                        adjusted.append((tag, min(y_pos, upper_bound)))
                    arranged = adjusted

                for tag, y_pos in arranged:
                    value_labels[tag].setAnchor(label_anchor)
                    value_labels[tag].setPos(label_x, y_pos)

            time_label.setPlainText(time_text)
            text_rect = time_label.boundingRect()
            pad_x, pad_y = 6.0, 2.0
            box_w = text_rect.width() + pad_x * 2.0
            box_h = text_rect.height() + pad_y * 2.0
            box_x = cursor_scene.x() - box_w / 2.0
            box_x = max(view_scene_rect.left(), min(box_x, view_scene_rect.right() - box_w))
            box_y = view_scene_rect.bottom() + 4.0
            time_bg.setRect(0, 0, box_w, box_h)
            time_bg.setPos(box_x, box_y)
            time_label.setPos(box_x + pad_x, box_y + pad_y - 2.0)
            is_time_visible = x_min <= cursor_x <= x_max
            time_bg.setVisible(is_time_visible)
            time_label.setVisible(is_time_visible)

        vLine.sigPositionChanged.connect(lambda _line: update_cursor(float(vLine.value())))
        self.cursor_updaters[name] = update_cursor
        
        # 保留游标位置；鼠标离开图表后不自动隐藏，便于读数和截图。
        class LeaveFilter(QObject):
            def eventFilter(self, obj, event):
                return False
        
        self.leave_filter = LeaveFilter(self)
        plot_widget.installEventFilter(self.leave_filter)
        
        # 用户手动拖拽或缩放时，自动取消画面跟随
        plot_widget.getViewBox().sigRangeChangedManually.connect(lambda: self.chk_autoscroll.setChecked(False))

        def curve_at_plot_pos(pos):
            """Return the curve under a plot-widget context-menu position."""
            scene_pos = plot_widget.mapToScene(pos)
            # Iterate from the visually topmost curve so overlapping curves pick
            # the one the user can actually see/click.
            candidates = []
            for curve_tag, dock_curves in self.curves.items():
                curve_item = dock_curves.get(name)
                if curve_item is not None:
                    candidates.append((curve_item.zValue(), curve_tag, curve_item))
            for _z, curve_tag, curve_item in sorted(candidates, reverse=True, key=lambda value: value[0]):
                try:
                    curve_path = getattr(curve_item, "curve", curve_item)
                    local_pos = curve_path.mapFromScene(scene_pos)
                    if curve_path.mouseShape().contains(local_pos):
                        return curve_tag
                except Exception:
                    continue
            return None

        def show_plot_menu(pos):
            curve_tag = curve_at_plot_pos(pos)
            if curve_tag is not None:
                self.show_curve_style_menu(curve_tag, plot_widget.mapToGlobal(pos))
                return
            menu = QMenu(plot_widget)
            cursor_enabled = self.cursor_states.get(name, False)
            action_cursor = menu.addAction("关闭游标" if cursor_enabled else "开启游标")
            action = menu.exec_(plot_widget.mapToGlobal(pos)) if QT_VERSION == 5 else menu.exec(plot_widget.mapToGlobal(pos))
            if action == action_cursor:
                enabled = not self.cursor_states.get(name, False)
                self.cursor_states[name] = enabled
                if enabled:
                    update_cursor(None)
                else:
                    set_cursor_visible(False)

        plot_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        plot_widget.customContextMenuRequested.connect(show_plot_menu)
        
        # 点击激活窗口机制
        def mouseClicked(evt):
            self.set_active_dock(name)
            if self.cursor_states.get(name, False) and evt.button() == Qt.LeftButton and plot_widget.sceneBoundingRect().contains(evt.scenePos()):
                mouse_point = plot_widget.plotItem.vb.mapSceneToView(evt.scenePos())
                update_cursor(float(mouse_point.x()))
                evt.accept()
        plot_widget.scene().sigMouseClicked.connect(mouseClicked)
        
        dock.setWidget(plot_widget)
        self.docks[name] = dock
        self.plot_widgets[name] = plot_widget
        self.crosshairs[name] = (vLine, time_label, time_bg)
        self.cursor_states[name] = False
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
        cursor_items = self.crosshairs.get(name, ())
        for item in cursor_items[1:]:
            try:
                self.plot_widgets[name].scene().removeItem(item)
            except Exception:
                pass
        # 清理对应的曲线
        for tag in list(self.curves.keys()):
            if name in self.curves[tag]:
                del self.curves[tag][name]
        for tag in list(self.gap_curves.keys()):
            if name in self.gap_curves[tag]:
                del self.gap_curves[tag][name]
            if not self.gap_curves[tag]:
                del self.gap_curves[tag]
        if self.selected_curve_dock == name:
            self.selected_curve_dock = None
        del self.plot_widgets[name]
        del self.docks[name]
        del self.crosshairs[name]
        self.cursor_states.pop(name, None)
        self.cursor_updaters.pop(name, None)
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
                self.last_curve_update_idx.pop((dock_name, tag), None)
                style = self.var_styles[tag]
                curve = pw.plot(
                    pen=self.make_curve_pen(
                        style,
                        selected=tag == self.selected_curve_tag and dock_name == self.selected_curve_dock,
                    ),
                    name=self.get_display_name(tag),
                    autoDownsample=False,
                    skipFiniteCheck=True,
                    connect='finite',
                    antialias=True,
                )
                self.curves[tag][dock_name] = curve
                self.configure_curve_selection(curve, tag, dock_name)
                self.create_gap_curve(tag, dock_name)
                self.request_curve_refresh()
                self.render_curve_history(tag, dock_name)
        else:
            if dock_name in self.curves[tag]:
                pw.removeItem(self.curves[tag][dock_name])
                del self.curves[tag][dock_name]
                self.remove_gap_curve(tag, dock_name)
                if tag == self.selected_curve_tag and dock_name == self.selected_curve_dock:
                    self.selected_curve_dock = None
        self.remember_last_session()

    def setup_network(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind(('0.0.0.0', self.port))
            print(f"Listening on {self.port}")
            ready_file = os.environ.get("FMUSOLVER_VIZ_READY_FILE", "").strip()
            if ready_file:
                try:
                    with open(ready_file, 'w', encoding='utf-8') as ready_handle:
                        ready_handle.write(f"pid={os.getpid()} port={self.port}\n")
                except Exception as ready_error:
                    print(f"Visualizer ready file error: {ready_error}")
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
            f"last_ui_ms={ui_elapsed_ms:.2f} docks={len(self.plot_widgets)} vars={len(self.data_store)} idx={self.current_idx} "
            f"rev={self.data_revision} force_rev={self.force_curve_update_revision} latest_t={(float(self.times[(self.current_idx - 1) % self.max_points]) if self.current_idx > 0 else 0.0):.9f} "
            f"first_t={(float(self.times[0]) if self.current_idx > 0 else -1.0):.9f} "
            f"trend_first={(float(self.trend_times[0]) if self.trend_times else -1.0):.9f} "
            f"trend_latest={(float(self.trend_times[-1]) if self.trend_times else -1.0):.9f}\n"
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

        has_start_marker = any(
            str(getattr(variable, 'name', '')) == "__FMUSOLVER_SIM_START_TIME__"
            for variable in pb_data.sim_vars
        )
        if has_start_marker:
            self.reset_simulation_history()

        # 同一仿真时刻可能会被分成多个 UDP 包发送；这些包必须合并到同一帧。
        # 否则看板去重时只保留第一包，后续包中的变量曲线会在终点/分包点断线。
        merge_tolerance = 1e-9
        if self.current_idx > 0:
            prev_idx = (self.current_idx - 1) % self.max_points
            same_frame = abs(float(self.times[prev_idx]) - float(t)) <= merge_tolerance
        else:
            same_frame = False

        if same_frame:
            idx = prev_idx
            is_new_frame = False
        else:
            idx = self.current_idx % self.max_points
            self.times[idx] = t
            is_new_frame = True
            if self.current_idx > 0:
                source_idx = (self.current_idx - 1) % self.max_points
                history_values = list(self.data_store.values()) + [
                    values for name, values in self.background_data_store.items()
                    if name not in self.data_store
                ]
                for values in history_values:
                    values[idx] = values[source_idx]
            else:
                history_values = list(self.data_store.values()) + [
                    values for name, values in self.background_data_store.items()
                    if name not in self.data_store
                ]
                for values in history_values:
                    values[idx] = np.nan

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

        has_end_marker = "__FMUSOLVER_SIM_END_TIME__" in var_map
        public_var_map = {name: val for name, val in var_map.items() if not str(name).startswith("__FMUSOLVER_")}
        if has_end_marker and self.last_end_marker_time != t:
            self.last_end_marker_time = t
            self.force_curve_update_revision = self.data_revision + 1
            try:
                with open(self.perf_log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [SNAPSHOT][VIZ] final time marker received: sim_time={float(t):.9f}s vars={len(pb_data.sim_vars)} idx={self.current_idx}\n")
            except Exception:
                pass

        if self.accumulate_enabled:
            if has_start_marker and not public_var_map:
                pass
            elif has_end_marker and not public_var_map:
                self.append_trend_boundary(t)
            else:
                self.append_trend_sample(t, public_var_map)

        if has_start_marker and public_var_map:
            try:
                finite_count = sum(1 for value in public_var_map.values() if np.isfinite(float(value)))
                with open(self.perf_log_file, "a", encoding="utf-8") as f:
                    f.write(
                        f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                        f"[SNAPSHOT][VIZ] exact initial frame accepted: sim_time={float(t):.9f}s "
                        f"vars={len(public_var_map)} finite={finite_count} accumulate={int(self.accumulate_enabled)}\n"
                    )
            except Exception:
                pass
        
        # 解析绝对时间基准
        if self.base_datetime is None and 'Year' in public_var_map:
            try:
                y, m, d = int(public_var_map['Year']), int(public_var_map['Mon']), int(public_var_map['Day'])
                h, minute, s = int(public_var_map['Hour']), int(public_var_map['Min']), int(public_var_map['Sec'])
                if y > 1900:
                    self.base_sim_time = t
                    self.base_datetime = datetime.datetime(y, m, d, h, minute, s)
            except: pass

        for name in public_var_map:
            if name not in self.data_store:
                self.background_data_store.setdefault(name, np.full(self.max_points, np.nan))
                self.register_runtime_variable(name)

        for name, val in public_var_map.items():
            values = self.data_store.get(name)
            if values is None:
                values = self.background_data_store.get(name)
            if values is not None:
                values[idx] = val
                if name in self.data_store:
                    self.latest_values[name] = val

        if is_new_frame:
            self.current_idx += 1
        self.data_revision += 1

    def reset_simulation_history(self):
        self.current_idx = 0
        self.times.fill(0.0)
        for values in self.data_store.values():
            values.fill(np.nan)
        for values in self.background_data_store.values():
            values.fill(np.nan)
        self.latest_values.clear()
        self.trend_times.clear()
        for values in self.trend_store.values():
            values.clear()
        self.trend_bucket_start = None
        self.trend_bucket_end = None
        self.trend_bucket_values = {}
        self.trend_bucket_last_values = {}
        self.base_datetime = None
        self.base_sim_time = 0.0
        self.last_end_marker_time = None
        self.last_ui_idx = -1
        self.last_ui_revision = -1
        self.last_curve_update_idx.clear()
        self.last_view_update.clear()
        self.data_revision += 1

    def update_ui(self):
        ui_start = time.perf_counter()
        self.drain_packet_queue()
        # The first packet can arrive before the deferred table population.
        # Defer only the presentation update; process_data has already kept
        # the data buffers current and the next tick will render them.
        if not self._variable_table_ready:
            self.write_perf_log(0.0)
            return
        if self.current_idx == 0:
            self.write_perf_log(0.0)
            return
        if self.data_revision == self.last_ui_revision:
            self.write_perf_log(0.0)
            return
        self.last_ui_idx = self.current_idx
        self.last_ui_revision = self.data_revision
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

            force_curve_update = self.data_revision == self.force_curve_update_revision
            if self.accumulate_enabled and not force_curve_update and (self.current_idx % self.accumulate_update_stride) != 0:
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
                if self.chk_autoscroll.isChecked() and not self.accumulate_enabled and self.last_curve_update_idx.get(update_key) == self.data_revision:
                    continue

                y_full = y_store.get(tag)
                if y_full is None or len(y_full) == 0:
                    continue

                y_slice = y_full[start_idx:end_idx]
                gap_item = self.gap_curves.get(tag, {}).get(dock_name) or self.create_gap_curve(tag, dock_name)
                if gap_item is not None:
                    gap_x, gap_y = self.build_gap_bridge_data(t_slice, y_slice)
                    gap_item.setData(x=gap_x, y=gap_y, connect='finite')
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
                self.last_curve_update_idx[update_key] = self.data_revision

            self.update_dock_y_range(dock_name, vb, rendered_y_arrays)
            if self.cursor_states.get(dock_name, False):
                updater = self.cursor_updaters.get(dock_name)
                if updater:
                    try:
                        cursor_line = self.crosshairs.get(dock_name, (None, None))[0]
                        updater(float(cursor_line.value()) if cursor_line is not None else None)
                    except Exception:
                        pass
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
    parser.add_argument("--start-hidden", action="store_true", help="预热启动时先隐藏窗口，等待主程序唤醒")
    args = parser.parse_args()
    
    try:
        app = QApplication(sys.argv)
        window = ProfessionalVisualizer(port=args.port)
        window.show()
        if args.start_hidden:
            # Create the native window handle so the launcher can find and
            # restore it immediately, but keep the preloaded dashboard out of
            # the user's way until the 看板 button is clicked.
            window.hide()
        sys.exit(app.exec_() if QT_VERSION == 5 else app.exec())
    except Exception:
        try:
            with open(os.path.join(APP_DIR, "visualizer_fatal.log"), "a", encoding="utf-8") as f:
                f.write(f"\n--- Visualizer Fatal {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                f.write(traceback.format_exc())
        except Exception:
            pass
        raise
