"""Final diagnostic: Year = default value, Mon+Day+Hour+Min+Sec+orbits without Year"""
import os, zipfile, shutil
import fmpy
from fmpy import instantiate_fmu, read_model_description

app_dir  = r"C:\Spaceship\FmuSolver_Package"
fmu_path = r"C:\Spaceship\FMU\MTLibrary_System_EPS_PD_Orbit_Pre.fmu"

os.chdir(app_dir)
extract_dir = os.path.join(app_dir, "fmu_orbit_work")
arch    = "win32"
bin_dir = os.path.join(extract_dir, "binaries", arch)
with zipfile.ZipFile(fmu_path, 'r') as z:
    z.extractall(extract_dir)
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(bin_dir)
os.environ['PATH'] = bin_dir + os.pathsep + os.environ.get('PATH', '')
shutil.copy2(os.path.join(app_dir, "Orbit_Pre.txt"), os.path.join(bin_dir, "Orbit_Pre.txt"))
os.chdir(bin_dir)
model_desc = read_model_description(fmu_path, validate=False)
var_map = {v.name: v for v in model_desc.modelVariables}
orbit_txt = os.path.abspath("Orbit_Pre.txt").replace('\\', '/')

# Print all Time/Date param default values
print("=== DATE/TIME PARAM DEFAULTS ===", flush=True)
for nm in ['Year','Mon','Day','Hour','Min','Sec']:
    v = var_map.get(nm)
    if v:
        print(f"  {nm}: start={getattr(v,'start','?')!r} variability={getattr(v,'variability','?')!r}", flush=True)

# Show first row of Orbit_Pre.txt for JD reference:
with open(os.path.join(app_dir, "Orbit_Pre.txt"), 'r') as f:
    for i, line in enumerate(f):
        if i < 5:
            print(f"  Orbit_Pre[{i}]: {line.strip()}", flush=True)

def try_init(label, extra_params):
    fmu_inst = instantiate_fmu(unzipdir=extract_dir, model_description=model_desc, fmi_type='CoSimulation')
    fmu_inst.setupExperiment(startTime=0.0)
    for v in model_desc.modelVariables:
        t = getattr(v, 'type', None) or getattr(v, 'typeName', '')
        if t == 'String':
            s = getattr(v, 'start', '') or ''
            if 'Orbit_Pre.txt' in s:
                fmu_inst.setString([v.valueReference], [orbit_txt])
    for k, val in extra_params.items():
        if k in var_map:
            fmu_inst.setReal([var_map[k].valueReference], [float(val)])
    try:
        fmu_inst.enterInitializationMode(); fmu_inst.exitInitializationMode()
        fmu_inst.terminate(); fmu_inst.freeInstance()
        print(f"  OK    {label}", flush=True); return True
    except:
        try: fmu_inst.terminate(); fmu_inst.freeInstance()
        except: pass
        print(f"  FAIL  {label}", flush=True); return False

print("\n=== TESTS ===", flush=True)
orbits = {"a_MT": 6766.71777, "e_MT": 0.0011, "i_MT": 0.72653, "OMEGA_MT": 2.39969, "omega_MT": 1.34409, "f_MT": 1.00447}
try_init("Year=2026 (default)", {"Year": 2026})
try_init("Mon+Day+Hour+Min+Sec (no Year)", {"Mon":4,"Day":10,"Hour":8,"Min":0,"Sec":0.0})
try_init("orbits only", orbits)
try_init("Mon+Day+orbits (no Year)", {"Mon":4,"Day":10,"Hour":8,"Min":0,"Sec":0.0, **orbits})
try_init("Year=2026+Mon+Day+orbits", {"Year":2026,"Mon":4,"Day":10,"Hour":8,"Min":0,"Sec":0.0, **orbits})
