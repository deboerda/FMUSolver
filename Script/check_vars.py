import fmpy

md = fmpy.read_model_description(r'C:\Spaceship\FMU\MTLibrary_System_EPS_PD_Orbit_Pre.fmu')
for v in md.modelVariables:
    name = v.name
    desc = getattr(v, 'description', '') or ''
    if name in ['Day_num', 'JulianDay', 'JD', 'julian_day', '儒略日'] or 'day' in name.lower() or 'julian' in desc.lower() or '儒略日' in desc:
        print(f"{name} ({v.causality}) - {desc}")
