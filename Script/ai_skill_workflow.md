# [SKILL] FMU 仿真平台 AI 开发与编译标准作业流程 (SOP)

> [!IMPORTANT]
> 当用户要求“修改代码”、“修复 Bug”或“编译发布”时，AI 必须严格执行此流程。

## 1. 源码编辑阶段
*   **目标路径**: 所有代码编辑必须在 `c:\Spaceship\FMUSOLVER\Script\` 目录下进行。
*   **严禁操作**: 禁止修改 `FmuSolver_Package` 目录下的同名文件，除非是发布阶段的覆盖写入。

## 2. 逻辑验证阶段
*   **单元测试**: 修改完 `packet_parser.py` 或 `main.py` 等核心逻辑后，必须运行对应的测试脚本（如 `test_match_logic.py`）。
*   **环境自检**: 确保 `C:\Py32` (32位) 和系统 Python (64位) 环境均可用。

## 3. 编译发布阶段 (编译 EXE)
*   **前置动作**: 必须先运行 `clean_env.bat` 杀掉所有运行中的仿真进程，防止 `.exe` 被占用导致编译失败。
*   **执行编译**: 运行 `rebuild_all.bat`。
*   **发布目标**: 编译生成的 `.exe` 必须存放在 `c:\Spaceship\FMUSOLVER\FmuSolver_Package\` 中。
*   **检查清单**:
    - [x] `FmuSolver.exe` (64-bit)
    - [x] `YaoCe_LinkLayer.exe` (64-bit)
    - [x] `FmuWorker64.exe` (64-bit)
    - [x] `FmuWorker32.exe` (32-bit)
    - [x] `OrbitPreCalc32.exe` (32-bit)
    - [x] `DataVisualizer64.exe` (64-bit)
    - [x] `DataVisualizer32.exe` (32-bit)

## 4. 故障排除模式
*   如果编译报错“Path not found”，立即运行 `dir /s` 重新定位源码位置。
*   如果编译报错“Permission Denied”，重试 `clean_env.bat`。

---
*此 Skill 已由 Antigravity 固化，作为本项目的标准开发协议。*
