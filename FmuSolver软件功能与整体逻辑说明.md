# FmuSolver 软件功能与整体逻辑说明

本文档用于说明 FmuSolver 当前版本的软件用途、主要功能、模块关系、数据流向和典型使用流程。它面向测试人员、使用人员和后续维护人员，重点解释“这个软件由哪些部分组成、每部分做什么、数据如何在 FMU、PE、遥测和看板之间流转”。

## 1. 软件定位

FmuSolver 是一个面向工业数字孪生与航空航天相邻（非密）能源 / 轨道类模型的 FMU 仿真控制平台。它的核心作用是加载 FMU 模型，控制实时仿真或轨道预示计算，并把仿真结果、遥测数据和外部注入变量通过 UDP/Protobuf 在不同系统之间转发。

从用户视角看，它主要解决四类问题：

- 启动和控制实时 FMU 仿真，包括开始、暂停、继续、停止、变量注入和结果转发。
- 执行轨道预示计算，生成或更新 `Orbit_Pre.txt`，供后续模型或外部系统使用。
- 接收遥测数据，将遥测 code 映射为 FMU 变量名后，既可注入 FMU，也可转发给 PE。
- 启动数据看板，查看实时变量曲线，保存布局预设，并将图表截图导出到 Word。

## 2. 软件组成

当前软件主要由以下部分组成：

| 模块 | 典型文件 | 作用 |
| --- | --- | --- |
| 主界面 | `FmuLauncherUniversal.py` / `FmuSolver.exe` | 提供轨道预示、实时仿真、遥测转发三大操作页签，负责启动子进程和统一调度。 |
| 实时仿真 Worker | `fmu_player.py` / `FmuWorker32.exe` / `FmuWorker64.exe` | 解压 FMU、加载 DLL、执行 `doStep()`、处理暂停/继续/变量注入、向 PE 和看板发送仿真数据。 |
| 轨道预示 Worker | `orbit_pre_runner.py` / `OrbitPreCalc32.exe` / `OrbitPreCalc64.exe` | 调用轨道预示 FMU，按时间和轨道参数计算未来轨道数据，并导出 `Orbit_Pre.txt`。 |
| 遥测桥接 | `yaocetest/main.py` / `YaoCe_LinkLayer32.exe` / `YaoCe_LinkLayer64.exe` | 接收遥测 UDP 包，按白名单过滤，按关系 XML 映射为 FMU 变量名，再转发给 PE 和 FMU 注入端口。 |
| 数据看板 | `DataVisualizerPython.py` / `DataVisualizer64.exe` | 接收本地仿真数据，展示变量表格和曲线，支持多画布、预设记忆、累积趋势和 Word 导出。 |
| 通信协议 | `ddm.proto` / `ddm_pb2.py` | 定义 DDMData、SimVar、TmVar、FcVar 等 Protobuf 数据结构。 |
| 配置文件 | `gui_config.json`、`sync_fields.json`、`ParamFilter.xml`、`DTS.TM.Sim.Relationship.xml` | 保存界面配置、变量筛选、遥测白名单和遥测到仿真变量的映射关系。 |

## 3. 主界面三大功能页

### 3.1 轨道预示计算

轨道预示计算用于提前根据初始时间、六根数和轨道预示 FMU 生成未来一段时间的轨道数据。该功能通常用于生成或更新 `Orbit_Pre.txt`，供实时仿真 FMU 或外部系统读取。

主要功能包括：

- 选择轨道预示 FMU，例如 `（示例 FMU 名已脱敏）`。
- 输入北京时形式的历元时间。
- 输入六根数参数，包括半长轴、偏心率、倾角、升交点赤经、近地点幅角和真近点角。
- 六根数角度项在界面上按“度”显示，并按界面数值原样传入 FMU，不再自动转换为弧度。
- 设置步长、采样频率、计算时长和运行速率。
- 支持开始、暂停/继续、停止和导出。

轨道预示运行逻辑如下：

1. 主界面收集轨道参数并启动 `orbit_pre_runner.py` 或对应 EXE。
2. Worker 解压轨道 FMU 到运行目录。
3. Worker 生成种子 `Orbit_Pre.txt` 或使用已有种子文件。
4. Worker 调用轨道 FMU 逐步计算轨道数据。
5. 计算完成后导出结果 JSON，并生成/同步 `Orbit_Pre.txt`。
6. 主界面读取结果，支持用户另存导出。

### 3.2 实时仿真控制

