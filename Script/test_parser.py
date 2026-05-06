import json

# Mocking the variable list
class MockVar:
    def __init__(self, name):
        self.name = name
        self.valueReference = 123

vars_list = []
for k in ["Table_A", "Table_B", "Table_FB", "Table_Att"]:
    for i in range(1, 5):
        for j in range(1, 5):
            vars_list.append(MockVar(f"{k}[{i},{j}]"))

init_params = {
    "Table_A": "1000, 3640; 2000, 3640",
    "Table_B": "1000, 3640; 2000, 3640",
    "Table_FB": "1000, 360, 184; 2000, 360, 184",
    "Table_Att": "1000, 0, 3, 90; 2000, 0, 3, 90"
}

print("[*] Injecting initialization parameters...")
for k, v in init_params.items():
    if k.startswith("Table_"):
        try:
            rows = [r.split(',') for r in str(v).split(';') if r.strip()]
            if rows:
                for i, row in enumerate(rows):
                    for j, val in enumerate(row):
                        cands = [f"{k}[{i+1},{j+1}]", f"{k}[{i+1}, {j+1}]"]
                        v_obj = next((mv for mv in vars_list if mv.name in cands), None)
                        if v_obj:
                            # fmu_instance.setReal([v_obj.valueReference], [float(val.strip())])
                            pass
                print(f"[OK] Parsed and injected table {k} ({len(rows)}x{len(rows[0])})")
        except Exception as e:
            print(f"[!] Error parsing table {k}: {e}")
