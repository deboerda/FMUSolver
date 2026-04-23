import os
import sys
import ctypes
import platform

# 必须由 32 位 Python 运行
target_dir = r"C:\Spaceship\fmu_work_worker\binaries\win32"
os.add_dll_directory(target_dir)

dlls = [f for f in os.listdir(target_dir) if f.endswith('.dll')]
print(f"[*] Starting DLL Diagnostics for {len(dlls)} files...")

results = {}
for dll_name in dlls:
    path = os.path.join(target_dir, dll_name)
    try:
        lib = ctypes.WinDLL(path)
        results[dll_name] = "OK"
    except Exception as e:
        results[dll_name] = f"FAILED: {e}"

print("\n" + "="*50)
print("             DLL LOADING REPORT")
print("="*50)
for name, status in results.items():
    if "FAILED" in status:
        print(f"[X] {name:40} | {status}")
    else:
        print(f"[V] {name:40} | OK")
