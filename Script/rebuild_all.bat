@echo off
set DIST_DIR=c:\Spaceship\FMUSOLVER\FmuSolver_Package
set PY32=C:\Py32\python.exe

echo [*] Starting Comprehensive CLEAN Rebuild (32/64-bit)...

echo [+] Updating visible build version...
python update_build_version.py
if errorlevel 1 exit /b 1

:: 0. Clean old build artifacts
echo [+] Cleaning old build artifacts...
if exist "build" rd /s /q "build"
if exist "build32" rd /s /q "build32"
if exist "dist" rd /s /q "dist"
if exist "__pycache__" rd /s /q "__pycache__"
if exist "%DIST_DIR%\FmuLauncher_Universal.exe" del /q "%DIST_DIR%\FmuLauncher_Universal.exe"
if exist "%DIST_DIR%\raw_record_*.log" del /q "%DIST_DIR%\raw_record_*.log"
if exist "%DIST_DIR%\worker_fatal.log" del /q "%DIST_DIR%\worker_fatal.log"
if exist "%DIST_DIR%\sys_argv.log" del /q "%DIST_DIR%\sys_argv.log"

:: 1. 64-bit Builds (System Python)
echo [+] Building 64-bit Components...
python -m PyInstaller --noconfirm FmuSolver.spec
python -m PyInstaller --noconfirm --onefile --console --name FmuWorker64 --workpath ./build --distpath ./dist fmu_player.py
python -m PyInstaller --noconfirm --onefile --console --name OrbitPreCalc64 --workpath ./build --distpath ./dist orbit_pre_runner.py
python -m PyInstaller --noconfirm --onefile --console --name YaoCe_LinkLayer64 --workpath ./build --distpath ./dist yaocetest/main.py
python -m PyInstaller --noconfirm --onefile --windowed --name DataVisualizer64 --workpath ./build --distpath ./dist DataVisualizerPython.py

:: 2. 32-bit Builds (C:\Py32 Python)
echo [+] Building 32-bit Components...
%PY32% -m PyInstaller --noconfirm --onefile --console --name FmuWorker32 --workpath ./build32 --distpath ./dist fmu_player.py
%PY32% -m PyInstaller --noconfirm --onefile --console --name OrbitPreCalc32 --workpath ./build32 --distpath ./dist orbit_pre_runner.py
%PY32% -m PyInstaller --noconfirm --onefile --console --name YaoCe_LinkLayer32 --workpath ./build32 --distpath ./dist yaocetest/main.py
%PY32% -m PyInstaller --noconfirm --onefile --windowed --name DataVisualizer32 --workpath ./build32 --distpath ./dist DataVisualizerPython.py

:: 3. Packaging
echo [+] Packaging final distribution...
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"
if not exist "%DIST_DIR%\Visualizer" mkdir "%DIST_DIR%\Visualizer"

:: Copy all from dist to package
copy /Y ".\dist\FmuSolver.exe" "%DIST_DIR%\"
copy /Y ".\dist\FmuWorker64.exe" "%DIST_DIR%\"
copy /Y ".\dist\FmuWorker32.exe" "%DIST_DIR%\"
copy /Y ".\dist\OrbitPreCalc64.exe" "%DIST_DIR%\"
copy /Y ".\dist\OrbitPreCalc32.exe" "%DIST_DIR%\"
copy /Y ".\dist\YaoCe_LinkLayer64.exe" "%DIST_DIR%\"
copy /Y ".\dist\YaoCe_LinkLayer32.exe" "%DIST_DIR%\"
copy /Y ".\dist\DataVisualizer64.exe" "%DIST_DIR%\Visualizer\"
copy /Y ".\dist\DataVisualizer32.exe" "%DIST_DIR%\Visualizer\"

:: Sync source snapshots for debugging/reference, avoid stale duplicate scripts in package
copy /Y ".\FmuLauncherUniversal.py" "%DIST_DIR%\"
copy /Y ".\DataVisualizerPython.py" "%DIST_DIR%\"

:: Sync FMU Models
if not exist "%DIST_DIR%\FMU" mkdir "%DIST_DIR%\FMU"
copy /Y "c:\Spaceship\FMU\*.fmu" "%DIST_DIR%\FMU\"

:: Sync Configs
copy /Y sync_fields.json "%DIST_DIR%\"
copy /Y gui_config.json "%DIST_DIR%\"
copy /Y fmusolver_full.ico "%DIST_DIR%\"

echo [*] Full Clean Build Completed.
echo [*] Launch packaged app with "%DIST_DIR%\FmuSolver.exe". Do NOT use legacy "%DIST_DIR%\FmuLauncher_Universal.exe".
pause
