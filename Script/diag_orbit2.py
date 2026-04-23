"""Diagnostic: verify variable types and test correct setters"""
import os, sys, zipfile, shutil
import fmpy
from fmpy import instantiate_fmu, read_model_description

app_dir  = r"C:\Spaceship\FmuSolver_Package"
fmu_path = r"C:\Spaceship\FMU\MTLibrary_System_EPS_PD_Orbit_Pre.fmu"
os.chdir(app_dir)

extract_dir = os.path.join(app_dir, "fmu_orbit_work")
os.makedirs(extract_dir, exist_ok=True)
with zipfile.ZipFile(fmu_path, 'r') as z:
    z.extractall(extract_dir)

arch    = "win32"
bin_dir = os.path.join(extract_dir, "binaries", arch)
shutil.copy2(os.path.join(app_dir, "Orbit_Pre.txt"), os.path.join(bin_dir, "Orbit_Pre.txt"))
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(bin_dir)
os.environ['PATH'] = bin_dir + os.pathsep + os.environ.get('PATH', '')
os.chdir(bin_dir)

model_desc = read_model_description(fmu_path, validate=False)

# Print types of the target parameters
target_names = ['Year', 'Mon', 'Day', 'Hour', 'Min', 'Sec',
                'a_MT', 'e_MT', 'i_MT', 'OMEGA_MT', 'omega_MT', 'f_MT']
print("=== TARGET VARIABLE TYPES ===", flush=True)
for v in model_desc.modelVariables:
    if v.name in target_names:
        t = getattr(v, 'type', None) or getattr(v, 'typeName', 'Unknown')
        print(f"  {v.name}: type={t!r}, causality={v.causality}, start={getattr(v,'start','')!r}", flush=True)

# Now test with correct type setters
fmu_inst = instantiate_fmu(unzipdir=extract_dir, model_description=model_desc, fmi_type='CoSimulation')
fmu_inst.setupExperiment(startTime=0.0)

# Override filepath
orbit_txt = os.path.abspath("Orbit_Pre.txt").replace('\\', '/')
for v in model_desc.modelVariables:
    t = getattr(v, 'type', None) or getattr(v, 'typeName', '')
    if t == 'String':
        s = getattr(v, 'start', '') or ''
        if 'Orbit_Pre.txt' in s:
            fmu_inst.setString([v.valueReference], [orbit_txt])
            print(f"[*] Override filepath OK", flush=True)

# Set params with CORRECT type
var_map = {v.name: v for v in model_desc.modelVariables if v.name in target_names}
int_values  = {'Year': 2024, 'Mon': 4, 'Day': 10, 'Hour': 8, 'Min': 0}
real_values = {'Sec': 0.0, 'a_MT': 6766.71777, 'e_MT': 0.0011,
               'i_MT': 0.72653, 'OMEGA_MT': 2.39969, 'omega_MT': 1.34409, 'f_MT': 1.00447}

for k, val in int_values.items():
    if k in var_map:
        t = getattr(var_map[k], 'type', None) or getattr(var_map[k], 'typeName', '')
        print(f"[*] Setting {k}={val} as type={t!r}", flush=True)
        if t == 'Integer':
            fmu_inst.setInteger([var_map[k].valueReference], [int(val)])
        else:
            fmu_inst.setReal([var_map[k].valueReference], [float(val)])

for k, val in real_values.items():
    if k in var_map:
        t = getattr(var_map[k], 'type', None) or getattr(var_map[k], 'typeName', '')
        print(f"[*] Setting {k}={val} as type={t!r}", flush=True)
        fmu_inst.setReal([var_map[k].valueReference], [float(val)])

print("[*] enterInitializationMode...", flush=True)
fmu_inst.enterInitializationMode()
print("[*] exitInitializationMode...", flush=True)
fmu_inst.exitInitializationMode()
print("[OK] SUCCESS!", flush=True)
fmu_inst.terminate()
fmu_inst.freeInstance()
