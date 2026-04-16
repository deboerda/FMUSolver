"""Find exactly which DLL fails to load - test each companion DLL one-by-one with 32-bit ctypes"""
import ctypes, os, sys

bin_dir = r"C:\Spaceship\FmuSolver_Package\fmu_work_worker2\binaries\win32"

# Add bin_dir to search path
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(bin_dir)
os.environ['PATH'] = bin_dir + ";" + os.environ.get('PATH', '')
os.chdir(bin_dir)

dll_files = sorted([f for f in os.listdir(bin_dir) if f.lower().endswith('.dll')])

print(f"Python: {sys.version} | bits: {struct.calcsize('P')*8 if True else '?'}")

for dll in dll_files:
    path = os.path.join(bin_dir, dll)
    try:
        lib = ctypes.CDLL(path)
        print(f"  OK    {dll}")
    except Exception as e:
        print(f"  FAIL  {dll}")
        print(f"        {e}")

# Also check if system C++ runtimes exist
print("\n=== C++ Runtime DLLs on this system (SysWOW64 = 32-bit) ===")
wow64 = r"C:\Windows\SysWOW64"
runtimes = [
    "msvcr100.dll", "msvcp100.dll",
    "msvcr110.dll", "msvcp110.dll",
    "msvcr120.dll", "msvcp120.dll",
    "vcruntime140.dll", "msvcp140.dll", "vcruntime140_1.dll",
    "vcomp140.dll", "vcomp120.dll", "vcomp100.dll",
    "openmp.dll",
]
for r in runtimes:
    p32 = os.path.join(wow64, r)
    p64 = os.path.join(r"C:\Windows\System32", r)
    have = os.path.exists(p32) or os.path.exists(p64)
    print(f"  {'YES' if have else 'NO '} {r}")
