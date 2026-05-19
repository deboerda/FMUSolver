import ctypes
import os

# Windows Constants
RT_ICON = 3
RT_GROUP_ICON = 14

def inject_icon(exe_path, ico_path):
    print(f"Directly injecting {ico_path} into {exe_path}...")
    if not os.path.exists(exe_path) or not os.path.exists(ico_path):
        print("Files not found.")
        return

    # Read ICO file
    with open(ico_path, 'rb') as f:
        ico_data = f.read()

    # Simple ICO parser to get frames
    # ICO Header: 2 bytes reserved (0), 2 bytes type (1), 2 bytes count
    count = int.from_bytes(ico_data[4:6], 'little')
    print(f"ICO contains {count} frames.")

    # Begin Update
    handle = ctypes.windll.kernel32.BeginUpdateResourceW(exe_path, False)
    if not handle:
        print("Failed to get update handle (is the EXE running?)")
        return

    try:
        # We need to build a new GRPICONDIR structure for the EXE
        # For simplicity, since PyInstaller usually does a decent job, 
        # we're just verifying that it exists.
        # But here we'll try to just overwrite the first icon group.
        
        # Actually, manually rebuilding GRPICONDIR is complex.
        # Let's try to just use PyInstaller's success but FORCE a refresh.
        pass
    finally:
        ctypes.windll.kernel32.EndUpdateResourceW(handle, False)

# Since pefile said it's already there, the issue is likely Shell Notification.
# We'll use SHChangeNotify to tell Windows to refresh icons.

def refresh_shell():
    print("Notifying Windows Shell to refresh icons...")
    # SHCNE_ASSOCCHANGED = 0x08000000
    # SHCNF_IDLIST = 0x0000
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)

refresh_shell()
