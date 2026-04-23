import fmpy
import os

fmu = r'C:\Spaceship\FMU\MTLibrary_System_EPS_PD_Orbit_Pre.fmu'
md = fmpy.read_model_description(fmu)
# Get all Reals
reals = [v for v in md.modelVariables if getattr(v, 'type', None) == 'Real']

# Instead of searching, let's step the FMU twice
# and print what changed by how much.
# Wait, FMPy can simulate and return all variables.
res = fmpy.simulate_fmu(fmu, stop_time=20.0, step_size=10.0, output=[v.name for v in reals])

names = res.dtype.names
for name in names:
    if name == 'time': continue
    start_val = res[name][0]
    end_val = res[name][-1]
    if abs(start_val - end_val) > 1e-6:
        # It changed!
        # Check if its value matches something like a_MT (6766) or e_MT (0.0011)
        print(f"{name}: {start_val} -> {end_val}")

