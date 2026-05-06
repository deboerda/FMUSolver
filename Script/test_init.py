import subprocess
import sys
import json

args = [
    sys.executable,
    "fmu_player.py",
    r"C:\Spaceship\FMUSOLVER\FmuSolver_Package\FMU\MTLibrary_System_EPS_PD_EPS_CJ.fmu",
    "--step", "0.02",
    "--rate", "0",
    "--freq", "50.0",
    "--time", "5.0",
    "--sim_id", "123",
    "--params", json.dumps({
        "Year": 2026, "Mon": 3, "Day": 31, "Hour": 12, "Min": 19, "Sec": 0.0,
        "Table_A": "1000, 3640; 2000, 3640",
        "Table_B": "1000, 3640; 2000, 3640",
        "Table_FB": "1000, 360, 184; 2000, 360, 184",
        "Table_Att": "1000, 0, 3, 90; 2000, 0, 3, 90",
        "PointSun": 0.0
    }),
    "--control_port", "8898"
]

import os
env = os.environ.copy()
env["TEMP"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_local_temp")
env["TMP"] = env["TEMP"]
os.makedirs(env["TEMP"], exist_ok=True)

print("[*] Running test...")
p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
for line in iter(p.stdout.readline, ''):
    print(line.strip())
p.wait()
print(f"[*] Exit code: {p.returncode}")
