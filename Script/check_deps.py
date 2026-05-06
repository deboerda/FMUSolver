import sys
import struct

def get_dll_imports(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    
    # PE Header offset at 0x3C
    pe_offset = struct.unpack('<I', data[0x3C:0x40])[0]
    # Import Directory RVA at PE_OFFSET + 0x80 (for 32-bit PE)
    import_dir_rva = struct.unpack('<I', data[pe_offset+0x80:pe_offset+0x84])[0]
    
    # This is a very simplified PE parser, might fail on complex files
    # But let's just search for common DLL strings as a fallback
    import re
    dlls = re.findall(rb'[a-zA-Z0-9_\.]+\.[dD][lL][lL]', data)
    return sorted(list(set([d.decode('ascii', 'ignore') for d in dlls])))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(f"[*] Dependencies for {sys.argv[1]}:")
        for d in get_dll_imports(sys.argv[1]):
            print(f"  - {d}")
