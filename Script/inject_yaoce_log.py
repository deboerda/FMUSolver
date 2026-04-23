import os

target_file = r'c:\Spaceship\FMUSOLVER\Script\FmuLauncherUniversal.py'
with open(target_file, 'r', encoding='utf-8') as f: content = f.read()

import re

old_reader = '''    def _yaoce_log_reader(self):
        if not hasattr(self, 'yaoce_proc') or not self.yaoce_proc: return
        for line in iter(self.yaoce_proc.stdout.readline, ''):
            if not line: continue
            l = line.strip()
            tag = "sys"
            if "[SEND]" in l or "[OK]" in l or "[*]" in l: tag = "info"
            elif "[!]" in l or "Error" in l or "Exception" in l: tag = "error"
            self.root.after(0, self.ylog, l, tag)
            
        self.yaoce_proc.stdout.close()
        rc = self.yaoce_proc.wait()
        self.root.after(0, self.ylog, f"[SYS] 转发引擎退出，退出码: {rc}", "sys")
        self.root.after(0, lambda: self.btn_yaoce_start.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.btn_yaoce_stop.config(state=tk.DISABLED))'''

new_reader = '''    def _yaoce_log_reader(self):
        if not hasattr(self, 'yaoce_proc') or not self.yaoce_proc: return
        log_file = os.path.join(APP_DIR, "yaoce_run.log")
        last_pos = 0
        import time
        while self.yaoce_proc.poll() is None:
            if os.path.exists(log_file):
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        f.seek(last_pos)
                        lines = f.readlines()
                        last_pos = f.tell()
                        for l in lines:
                            l = l.strip()
                            if not l: continue
                            tag = "sys"
                            if "[SEND]" in l or "[TCP/UDP]" in l or "[RECV]" in l or "[OK]" in l or "[*]" in l: tag = "info"
                            elif "[-]" in l: tag = "error"
                            elif "[WARN]" in l: tag = "error"
                            elif "[!]" in l or "Error" in l or "Exception" in l: tag = "error"
                            self.root.after(0, self.ylog, l, tag)
                except: pass
            time.sleep(0.2)
        rc = self.yaoce_proc.wait()
        self.root.after(0, self.ylog, f"[SYS] 转发引擎退出，退出码: {rc}", "sys")
        self.root.after(0, lambda: self.btn_yaoce_start.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.btn_yaoce_stop.config(state=tk.DISABLED))'''

old_main = '''    elif len(sys.argv) > 1 and sys.argv[1] == "--yaoceworker":
        import builtins
        import os
        
        # 针对 PyInstaller console=False 导致 stdout 黑洞的问题
        # 强制底层写出到文件描述符 1 (连接到了 Popen 的 stdout PIPE)
        def _fd_print(*args, **kwargs):
            try:
                msg = " ".join(map(str, args)) + "\\n"
                os.write(1, msg.encode('utf-8'))
            except: pass
            
        builtins.print = _fd_print
        import sys
        
        class FDWriter:
            def __init__(self, prefix=""): self.p = prefix
            def write(self, s):
                if s.strip(): _fd_print(self.p + s.strip())
            def flush(self): pass
            
        sys.stdout = FDWriter()
        sys.stderr = FDWriter("[!ERR] ")

        yaoce_path = os.path.join(APP_DIR, "yaocetest")'''

new_main = '''    elif len(sys.argv) > 1 and sys.argv[1] == "--yaoceworker":
        import builtins
        import os
        
        log_file = os.path.join(APP_DIR, "yaoce_run.log")
        with open(log_file, "w", encoding="utf-8") as f: f.write("")
        
        def _file_print(*args, **kwargs):
            try:
                msg = " ".join(map(str, args)) + "\\n"
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(msg)
            except: pass
            
        builtins.print = _file_print
        import sys

        yaoce_path = os.path.join(APP_DIR, "yaocetest")'''

content = content.replace(old_reader, new_reader)
content = content.replace(old_main, new_main)

with open(target_file, 'w', encoding='utf-8') as f: f.write(content)
print("Done")
