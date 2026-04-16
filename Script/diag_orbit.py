"""Diagnostic: test FMU init without setting orbital params"""
import os
import sys
import zipfile
import shutil
import fmpy
from fmpy import instantiate_fmu, read_model_description

# Use 32-bit python: C:\Py32\python.exe
app_dir = r"C:\Spaceship\FmuSolver_Package"
fmu_path = r"C:\Spaceship\FMU\MTLibrary_System_EPS_PD_Orbit_Pre.fmu"

os.chdir(app_dir)

extract_dir = os.path.join(app_dir, "fmu_orbit_work")
os.makedirs(extract_dir, exist_ok=True)

with zipfile.ZipFile(fmu_path, 'r') as z:
    z.extractall(extract_dir)

arch = "win32"
bin_dir = os.path.join(extract_dir, "binaries", arch)
protected = {'kernel32.dll', 'user32.dll', 'ntdll.dll', 'advapi32.dll'}
for fname in os.listdir(app_dir):
    if fname.lower().endswith(('.dll', '.txt')) and fname.lower() not in protected:
        dst = os.path.join(bin_dir, fname)
        if not os.path.exists(dst):
            shutil.copy2(os.path.join(app_dir, fname), dst)

# Always refresh Orbit_Pre.txt
shutil.copy2(os.path.join(app_dir, "Orbit_Pre.txt"), os.path.join(bin_dir, "Orbit_Pre.txt"))

if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(app_dir)
    os.add_dll_directory(bin_dir)
os.environ['PATH'] = bin_dir + os.pathsep + app_dir + os.pathsep + os.environ.get('PATH', '')

os.chdir(bin_dir)
print(f"CWD = {os.getcwd()}", flush=True)

model_desc = read_model_description(fmu_path, validate=False)
print(f"Model: {model_desc.modelName}", flush=True)

# Print all String vars and their default values
print("\n=== ALL STRING VARS ===")
for v in model_desc.modelVariables:
    t = getattr(v, 'type', None) or getattr(v, 'typeName', '')
    if t == 'String':
        print(f"  {v.name} ({v.causality}) = {getattr(v, 'start', '')!r}", flush=True)

fmu_inst = instantiate_fmu(
    unzipdir=extract_dir,
    model_description=model_desc,
    fmi_type='CoSimulation'
)
print("[OK] Instantiated", flush=True)

fmu_inst.setupExperiment(startTime=0.0)

# Override ONLY filepath
orbit_txt = os.path.abspath("Orbit_Pre.txt").replace('\\', '/')
for v in model_desc.modelVariables:
    t = getattr(v, 'type', None) or getattr(v, 'typeName', '')
    if t == 'String':
        s = getattr(v, 'start', '') or ''
        if 'Orbit_Pre.txt' in s:
            print(f"[*] Override filepath: {orbit_txt}", flush=True)
            fmu_inst.setString([v.valueReference], [orbit_txt])

# DO NOT set a_MT, e_MT, etc. – test if this is the cause
print("[*] enterInitializationMode...", flush=True)
fmu_inst.enterInitializationMode()
print("[*] exitInitializationMode...", flush=True)
fmu_inst.exitInitializationMode()
print("[OK] Init success!", flush=True)
fmu_inst.terminate()
fmu_inst.freeInstance()
