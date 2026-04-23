import os
import pefile # 如果没有，可以直接查看二进制头

target_dir = r"C:\Spaceship\fmu_work\binaries\win32"
failed_dlls = ["dynamic_rvddll.dll", "GNCCsim.dll", "GNC_EOB_SYC1.dll"]

print("[*] Tracing inner dependencies for failed DLLs...")

def get_dependencies(file_path):
    deps = []
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
            # 搜索常见的 .dll 字符串（这是一种简单但极其有效的办法）
            import re
            found = re.findall(b"[a-zA-Z0-9_\-\.]+\.dll", content)
            deps = sorted(list(set([d.decode().lower() for d in found])))
    except: pass
    return deps

for dll in failed_dlls:
    print(f"\n[!] Checking {dll}:")
    deps = get_dependencies(os.path.join(target_dir, dll))
    # 过滤掉系统核心库和自身已有的库
    for d in deps:
        if d not in [d.lower() for d in os.listdir(target_dir)]:
            print(f"    - Potential missing: {d}")

