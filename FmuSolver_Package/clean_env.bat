@echo off
echo [*] Cleaning up FmuSolver environment...
taskkill /F /IM FmuSolver.exe /T 2>NUL
taskkill /F /IM FmuWorker32.exe /T 2>NUL
taskkill /F /IM FmuWorker64.exe /T 2>NUL
taskkill /F /IM OrbitPreCalc32.exe /T 2>NUL
taskkill /F /IM python.exe /T 2>NUL
echo [OK] All processes terminated.
pause