实时仿真控制用于运行能源/载荷相关 FMU 模型，并按配置向 PE 和本地看板发送实时变量。

主要功能包括：

- 选择实时仿真 FMU，例如 `（示例 FMU 名已脱敏）` 或 NoShelter 版本。
- 配置 PE 接收 IP 和端口。
- 配置变量注入监听地址和端口，默认常见端口为 `9988`，也会兼容部分配置中的 `8888`。
- 配置仿真初始时间、初始表格参数、PointSun 等初始化参数。
- 配置步长、采样频率、仿真时长和仿真速率。
- 支持开始、暂停/继续、停止、同步、变量配置、打开看板和打开输出包。

实时仿真页中的 `PointSun` 和 `Is_initial` 含义不同，使用时需要区分：

- `PointSun` 对应界面中的“Alpha轴对日定向 (PointSun)”复选框，是仿真启动前的初始化配置。用户在启动仿真前勾选或取消，启动后不再通过同步按钮动态修改。
- `Is_initial` 是 FMU 输入变量 `input Real Is_initial "同步信号"`，用于运行过程中的天地状态同步脉冲。点击“同步”按钮时，主界面只对 `Is_initial` 发送 `1.0 -> 0.0` 脉冲，不再操作 `PointSun`。

实时仿真运行逻辑如下：

1. 主界面根据 FMU 架构自动选择 32 位或 64 位 Worker。
2. Worker 为每次仿真创建独立运行目录，避免旧 DLL 文件锁导致新模型解压失败。
3. Worker 解压 FMU，读取 `modelDescription.xml`，加载对应 DLL。
4. Worker 根据 `sync_fields.json` 建立输出变量白名单。
5. Worker 执行 FMU 初始化参数注入。
6. Worker 进入仿真循环，执行 `doStep()`。
7. Worker 按采样频率读取变量，并通过 UDP/Protobuf 发送到 PE 和本地看板。
8. 主界面通过控制端口发送暂停、继续、停止、速率调整和变量注入命令。

暂停逻辑现在采用双保险：

- UDP 控制命令通知 Worker 暂停或继续。
- 主界面同时创建或删除 `sim_pause_<id>.flag` 文件，Worker 每轮检查该文件，确保即使高频注入消息存在，暂停也不会被覆盖。

### 3.3 遥测接收转发

遥测接收转发用于接收外部遥测 UDP 数据，并把遥测 code 转换为 FMU 使用的仿真变量名。

主要功能包括：

- 选择遥测配置目录，目录中应包含 `config.ini`、`ParamFilter.xml` 和可选的 `DTS.TM.Sim.Relationship.xml`。
- `ParamFilter.xml` 用于定义允许处理的遥测 code 白名单。
- `DTS.TM.Sim.Relationship.xml` 用于定义遥测 code 到 FMU 变量名的对应关系。
- 遥测页提供 `DTS关系配置` 按钮，可直接打开当前配置目录下的 `DTS.TM.Sim.Relationship.xml`，用于查看或编辑遥测到仿真变量的对应关系。
- 遥测数据会同时走两条路径：一条转发给 PE，一条转发给本机 FMU 注入监听端口。

例如关系文件中：

```xml
<Var init_var="false" sim_var="Beta_Online[2]" desc="右帆板Beta转角信息" expression="#(TGMTC101.DAHE@K0189)"/>
```

表示遥测 code `K0189` 对应 FMU 变量 `Beta_Online[2]`。遥测桥接收到 `K0189` 后，不再以 `K0189` 作为变量名发出，而是以 `Beta_Online[2]` 作为 `SimVar.name` 发出。

遥测桥接运行逻辑如下：

1. 读取 `config.ini`，获取遥测接收端口和默认目标配置。
2. 如果主界面配置了统一 PE 目标，则遥测和仿真统一发往该 PE 端口。
3. 同时保留本机 FMU 注入目标，默认指向主界面的变量注入监听端口。
4. 读取 `ParamFilter.xml`，建立遥测白名单。
5. 读取 `DTS.TM.Sim.Relationship.xml`，建立 `code -> sim_var` 映射。
6. 接收遥测包，解析出 code 和数值。
7. 白名单通过后，将 code 映射成 FMU 变量名。
8. 组装 DDM Protobuf 包，分别发送到 PE 和本机注入端口。

## 4. 数据看板功能

数据看板用于查看实时仿真变量和 PE/遥测注入变量的曲线趋势。

主要功能包括：

