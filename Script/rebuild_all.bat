@echo off
set DIST_DIR=c:\Spaceship\FMUSOLVER\FmuSolver_Package
set PY32=C:\Py32\python.exe

echo [*] Starting Rebuild All (2026-04-29)...

:: 1. 64-bit Builds (System Python)
echo [+] Building FmuSolver.exe (64-bit)...
python -m PyInstaller --icon=C:\Spaceship\fmusolver.ico --noconfirm --onefile --windowed --name FmuSolver --workpath ./build --distpath . FmuLauncherUniversal.py

echo [+] Building YaoCe_LinkLayer.exe (64-bit)...
python -m PyInstaller --noconfirm --onefile --console --name YaoCe_LinkLayer --workpath ./build --distpath . yaocetest/main.py

echo [+] Building FmuSync_Controller.exe (64-bit)...
python -m PyInstaller --noconfirm --onefile --console --name FmuSync_Controller --workpath ./build --distpath . yaocetest/sync_control.py

echo [+] Building FmuWorker64.exe (64-bit)...
python -m PyInstaller --noconfirm --onefile --console --name FmuWorker64 --workpath ./build --distpath . fmu_player.py

:: 2. 32-bit Builds (C:\Py32 Python)
echo [+] Building FmuWorker32.exe (32-bit using %PY32%)...
%PY32% -m PyInstaller --noconfirm --onefile --console --name FmuWorker32 --workpath ./build32 --distpath . fmu_player.py

echo [+] Building OrbitPreCalc32.exe (32-bit using %PY32%)...
%PY32% -m PyInstaller --noconfirm --onefile --console --name OrbitPreCalc32 --workpath ./build32 --distpath . ../Script/orbit_pre_runner.py

echo [*] All builds completed.
