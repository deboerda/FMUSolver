import sys, os, json, time, threading, subprocess, re, socket, zipfile
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QGridLayout, QLabel, QLineEdit, QPushButton, QFrame, QScrollArea, 
                             QPlainTextEdit, QProgressBar, QCheckBox, QFileDialog, QTreeWidget, 
                             QTreeWidgetItem, QHeaderView, QDialog, QGraphicsDropShadowEffect)
from PySide6.QtCore import Qt, QTimer, Signal, QSize, QRect, QPoint
from PySide6.QtGui import QFont, QColor, QIcon, QPainter, QBrush, QPen, QCursor

# ─── Constants & Colors ───
APP_DIR   = os.path.dirname(os.path.abspath(__file__))
GUI_CONFIG_PATH = os.path.join(APP_DIR, "gui_config.json")

C_BG      = "#F5F5F7"
C_CARD    = "#FFFFFF"
C_ACCENT  = "#007AFF"
C_SUCCESS = "#28CD41"
C_ERROR   = "#FF3B30"
C_WARNING = "#FF9F0A"
C_TEXT    = "#1D1D1F"
C_MUTED   = "#86868B"
C_INPUT   = "#E3E3E8" 
C_SEP     = "#D1D1D6"

# ─── Global QSS (macOS Sequoia High Fidelity) ───
APP_QSS = f"""
QMainWindow, QDialog {{
    background: {C_BG};
}}
QWidget {{
    background: transparent;
    color: {C_TEXT};
    font-family: 'Segoe UI Variable Text', 'SF Pro Text', sans-serif;
    font-size: 13px;
    letter-spacing: 0.2px;
}}

/* ══ Modern Card ══ */
QFrame#Card {{
    background: {C_CARD};
    border-radius: 14px;
    border: none;
}}

/* ══ Segmented Control (The Capsule Track) ══ */
QWidget#SegTrack {{
    background: #E3E3E8;
    border-radius: 10px;
}}
QPushButton#SegBtn {{
    background: transparent;
    color: #48484A;
    border: none;
    border-radius: 8px;
    padding: 6px 18px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#SegBtnActive {{
    background: {C_CARD};
    color: {C_TEXT};
    border: none;
    border-radius: 8px;
    padding: 6px 18px;
    font-size: 12px;
    font-weight: 600;
}}

/* ══ Pill Input Group ══ */
QFrame#PillInput {{
    background: #EBEBEB;
    border-radius: 6px;
}}
QLabel#PillLabel {{
    color: #86868B;
    font-size: 11px;
    font-weight: 500;
    padding-left: 8px;
}}
QLineEdit#PillEdit {{
    background: transparent;
    border: none;
    color: {C_TEXT};
    font-family: 'SF Mono', 'Consolas', monospace;
    font-size: 12px;
    padding: 4px 8px;
}}
QLineEdit#PillEdit:focus {{
    background: {C_CARD};
    border: 2px solid {C_ACCENT};
    border-radius: 5px;
}}

/* ══ Buttons ══ */
QPushButton {{
    background: #E3E3E8; 
    color: {C_TEXT};
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 600;
    font-size: 13px;
    min-height: 32px;
}}
QPushButton:hover {{ background: #D1D1D6; }}

/* Primary Action (Blue) */
QPushButton#PrimaryAction {{
    background: {C_ACCENT};
    color: white;
}}
QPushButton#PrimaryAction:hover {{ background: #0071EB; }}
QPushButton#PrimaryAction:pressed {{ background: #005ECB; }}

QPushButton#Danger {{
    background: {C_ERROR};
    color: white;
}}
QPushButton#Danger:hover {{ background: #E0352A; }}

/* ══ Progress Bar ══ */
QProgressBar {{
    background: #E3E3E8;
    border-radius: 3px;
    border: none;
    min-height: 6px;
    max-height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {C_ACCENT};
    border-radius: 3px;
}}

/* ══ Console ══ */
QPlainTextEdit#Console {{
    background: #1C1C1E;
    color: #D4D4D4;
    border: none;
    border-radius: 12px;
    font-family: 'SF Mono', 'Consolas', monospace;
    font-size: 12px;
    padding: 12px;
}}
"""

# ─── Modern UI Helper Classes ───

class ModernCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 20))
        self.setGraphicsEffect(shadow)

class PillInput(QFrame):
    def __init__(self, label_text, value="", parent=None):
        super().__init__(parent)
        self.setObjectName("PillInput")
        self.setFixedHeight(32)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(4)
        
        lbl = QLabel(label_text)
        lbl.setObjectName("PillLabel")
        lay.addWidget(lbl)
        
        self.edit = QLineEdit(str(value))
        self.edit.setObjectName("PillEdit")
        lay.addWidget(self.edit, 1)

class SegmentedControl(QWidget):
    changed = Signal(int)
    def __init__(self, labels, parent=None):
        super().__init__(parent)
        self.setObjectName("SegTrack")
        self.setFixedHeight(38)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(4)
        self.buttons = []
        for i, text in enumerate(labels):
            btn = QPushButton(text)
            btn.setObjectName("SegBtn")
            btn.clicked.connect(lambda _, idx=i: self.set_index(idx))
            btn.setCursor(Qt.PointingHandCursor)
            self.layout.addWidget(btn)
            self.buttons.append(btn)
        self.set_index(0)

    def set_index(self, idx):
        for i, btn in enumerate(self.buttons):
            btn.setObjectName("SegBtnActive" if i == idx else "SegBtn")
            btn.setStyle(btn.style())
        self.changed.emit(idx)

# ─── Helper Factories ───

def card(parent=None): return ModernCard(parent)
def pill_field(label, value="", parent=None): return PillInput(label, value, parent)
def btn(text, primary=True, parent=None):
    b = QPushButton(text, parent)
    if primary: b.setObjectName("PrimaryAction")
    b.setCursor(Qt.PointingHandCursor)
    return b
def danger_btn(text, parent=None):
    b = QPushButton(text, parent)
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
    f.setStyleSheet("background: #E5E5EA;")
    return f

# ─── Low-level Engine Helpers ───

def get_fmu_arch(fmu_path):
    try:
        with zipfile.ZipFile(fmu_path, 'r') as z:
            names = z.namelist()
            if any(n.startswith('binaries/win64/') for n in names): return 64
            if any(n.startswith('binaries/win32/') for n in names): return 32
    except: pass
    return None

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
    roots = [os.path.join(APP_DIR, "FMU"), os.path.join(APP_DIR, "..", "FMU"), APP_DIR]
    result = _find_file_by_names(roots, names)
    if result: return result
    return None

def auto_find_yaoce_dir():
    for c in [os.path.join(APP_DIR, "yaocetest"), os.path.join(APP_DIR, "..", "yaocetest")]:
        if os.path.isdir(c) and os.path.exists(os.path.join(c, "config.ini")):
            return os.path.normpath(c)
    return None
