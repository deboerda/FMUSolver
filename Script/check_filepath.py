import fmpy
md = fmpy.read_model_description(r'C:\Spaceship\FMU\MTLibrary_System_EPS_PD_Orbit_Pre.fmu')
for v in md.modelVariables:
    if v.name == 'filepath':
        print(v.name, getattr(v, 'start', ''))
