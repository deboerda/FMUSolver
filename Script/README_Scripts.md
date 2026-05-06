# FMU 仿真平台脚本说明文档 (Script README)

> [!TIP]
> **AI 开发指南**: 本项目的开发、测试与发布遵循 [ai_skill_workflow.md](file:///c:/Spaceship/FMUSOLVER/Script/ai_skill_workflow.md) 中的标准流程。请 AI 在操作前务必阅读该 Skill。

本目录集成了 FMU 仿真平台的所有核心源码、辅助工具以及编译发布脚本，便于进行版本控制与二次开发。

## 1. 核心仿真组件

### 1.1 主控界面 (FmuLauncherUniversal.py)
*   **对应程序**: `FmuSolver.exe` (64-bit)
*   **功能**: 平台的主入口。负责加载 `.fmu` 模型文件、解析 FMU 变量列表、管理仿真步长/速率等参数，并负责启动和管理各个子进程（Worker、LinkLayer）。
*   **关键特性**:
    *   动态自适应 32/64 位 FMU 架构自动切换。
    *   脉冲式“同步”按钮逻辑（0->1->0）。

### 1.2 仿真运行器 (fmu_player.py)
*   **对应程序**: `FmuWorker32.exe` / `FmuWorker64.exe`
*   **功能**: 实际加载并运行 FMU DLL 的核心驱动程序。
*   **逻辑**: 接收主控端的参数指令，通过 `fmpy` 库执行高精度时间步进，并将仿真状态通过 UDP 以 DDM 格式回传。
*   **注意**: 32 位版本使用 `C:\Py32` 环境编译，以兼容 32 位底层 DLL。

### 1.3 轨道预报工具 (orbit_pre_runner.py)
*   **对应程序**: `OrbitPreCalc32.exe` (32-bit)
*   **功能**: 负责在仿真开始前进行高精度的轨道外推计算，生成供 FMU 调用的数据文件。

---

## 2. 遥测与数据链路

### 2.1 遥测转发网桥 (main.py / YaoCe_Main)
*   **对应程序**: `YaoCe_LinkLayer.exe` (64-bit)
*   **功能**: 遥测链路层，负责接收外部 UDP 遥测数据包，解析并根据白名单过滤。
*   **核心逻辑**: 
    *   使用 `packet_parser.py` 进行协议脱壳。
    *   将结果打包为 Google Protobuf (DDM) 格式发送给仿真器。

### 2.2 协议解析器 (packet_parser.py)
*   **功能**: 遥测协议解析库，支持正则表达式提取变长参数 ID（如 `TPALLS0067`），处理 ID 与数值粘连等异常情况。

### 2.3 配置管理器 (config_manager.py)
*   **功能**: 负责加载 `ParamFilter.xml`（参数白名单）和 `config.ini`。支持数字后缀模糊匹配规则。

### 2.4 同步注入控制器 (sync_control.py)
*   **对应程序**: `FmuSync_Controller.exe`
*   **功能**: 独立运行的注入控制器，负责实时接收遥测解析结果并注入到正在运行的 FMU 实例中。

---

## 3. 开发与部署工具

### 3.1 一键编译脚本 (rebuild_all.bat)
*   **作用**: 自动化执行 PyInstaller 编译流程。
*   **逻辑**:
    1.  检测并使用系统默认 Python 编译 64 位组件。
    2.  检测并使用 `C:\Py32` 环境编译 32 位组件（Worker、OrbitPre）。
*   **发布**: 编译后的 `.exe` 会自动生成/更新在 `FmuSolver_Package` 根目录下。

### 3.2 环境清理工具 (clean_env.bat)
*   **作用**: 强制结束所有残留的仿真和遥测进程（FmuSolver, YaoCe, Worker 等），清理死锁端口。

---

## 4. 辅助测试工具
*   `replay_telemetry.py`: 遥测回放工具，可加载历史 `.log` 文件模拟现场遥测流。
*   `sniff_test.py`: 端口监听测试工具，用于调试 UDP 报文是否通畅。
*   `ddm_pb2.py`: DDM 协议的 Protobuf 自动生成代码。

---

## 5. 版本控制建议
*   **提交内容**: 仅提交 `.py`、`.bat`、`.spec`、`.xml` 和 `.ini` 等源码文件。
*   **排除内容**: 建议在 `.gitignore` 中排除 `build/`、`dist/` 文件夹以及巨大的 `.exe` 文件（如果空间有限）。

---
*Last Updated: 2026-04-29*