- 显示变量列表和最新值。
- 创建多个绘图窗口。
- 支持绘图窗口布局记忆和看板预设。
- 支持折叠配置面板后画布铺满。
- 支持鼠标左键框选缩放。
- 支持鼠标滚轮/中键拖动画布。
- 支持实时滚动曲线和累积趋势模式。
- 累积趋势模式用于观察长期趋势，会进行降采样和压缩以降低卡顿。
- 支持导出当前图表截图到 Word。

看板数据来源有两类：

| 来源 | 变量来源 | 是否经过变量配置筛选 | 看板中的变量名 |
| --- | --- | --- | --- |
| FMU 实时输出 | Worker 从 FMU 中读取的变量 | 是，经过 `sync_fields.json` 筛选 | 原变量名或配置别名 |
| PE 注入数据 | PE 发给 FMU 的输入变量 | 否，不需要写入 `sync_fields.json`，收到后动态加入看板变量栏 | `PE.` 前缀变量，例如 `PE.SolarAngle_CJinput[1]` |
| 遥测注入数据 | 遥测桥接发给 FMU 的输入变量 | 否，不需要写入 `sync_fields.json`，收到后动态加入看板变量栏 | `YC.` 前缀变量，例如 `YC.Beta_Online[2]` |

需要注意：看板不会自动显示 FMU 的全部 3 万多个变量。FMU 输出变量由 `sync_fields.json` 控制；PE 和遥测输入变量不应为了显示而加入 `sync_fields.json`，否则可能被误当作 FMU 输出变量再次转发。当前逻辑是收到 PE/遥测输入后直接动态加入看板变量栏，仅用于显示和绘图。

`PE.` 与 `YC.` 前缀只用于看板区分数据来源。实际注入 FMU 时，Worker 会先剥离来源前缀，再用原始变量名匹配 FMU 输入变量。因此 `YC.Beta_Online[2]` 在看板中显示为遥测变量，但注入 FMU 时匹配的是 `Beta_Online[2]`。

看板长时间运行时采用以下性能策略：

- 实时滚动曲线只渲染当前可视范围内的数据，并进行均匀降采样，避免每次刷新全量重绘。
- 实时模式会清洗时间序列，处理环形缓存回绕、重复时间戳和仿真重启后的时间倒退，避免出现异常竖线或柱状图。
- 累积趋势模式保留长期趋势，但会按趋势桶压缩数据，减少长期运行时的内存和绘图压力。
- 多画布场景下采用分批更新，避免多个窗口在同一刷新周期内同时重绘造成明显卡顿。
- 日志窗口设置最大行数，超过后自动删除旧日志，避免日志文本无限增长。

## 5. 关键数据流

### 5.1 实时仿真数据流

```text
主界面选择 FMU 和参数
        ↓
启动 FmuWorker32/FmuWorker64
        ↓
Worker 解压 FMU 并加载 DLL
        ↓
Worker 根据 sync_fields.json 读取白名单变量
        ↓
Worker 执行 doStep
        ↓
读取 FMU 输出变量
        ↓
发送到 PE 端口，同时发送到本地看板端口 22345
```

### 5.2 PE 注入 FMU 数据流

```text
PE 发送 Protobuf 或 JSON 变量包
        ↓
主界面变量注入监听端口接收，例如 9988
        ↓
主界面解析变量类型和值
        ↓
转发到 Worker 控制端口 8898
        ↓
Worker 匹配 FMU 变量名
        ↓
调用 setReal / setInteger / setBoolean 写入 FMU
        ↓
同时镜像到本地看板，便于查看 PE 发来的变量
看板变量名带 PE. 前缀
```

### 5.3 遥测到 FMU 和 PE 数据流

```text
外部遥测 UDP 包
        ↓
yaocetest/main.py 接收并解析
        ↓
ParamFilter.xml 判断是否在白名单内
        ↓
DTS.TM.Sim.Relationship.xml 将 code 映射为 sim_var
        ↓
组装 DDMData / SimVar
        ↓
一路发送给 PE
一路发送给本机 FMU 注入监听端口
        ↓
本机注入路径会为看板来源标识添加 YC. 前缀
        ↓
FMU Worker 注入前剥离 YC. 前缀，并将对应变量写入 FMU
        ↓
同时镜像到看板，变量名带 YC. 前缀
```

### 5.4 轨道预示数据流

```text
主界面输入时间和六根数
        ↓
启动 orbit_pre_runner
        ↓
生成或读取 Orbit_Pre.txt 种子
        ↓
轨道 FMU 执行外推计算
        ↓
输出轨道数据 JSON
        ↓
导出或同步 Orbit_Pre.txt
```

