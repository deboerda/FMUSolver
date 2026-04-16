"""Inspect EPS_CJ.fmu: list ALL files, and check implicit DLL deps (if dumpbin available)"""
import zipfile, os, subprocess, sys

fmu = r'C:\Spaceship\FmuSolver_Package\FMU\MTLibrary_System_EPS_PD_EPS_CJ.fmu'
with zipfile.ZipFile(fmu) as z:
    all_files = z.namelist()

print("=== ALL FILES IN FMU ===")
for f in sorted(all_files):
    info = z.getinfo(f)
    if info.file_size > 0:
        print(f"  {f}  ({info.file_size:,} bytes)")

# Check what's extracted to fmu_work_worker2/binaries/win32
bin_dir = r"C:\Spaceship\FmuSolver_Package\fmu_work_worker2\binaries\win32"
print(f"\n=== FILES IN {bin_dir} ===")
if os.path.exists(bin_dir):
    for f in sorted(os.listdir(bin_dir)):
        sz = os.path.getsize(os.path.join(bin_dir, f))
        print(f"  {f}  ({sz:,} bytes)")
else:
    print("  (directory does not exist)")

# Check root dir
root = r"C:\Spaceship\FmuSolver_Package"
print(f"\n=== DLLs in {root} ===")
for f in os.listdir(root):
    if f.lower().endswith('.dll'):
        sz = os.path.getsize(os.path.join(root, f))
        print(f"  {f}  ({sz:,} bytes)")

# Try dumpbin on the main DLL
main_dll = os.path.join(bin_dir, "MTLibrary_System_EPS_PD_EPS_CJ.dll")
if os.path.exists(main_dll):
    print(f"\n=== DUMPBIN /DEPENDENTS on main DLL ===")
    # Try VS dumpbin
    for dumpbin in [r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.43.34808\bin\Hostx64\x64\dumpbin.exe",
                    r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Tools\MSVC\14.29.30133\bin\HostX86\x86\dumpbin.exe"]:
        if os.path.exists(dumpbin):
            r = subprocess.run([dumpbin, '/dependents', main_dll], capture_output=True, text=True)
            print(r.stdout[:3000])
            break
    else:
        print("  dumpbin not found; using C:\Py32\python.exe to test ctypes.CDLL load:")
        # Test load directly
        r2 = subprocess.run([r'C:\Py32\python.exe', '-c',
            f'import ctypes, os\n'
            f'os.add_dll_directory({bin_dir!r})\n'
            f'os.environ["PATH"] = {bin_dir!r} + ";" + os.environ.get("PATH","")\n'
            f'try:\n'
            f'  lib = ctypes.CDLL({main_dll!r})\n'
            f'  print("LOADED OK:", lib)\n'
            f'except Exception as e:\n'
            f'  print("FAIL:", e)\n'
        ], capture_output=True, text=True)
        print("STDOUT:", r2.stdout)
        print("STDERR:", r2.stderr[:2000])
