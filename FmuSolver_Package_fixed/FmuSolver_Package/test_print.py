import sys
import os

log_file = "test_print.log"

class FileOut:
    def write(self, text):
        with open(log_file, "a", encoding="utf-8") as f: f.write(text)
    def flush(self): pass

sys.stdout = FileOut()
sys.stderr = FileOut()

print("This is a print test.")
