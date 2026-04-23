"""Find mode-switch parameter and test hPOP.Is_initial"""
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
os.chdir(bin_dir)

model_desc = read_model_description(fmu_path, validate=False)

# 1. Print ALL Boolean/Integer parameters
print("=== BOOLEAN / INTEGER / INIT-RELATED PARAMS ===", flush=True)
for v in model_desc.modelVariables:
    t      = getattr(v, 'type', None) or getattr(v, 'typeName', '')
    name   = v.name
    start  = getattr(v, 'start', '')
    caus   = v.causality
    var    = getattr(v, 'variability', '')
    # Show all non-Real params + anything with 'init', 'mode', 'online', 'flag' in name
    if t in ('Boolean', 'Integer') or any(k in name.lower() for k in ['init', 'mode', 'online', 'flag', 'switch', 'enable', 'is_']):
        print(f"  [{t}] {name} ({caus},{var}) = {start!r}", flush=True)

# 2. Look for hPOP.Is_initial or similar
var_map = {v.name: v for v in model_desc.modelVariables}
print("\n=== hPOP.* PARAMS (first 30) ===", flush=True)
hpop_vars = [(v.name, getattr(v,'type',None), getattr(v,'start',''), v.causality) 
             for v in model_desc.modelVariables if v.name.startswith('hPOP.')]
for nm, t, s, c in hpop_vars[:30]:
    print(f"  {nm} [{t}] ({c}) = {s!r}", flush=True)
