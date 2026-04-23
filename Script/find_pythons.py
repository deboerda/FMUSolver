import os
import platform
import struct

def get_arch(exe_path):
    try:
        with open(exe_path, 'rb') as f:
            header = f.read(1024)
            if b'PE' in header:
                # Simple check for IA64/AMD64 hex values
                if b'\x64\x86' in header: return '64bit'
                if b'\x4c\x01' in header: return '32bit'
        return 'Unknown'
    except:
        return 'Error'

python_found = []
for root, dirs, files in os.walk('C:\\Users\\木木\\AppData\\Local\\Programs\\Python'):
    if 'python.exe' in files:
        full_path = os.path.join(root, 'python.exe')
        python_found.append((full_path, get_arch(full_path)))

for root, dirs, files in os.walk('C:\\Program Files (x86)\\Python'):
    if 'python.exe' in files:
        full_path = os.path.join(root, 'python.exe')
        python_found.append((full_path, get_arch(full_path)))

with open('python_paths.txt', 'w') as f:
    for p, a in python_found:
        f.write(f'{p}|{a}\n')