## 6. 主要配置文件说明

| 文件 | 位置 | 作用 |
| --- | --- | --- |
| `gui_config.json` | `Script/` 或 `FmuSolver_Package/` | 保存主界面的路径、端口、主题和用户配置记忆。 |
| `sync_fields.json` | `Script/` 或 `FmuSolver_Package/` | 控制实时仿真中哪些 FMU 输出变量发送给 PE 和看板。 |
| `ParamFilter.xml` | `yaocetest/` | 遥测白名单，只处理其中声明的遥测 code。 |
| `DTS.TM.Sim.Relationship.xml` | `yaocetest/` | 遥测 code 到 FMU 变量名的映射关系，例如 `K0189 -> Beta_Online[2]`。可在遥测页点击 `DTS关系配置` 打开编辑。 |
| `config.ini` | `yaocetest/` | 遥测接收端口、默认目标 IP/端口、字节序等配置。 |
| `Orbit_Pre.txt` | 运行目录或 `txt/` | 轨道预示结果文件，可能被实时 FMU 通过 `filepath` 读取。 |

## 7. 端口和通信说明

| 端口 | 默认值 | 用途 |
| --- | --- | --- |
| PE 接收端口 | 界面配置，常见为 `8889` | 接收仿真数据和遥测转发数据。 |
| FMU 控制端口 | `8898` | 主界面向 Worker 发送暂停、继续、停止、参数更新和变量注入控制命令。 |
| 变量注入监听端口 | 常见为 `9988`，兼容 `8888` | 接收 PE 或遥测桥接发来的变量注入数据。 |
| 看板端口 | `22345` | Worker 向本地 DataVisualizer 发送绘图数据。 |
| 遥测接收端口 | `config.ini` 中 `RecvPort`，常见为 `30019` | 接收外部遥测原始 UDP 数据。 |

## 8. 典型使用流程

### 8.1 源码调试流程

1. 运行 `Script/run_fmusolver_dev.bat` 或直接运行 `FmuLauncherUniversal.py`。
2. 在实时仿真页选择 FMU。
3. 配置 PE IP/端口、注入监听端口、仿真步长、采样频率和时长。
4. 根据需要在启动前勾选或取消 `PointSun`。
5. 勾选自动开启看板或手动点击“看板”。
6. 点击“启动仿真”。
7. 运行中如需触发同步信号，点击“同步”按钮，此按钮只会脉冲 `Is_initial`。
8. 如需遥测接入，切换到遥测页，选择 `yaocetest` 配置目录并启动遥测桥接。
9. 在日志中观察 FMU 加载、变量筛选、注入成功和转发状态。

### 8.2 打包版使用流程

1. 进入 `FmuSolver_Package/`。
2. 双击 `FmuSolver.exe`，不要使用旧入口 `FmuLauncher_Universal.exe`。
3. 确认 `FMU/`、`Visualizer/`、`yaocetest/`、`sync_fields.json` 等文件存在。
4. 按源码调试流程进行配置和运行。

### 8.3 更换新 FMU 的流程

1. 将新的 `.fmu` 文件放入 `FmuSolver_Package/FMU/` 或 `Script/FMU/`。
2. 在主界面重新选择该 FMU。
3. 如果变量有变化，更新 `sync_fields.json` 或通过变量配置界面重新选择变量。
4. 如果遥测变量关系有变化，更新 `DTS.TM.Sim.Relationship.xml`。
5. 启动仿真后观察日志中的 `FMU Metadata Loaded`、`Variable Filter Summary` 和 missing 变量提示。

如果更换 FMU 后出现 GUID 不匹配，通常说明运行目录或包内存在旧模型解压缓存。当前版本会为每次仿真创建独立运行目录，但如果仍遇到类似问题，优先确认使用的是最新打包版本，并结束残留 Worker 进程后重新启动。

### 8.4 全量打包流程

当前推荐使用 `Script/rebuild_all.bat` 进行全量打包，不建议使用 `FmuSolver_Package/rebuild_all.bat` 旧脚本。新版脚本会构建并复制以下主要产物：

- `FmuSolver.exe`
- `FmuWorker64.exe` / `FmuWorker32.exe`
- `OrbitPreCalc64.exe` / `OrbitPreCalc32.exe`
- `YaoCe_LinkLayer64.exe` / `YaoCe_LinkLayer32.exe`
- `Visualizer/DataVisualizer64.exe` / `Visualizer/DataVisualizer32.exe`

