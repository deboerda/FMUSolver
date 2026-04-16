import zipfile, xml.etree.ElementTree as ET

fmu = r'C:\Spaceship\FmuSolver_Package\FMU\MTLibrary_System_EPS_PD_EPS_CJ.fmu'
with zipfile.ZipFile(fmu) as z:
    names = z.namelist()
    bins = [n for n in names if 'binaries' in n]
    print('Arch files:')
    for b in bins[:8]:
        print(' ', b)
    with z.open('modelDescription.xml') as f:
        tree = ET.parse(f)
root2 = tree.getroot()
print('\nString parameters:')
for sv in root2.findall('.//ScalarVariable'):
    s = sv.find('String')
    if s is not None:
        print(f"  {sv.get('name')} = {s.get('start','')!r}")
