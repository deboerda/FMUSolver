import fmpy

md = fmpy.read_model_description(r'C:\Spaceship\FMU\MTLibrary_System_EPS_PD_Orbit_Pre.fmu')

# Filter for Real variables
real_vars = [v for v in md.modelVariables if getattr(v, 'type', None) == 'Real' or getattr(v, 'typeName', '') == 'Real']

# We just want to see if any local/output variable has values close to 6766 etc
print('Total real vars:', len(real_vars))