打包后建议检查 `FmuSolver_Package` 中这些 EXE 的修改时间，尤其是 `Visualizer/DataVisualizer64.exe`。如果复制阶段提示文件被占用，需要关闭旧看板或旧主程序后重新复制或重新打包。

## 9. 常见问题说明

### 9.1 点击暂停后仿真还继续跑

当前版本已采用 UDP 控制队列和暂停标志文件双保险。若仍出现异常，应确认使用的是最新源码或已重新打包的 EXE。暂停成功时日志会出现：

```text
Simulation Paused by pause flag
```

### 9.2 DLL PermissionError 或 FMU 解压失败

旧版本复用固定运行目录，旧 Worker 占用 DLL 时可能导致新模型解压失败。当前版本每次仿真创建独立工作目录，例如：

```text
C:\FmuSolver_Runtime\fmu_work_worker2_<pid>_<timestamp>
```

如果仍出现占用，可结束残留的 `FmuWorker32.exe` 或 `FmuWorker64.exe` 后重试。

### 9.3 PE 发来的变量 FMU 没有变化

需要同时确认三件事：

- 主界面日志是否显示 `RECV Protobuf` 或 `RECV JSON`。
- 主界面是否显示已转发到 FMU Worker。
- Worker 是否显示 `Injection summary: x/y applied`。

如果日志显示 missing，说明变量名没有匹配到 FMU 变量。需要检查 PE 发来的变量名、FMU 内真实变量名，以及是否需要映射关系。

### 9.4 遥测变量日志中带 `YC.` 是否会影响 FMU 注入

不会。`YC.` 是遥测来源标识，用于看板区分遥测变量和 PE 变量。Worker 实际注入 FMU 前会剥离 `YC.` 前缀，再匹配 FMU 变量名。

如果日志中显示：

```text
Injection summary: 0/3 applied; missing: YC.xxx
```

含义是“收到的遥测变量原始显示名为 `YC.xxx`，但去掉前缀后的 `xxx` 仍未匹配到 FMU 输入变量”。此时应检查 `DTS.TM.Sim.Relationship.xml` 中 `sim_var` 是否与 FMU 中真实输入变量名一致。

### 9.5 看板看不到某个变量

看板只显示实际收到的数据包变量。FMU 输出变量必须在 `sync_fields.json` 中配置并成功匹配；遥测变量必须经过 `ParamFilter.xml` 和 `DTS.TM.Sim.Relationship.xml` 转换后发送。

### 9.6 遥测能发给 PE，但没有注入 FMU

确认主界面启动遥测时日志包含：

```text
遥测与仿真统一转发到 PE: ...
遥测同步注入到本机 FMU 监听端口: 127.0.0.1:...
```

如果只看到 PE 转发而没有本机注入端口，说明运行的不是最新脚本或最新打包版本。

### 9.7 点击同步按钮导致 FMU 报错

当前版本同步按钮只应操作 `Is_initial`，不应操作 `PointSun`。如果日志中仍出现类似 `SetBoolean failed ... PointSun`，说明运行的不是最新源码或最新打包版本。

`PointSun` 的正确使用方式是在仿真启动前通过界面复选框配置；启动仿真后不再运行中修改。

### 9.8 长时间运行变卡

当前版本已对看板绘制、累积趋势、日志窗口和遥测日志做了限流或上限控制。若长时间测试仍出现卡顿，建议先记录以下现场信息：

- 仿真采样频率，例如 `50Hz` 或 `100Hz`。
- `sync_fields.json` 中实际同步变量数量。
- 看板打开的绘图窗口数量和每个窗口曲线数量。
- 是否开启累积趋势模式。
- 遥测输入频率和每包变量数量。

通常情况下，如果主要观察长期趋势，建议使用累积趋势模式；如果使用实时滚动模式，建议减少同时显示的曲线数量和画布数量。

## 10. 维护建议

- 修改 Python 脚本后，源码调试可直接运行；若使用 EXE 测试，必须重新打包。
- 更换 FMU 后建议检查 `Variable Filter Summary`，如果 missing 很多，说明变量配置需要同步更新。
- 遥测 code 和 FMU 变量名不要硬编码在程序里，优先维护 `DTS.TM.Sim.Relationship.xml`。
- 长时间测试前建议关闭旧的 Worker、看板和遥测进程，避免旧版本进程继续占用端口。
- 保留 `sync_fields.json`、`gui_config.json`、`ParamFilter.xml`、`DTS.TM.Sim.Relationship.xml` 的备份，便于恢复现场配置。
