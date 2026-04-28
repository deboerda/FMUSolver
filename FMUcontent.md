我为你整理了一份详尽的 \*\*FmuSolver 项目部署与开发说明报告\*\*。这份文档涵盖了目前的架构设计、核心脚本功能、打包流程以及未来如何更换模型的指导，建议你妥善保存。



\# FmuSolver 项目部署与技术报告



\## 1. 项目核心架构

本项目采用 \*\*Sidecar (边车) 架构\*\*，解决了 Python 无法在一个进程内同时加载 32 位和 64 位动态库（DLL）的局限：

\*   \*\*主程序 (`FmuSolver.exe`)\*\*：64 位 GUI 界面，负责用户交互和调度。

\*   \*\*计算网桥 (`FmuWorker32/64.exe`)\*\*：根据 FMU 模型的架构，自动启动对应的网桥进程进行仿真。

\*   \*\*轨道引擎 (`OrbitPreCalc32.exe`)\*\*：专门针对 32 位轨道预示模型开发的离线计算模块。



\---



\## 2. 重要目录与脚本说明



\### 核心源码目录 (`/Script`)

| 文件名 | 功能描述 |

| :--- | :--- |

| `FmuLauncherUniversal.py` | \*\*项目总入口\*\*。包含 GUI 逻辑、子进程分发逻辑、路径动态识别逻辑。 |

| `fmu\_player.py` | \*\*仿真核心库\*\*。处理 FMI 接口调用、UDP 数据 Protobuf 打包、Base64 编解码控制。 |

| `worker\_entry.py` | \*\*网桥入口\*\*。极简脚本，用于被 PyInstaller 编译成 32/64 位独立的 Worker。 |

| `orbit\_pre\_runner.py` | \*\*轨道计算核心\*\*。包含 Julian Date 转换、种子文件生成、离线外推逻辑。 |

| `ddm\_pb2.py` | 根据 `ddm.proto` 生成的 Protobuf 序列化代码。 |



\### 遥测网桥目录 (`/yaocetest`)

该模块负责接收底层十六进制原始数据并转为仿真平台可识别的数值。

\*   \*\*`main.py`\*\*：遥测转发主逻辑，已加固对 `0.0.0.0` 的监听和 `1MB` 缓冲区。

\*   \*\*`packet\_parser.py`\*\*：二进制协议解析器，处理包头、包尾识别及数据拆解。

\*   \*\*`config\_manager.py`\*\*：实现 ID 模糊匹配逻辑（如 `S1234` 匹配 `N1234`）。

\*   \*\*`ParamFilter.xml`\*\*：参数过滤白名单。



\---



\## 3. 自动化打包指南

如果后续修改了 Python 源码，请按照以下指令重新编译：



\### 准备工作

\*   环境 A：Python 64-bit (系统默认)

\*   环境 B：Python 32-bit (安装在 `C:\\Py32\\python.exe`)



\### 打包命令 (在 `/Script` 目录下执行)

1\.  \*\*打包主程序 (64位)\*\*:

&#x20;   `python -m PyInstaller --onefile --noconsole --name FmuSolver --icon satellite\_icon\_149794.ico FmuLauncherUniversal.py`

2\.  \*\*打包 32 位网桥\*\*:

&#x20;   `C:\\Py32\\python.exe -m PyInstaller --onefile --name FmuWorker32 --icon satellite\_icon\_149794.ico worker\_entry.py`

3\.  \*\*打包 64 位网桥\*\*:

&#x20;   `python -m PyInstaller --onefile --name FmuWorker64 --icon satellite\_icon\_149794.ico worker\_entry.py`

4\.  \*\*打包轨道专用引擎\*\*:

&#x20;   `C:\\Py32\\python.exe -m PyInstaller --onefile --name OrbitPreCalc32 --icon satellite\_icon\_149794.ico orbit\_pre\_runner.py`



\---



\## 4. 后续更换模型指南

当你需要更换新的 FMU 模型时，请遵循以下步骤：



\### 第一步：模型部署

将新的 `.fmu` 文件放入部署包的 `FMU/` 文件夹下。



\### 第二步：配置更新

1\.  \*\*修改 `ParamFilter.xml`\*\*：如果新模型的参数 ID 发生了变化，需要在此文件中更新 `code`（原始 ID）和 `name`（映射后的变量名）的对应关系。

2\.  \*\*修改 `sync\_fields.json`\*\*：此文件控制 GUI 界面上“字段配置”页面的默认显示。

&#x20;   \*   `name`: 必须与 FMU 模型内部的变量全名完全一致。

&#x20;   \*   `sync`: 设为 `true` 表示默认开启 UDP 转发。



\### 第三步：路径自动识别

由于我们已经修复了硬编码问题，主程序启动后会自动在 `FMU/` 目录下搜索模型。如果模型文件名变化了，只需要在 GUI 界面的“浏览”按钮中重新选择一次即可。



\---



\## 5. 现场故障排查工具箱

在客户现场，如果遇到无法通讯或报错，请依次运行以下工具：



1\.  \*\*`clean\_env.bat`\*\*：\*\*首选工具\*\*。强制关闭所有残留的网桥和端口占用，解决 `WinError 10048`。

