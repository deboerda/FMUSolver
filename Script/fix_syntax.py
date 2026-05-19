import re

with open('c:/Spaceship/FMUSOLVER/Script/FmuLauncherUniversal.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The junk block is between the end of the f-string and the setStyleSheet call
# Actually, the f-string was closed early and then junk followed.

# I'll replace the entire apply_theme method with a clean version.
pattern = re.compile(r'    def apply_theme\(self, base_color, text_color=None\):[\s\S]*?self\.setStyleSheet\(qss\)\n')
new_apply_theme = '''    def apply_theme(self, base_color, text_color=None):
        r, g, b = base_color.red(), base_color.green(), base_color.blue()
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        is_dark = brightness < 128
        
        if text_color:
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
        
        qss = f"""
        QMainWindow, QDialog {{ background: transparent; color: {text_c}; font-family: 'SF Pro Display', 'Inter', 'PingFang SC', 'Microsoft YaHei UI', sans-serif; font-size: 13px; }}
        QWidget#MainContainer {{ background: {main_bg}; border: none; border-radius: 12px; }}
        QWidget#TitleBar {{ background: transparent; border-top-left-radius: 12px; border-top-right-radius: 12px; border-bottom: 1px solid rgba(255,255,255,80); }}
        QWidget#TabContainer {{ background: transparent; border: none; }}
        QWidget#ContentStack {{ background: transparent; }}
        QLabel#BrandLabel, QLabel#HeaderLabel {{ color: {text_c}; font-size: 15px; font-weight: 800; }}
        QLabel#SubHeaderLabel, QLabel#StatusText, QLabel#Muted, QLabel#ParamLabel {{ color: {text_c}; font-weight: 600; }}
        QLabel#StatusText {{ font-size: 11px; font-weight: 700; }}
        QLabel#SubHeaderLabel {{ font-size: 11px; opacity: 0.8; }}
        QLabel#ParamLabel {{ font-size: 10px; opacity: 0.8; }}
        
        QPushButton#ThemeBtn {{
            min-width: 14px; max-width: 14px; min-height: 14px; max-height: 14px; padding: 0; border: none; border-radius: 7px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #FF5F56, stop:0.5 #FFBD2E, stop:1 #27C93F);
        }}
        QPushButton#ThemeBtn:hover {{ border: 1px solid rgba(255,255,255,180); }}
        
        QFrame#Card {{ background: {card_bg}; border: 1px solid {btn_border}; border-radius: 14px; }}
        QFrame#SegTrack {{ background: {seg_bg}; border: 1px solid rgba(0, 0, 0, 8); border-radius: 17px; }}
        QPushButton#SegBtn {{ background: transparent; color: {text_c}; border: none; border-radius: 15px; padding: 0 14px; min-height: 32px; max-height: 32px; font-weight: 600; font-size: 13px; }}
        QPushButton#SegBtn:hover {{ background: {seg_btn_hover}; color: {text_c}; }}
        QPushButton#SegBtnActive {{ background: {seg_btn_active}; color: {seg_btn_active_text}; border: none; border-radius: 15px; padding: 0 14px; min-height: 32px; max-height: 32px; font-weight: 800; font-size: 13px; }}
        QLabel#Title {{ color: {text_c}; font-size: 12pt; font-weight: 800; }}
        
        QLineEdit#PathEdit, QLineEdit#ParamEdit, QLineEdit#SeriesEdit {{ background: {input_bg}; border: none; border-radius: 6px; color: {text_c}; font-family: 'SF Mono', 'Cascadia Mono', 'Consolas', monospace; font-weight: 600; padding: 0 10px; }}
        QLineEdit#PathEdit {{ min-height: 26px; max-height: 26px; font-size: 11px; }}
        QLineEdit#ParamEdit {{ min-height: 25px; max-height: 25px; font-size: 12px; }}
        QLineEdit#SeriesEdit {{ min-height: 25px; max-height: 25px; font-size: 11px; border-bottom: 1px solid rgba(128,128,128,50); background: transparent; }}
        QLineEdit#ParamEdit:focus, QLineEdit#PathEdit:focus {{ background: {card_bg}; border: 1px solid rgba(0, 122, 255, 90); }}
        
        QPushButton {{ background: {btn_bg}; color: {text_c}; border: 1px solid {btn_border}; border-radius: 16px; padding: 0 14px; font-weight: 700; font-size: 13px; min-height: 32px; max-height: 32px; }}
        QPushButton:hover {{ background: {btn_hover}; }}
        QPushButton:disabled {{ color: {text_c}; opacity: 0.5; background: rgba(128, 128, 128, 30); border: 1px solid rgba(128, 128, 128, 20); }}
        QPushButton#PrimaryAction {{ background: #007AFF; color: white; border: 1px solid rgba(0, 98, 204, 235); font-weight: 800; }}
        QPushButton#Danger {{ background: rgba(255, 59, 48, 42); color: #FF3B30; border: 1px solid rgba(255, 59, 48, 120); font-weight: 800; }}
        
        QCheckBox {{ spacing: 8px; font-size: 12px; color: {text_c}; font-weight: 600; }}
        QCheckBox::indicator {{ width: 15px; height: 15px; border-radius: 4px; background: {card_bg}; border: 1px solid {btn_border}; }}
        QCheckBox::indicator:checked {{ background: #007AFF; border: 1px solid #007AFF; }}
        QCheckBox#SwitchCheck, QCheckBox#CaptureLogs {{ color: #2F87F6; font-size: 11px; font-weight: 700; }}
        
        QProgressBar {{ background: rgba(0, 0, 0, 10); border: none; border-radius: 3px; min-height: 6px; max-height: 6px; text-align: center; color: transparent; }}
        QProgressBar::chunk {{ background: #2F8CFF; border-radius: 3px; }}
        
        QFrame#ConsoleShell {{ background: rgba(30, 30, 30, 242); border: none; border-radius: 12px; }}
        QTextEdit#Console {{ background: transparent; color: #FFFFFF; border: none; font-family: 'SF Mono', 'Consolas', monospace; font-size: 11px; line-height: 1.4; }}
        
        QScrollBar:vertical {{ border: none; background: transparent; width: 8px; margin: 0px 0px 0px 0px; }}
        QScrollBar::handle:vertical {{ background: rgba(128, 128, 128, 100); min-height: 30px; border-radius: 4px; }}
        QScrollBar::handle:vertical:hover {{ background: rgba(128, 128, 128, 150); }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QScrollBar:horizontal {{ height: 0px; }}
        """
        self.setStyleSheet(qss)
'''

content = pattern.sub(new_apply_theme, content)

# Remove any extra duplicated qss if they survived the regex (unlikely but safe)
content = content.replace('"""\n        self.setStyleSheet(qss)\n        QLineEdit#PathEdit', '"""\n        self.setStyleSheet(qss)\n        # Removed junk')

with open('c:/Spaceship/FMUSOLVER/Script/FmuLauncherUniversal.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done!")
