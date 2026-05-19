import pefile
import os

def check_icon(exe_path):
    print(f"Checking {exe_path}...")
    if not os.path.exists(exe_path):
        print("File not found.")
        return
        
    try:
        pe = pefile.PE(exe_path)
        # Check for RT_GROUP_ICON (14) or RT_ICON (3)
        icon_found = False
        if hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
            for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
                if entry.id == 14: # RT_GROUP_ICON
                    print(f"Found RT_GROUP_ICON (14) in {exe_path}")
                    icon_found = True
                if entry.id == 3: # RT_ICON
                    print(f"Found RT_ICON (3) in {exe_path}")
                    icon_found = True
        
        if not icon_found:
            print("No icon resources found in the EXE.")
        else:
            print("Icon resources are present.")
            
        pe.close()
    except Exception as e:
        print(f"Error: {e}")

check_icon(r'c:\Spaceship\FMUSOLVER\FmuSolver_Package\FmuSolver.exe')