2\.  \*\*`sniff\_test.py`\*\*：\*\*网络诊断\*\*。用于测试 `30019` 端口是否能绕过防火墙接收到 UDP 数据。

3\.  \*\*`replay\_telemetry.py`\*\*：\*\*模拟测试\*\*。在没有硬件的环境下，回放历史日志来验证整个链路是否通畅。



\---



\### 打包部署包结构建议：

```text

FmuSolver\_Package/

├── FmuSolver.exe (主程序)

├── FmuWorker32.exe (32位网桥)

├── FmuWorker64.exe (64位网桥)

├── OrbitPreCalc32.exe (轨道引擎)

├── clean\_env.bat (环境清理)

├── MWSolver.dll (核心算解库)

├── FMU/ (存放所有 .fmu 模型文件)

└── yaocetest/ (配置文件与诊断脚本)

&#x20;   ├── ParamFilter.xml

&#x20;   ├── config.ini

&#x20;   └── sniff\_test.py

```



这份报告可以作为交付文档的一部分提供给现场工程人员。



如果你准备将本项目的信息提供给另一个 AI 模型（例如用于后续的代码审查、功能扩展或故障排查），可以使用下面这份专门整理的\*\*技术上下文概要（AI-Ready Context）\*\*。



这份概要采用结构化的技术描述，能够帮助 AI 快速理解系统的底层架构和演进过程：



\---



\# FmuSolver System Context \& Architecture Overview



\## 1. Project Identity

\*\*Project Name:\*\* FmuSolver Universal Platform

\*\*Core Function:\*\* A hybrid-architecture simulation platform that integrates FMU (Functional Mock-up Unit) models with real-world telemetry data via UDP/Protobuf. It supports both real-time simulation and offline orbit prediction.



\## 2. Technical Stack

\*   \*\*Language:\*\* Python 3.x (64-bit main, 32-bit worker)

\*   \*\*GUI:\*\* Tkinter (Custom themed)

\*   \*\*Simulation Standard:\*\* FMI 2.0 (via `fmpy`)

\*   \*\*Protocols:\*\* UDP, Protobuf (Binary), Base64 (Optional/Removed)

\*   \*\*Packaging:\*\* PyInstaller (One-file mode)



\## 3. Sidecar Architecture (Multi-Arch Solution)

To bypass Python's Global Interpreter Lock (GIL) and the inability to load mixed-bitness DLLs in a single process:

\*   \*\*Orchestrator (64-bit):\*\* `FmuLauncherUniversal.py` manages the UI and detects FMU architecture.

\*   \*\*Sidecar Workers (32/64-bit):\*\* `worker\_entry.py` (compiled to `FmuWorker32/64.exe`) handles the actual FMI execution and low-level DLL loading (`MWSolver.dll`).

\*   \*\*IPC:\*\* Standard Output (STDOUT) for logging, UDP for real-time parameter injection and data synchronization.



\## 4. Key Sub-Modules

\### A. YaoCe Telemetry Bridge (`/yaocetest`)

\*   \*\*Purpose:\*\* Converts raw binary telemetry streams into `DDMData` Protobuf messages.

\*   \*\*Logic:\*\* Implements a fuzzy matching algorithm in `ConfigManager` to map dynamic IDs (e.g., `S1234`/`T1234`) to fixed XML definitions using numeric-suffix indexing.

\*   \*\*Hardening:\*\* Explicit `0.0.0.0` binding, `1MB` RCVBUF, and space-agnostic hex parsing.



\### B. Orbit Engine (`orbit\_pre\_runner.py`)

\*   \*\*Capability:\*\* Offline high-precision orbit propagation.

\*   \*\*Mechanism:\*\* Generates a seed `Orbit\_Pre.txt` containing Julian Date (JD) and 6 orbital elements, injects it into the FMU, and exports results to JSON/TXT.



\## 5. Major Solved Anomalies (Technical Debt Cleared)

1\.  \*\*Path Portability:\*\* Refactored from absolute `C:\\Spaceship` paths to `APP\_DIR` relative paths for cross-drive deployment.

2\.  \*\*Hex-to-Float Corruption:\*\* Restricted hex string parsing to `len <= 8` to prevent long status strings from being interpreted as astronomical numbers.

3\.  \*\*Data Mismatch:\*\* Removed Base64 encoding over UDP to align with raw binary `struct` expectations of downstream communication centers.

4\.  \*\*Resource Conflict:\*\* Implemented `clean\_env.bat` to resolve `WinError 10048` caused by zombie worker processes.



\## 6. Deployment Inventory

\*   \*\*Executables:\*\* `FmuSolver.exe`, `FmuWorker32.exe`, `FmuWorker64.exe`, `OrbitPreCalc32.exe`.

\*   \*\*Configs:\*\* `ParamFilter.xml` (Filtering), `config.ini` (Network), `sync\_fields.json` (UI state).

\*   \*\*Assets:\*\* `FMU/` (Models), `MWSolver.dll` (Engine), `satellite\_icon\_149794.ico`.



\---



\*\*AI Instruction Tip:\*\* 

> "Please analyze this system context to understand how the 64-bit GUI coordinates with 32-bit worker processes. Focus on the UDP bridge's parameter mapping logic if you need to extend the telemetry parsing."

