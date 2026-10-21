# FmuSolver 看板与长时间运行交接文档

生成日期：2026-08-05
仓库路径：`C:\Users\木木\.codex\worktrees\eac1\FMUSOLVER`
当前分支：`dev`
最近提交：`7dde138 增强看板功能和稳定性，支持长时间生产运行`

## 新任务恢复提示词

```text
我们正在继续 FmuSolver 项目。请先完整阅读：
C:\Users\木木\.codex\worktrees\eac1\FMUSOLVER\docs\codex-handoffs\2026-08-05-fmusolver-dashboard-t0-handoff.md

然后检查当前 git 状态、相关源码和最新运行日志，验证交接内容仍然适用，再从“下一步”继续。不要依赖旧聊天上下文，也不要覆盖工作树中已有的用户修改。

重要约束：日常开发只使用 C:\Users\木木\.codex\worktrees\eac1\FMUSOLVER。除非我明确说“打包”，不要打包 EXE；除非我明确说“同步到发布目录”，不要同步到 C:\Spaceship\FMUSOLVER。不要擅自提交、推送、清理或回滚。
```

## 当前目标

让 FmuSolver 在真实生产环境连续运行至少一天，并保证实时仿真、遥测/PE 注入、PE 外发和看板 UI 长时间稳定。当前最具体的验收点是：看板必须真实显示 FMU 的精确初始快照 `t=0.000000000s` 和精确终点，不允许用插值、前向填充或伪造数值掩盖缺失数据。

## 用户偏好与硬性约束

- 日常开发目录固定为 `C:\Users\木木\.codex\worktrees\eac1\FMUSOLVER`。
- `C:\Spaceship\FMUSOLVER` 是正式发布/打包目录，只有用户明确要求时才同步。
- 只有用户明确说“打包”才构建 EXE；当前这轮修改未打包、未同步。
- 不擅自提交、推送、创建分支、清理运行目录或回滚已有修改。
- 工作树很脏，包含源码、发布 EXE、截图、结果 JSON 等用户已有修改；禁止 `git reset --hard`、`git checkout -- .` 或大范围删除。
- 看板必须忠实反映真实采样。真实缺失位置不得显示伪造数值；缺失区可用同色半透明虚线提示，但游标在缺失点只显示时间。
- UI 风格偏苹果式、状态反馈明确、版本号融入主题；默认曲线线宽为 2，选中曲线至少 5。

## 本阶段已完成

### 1. 精确零时刻快照

此前实测曲线从约 `0.84s` 开始。日志证明这不是 FMU 未计算或 UDP 丢包：

- Worker 输出：`[SNAPSHOT] initial precise dashboard frame sent at sim_time=0.000000000s vars=103 finite=103 deferred=0`。
- Worker 性能日志：`send_err=0`。
- 看板性能日志：`rx_err=0 rx_drop=0 queue=0/20`。

根因是看板“累积趋势”默认使用 1 秒时间桶。真实 `t=0` 与随后约 1 秒采样被压缩为一个点，并用桶末时刻（现场约 `0.84s`）作为横坐标，因此零点在显示层被吞掉。

修复内容：

- `Script\DataVisualizerPython.py`
  - `append_trend_sample()` 将真实 `t=0` 初始快照保存为不可聚合边界点。
  - 同一 `t=0` 的后续 UDP 分包会合并到同一个趋势点，支持未来超过 200 个变量的初始帧。
  - 性能日志新增 `first_t` 和 `trend_first`。
  - 收到原子首帧后写入：`[SNAPSHOT][VIZ] exact initial frame accepted...`。
- `Script\fmu_player.py`
  - `send_fmu_data()` 新增 `viz_start` 参数。
  - 开始标记 `__FMUSOLVER_SIM_START_TIME__` 与初始变量合并在同一个看板 UDP 包，避免两个独立报文极端乱序后清空首帧。
  - 初始发送改为 `send_fmu_data(0.0, initial_out, force_viz=True, viz_start=True)`。

这些修改只改善传输和显示，不改变 FMU 内部积分、输出值或计算精度。

### 2. 精确终点与游标

- Worker 在有限时长结束时发送精确最终快照和 `__FMUSOLVER_SIM_END_TIME__` 标记。
- 看板合并同一仿真时刻的 UDP 分包，并强制刷新累计趋势终点。
- 20 秒仿真数据层已能达到 `latest_t=20.000000000`、`trend_latest=20.000000000`。
- “实际计时”游标直接使用仿真经过时间，避免用首个日历时间包基准导致 `20.00` 显示成 `19.98`。

### 3. 看板交互与真实缺失显示

- 默认曲线线宽为 2；选中曲线变粗至至少 5，并与变量表双向高亮。
- 右键开启可拖动竖直游标，显示曲线交点值和 X 轴半透明时间标签。
- 游标数值标签自动避让，右侧空间不足时切换到左侧。
- 取消左键框选放大。
- 累积趋势数组已修复前后错位问题：短变量历史使用前置 `NaN` 对齐旧时间。
- 真实数据使用实线；两个真实端点之间的无数据区使用同色半透明虚线提示；游标落在缺失点不显示变量数值。
- 绘图设置已折叠收纳 `Realtime`、`累积趋势`、`Title`、`Mode`、`Span (s)`、`游标时间`；“导出 Word”使用有背景色按钮。

### 4. 黑名单、遥测状态与版本

- 黑名单管理支持保存 `blocked: true/false`，运行中可通过 `__reload_injection_blacklist` 热加载。
- 用户明确允许的变量不会被自动保护逻辑重新加入黑名单。
- 仿真界面已有遥测接收状态灯，区分等待、接收和超时状态。
- 主界面和看板版本统一为 `v26.0724.0946`，样式融入主题。

## 关键文件

- `Script\DataVisualizerPython.py`：看板数据接收、趋势缓存、曲线、游标、缺失区和版本 UI。
- `Script\fmu_player.py`：FMU Worker、初始/最终快照、看板 UDP、PE 外发、注入及黑名单。
- `Script\FmuLauncherUniversal.py`：主界面、Worker/看板启动、遥测状态灯和黑名单管理。
- `Script\build_version.json`：当前界面版本。
- `Script\fmu_injection_blacklist.json`：注入黑名单/允许状态。
- `Script\fmusolver_runtime.log`：主程序与 Worker 运行证据。
- `Script\visualizer_perf.log`：看板收包、队列、首末时间和刷新证据。
- `FmuSolver_Package\`：当前工作树内已有一次正式打包产物，但不要假定它包含 2026-08-03 的零时刻修复。

## 已运行验证

- `python -m py_compile Script\DataVisualizerPython.py Script\fmu_player.py`
- 无界面趋势测试：`t=0` 初始值保持为 `trend_times[0] == 0.0`。
- 本机 UDP 协议测试：初始看板包同时包含 `__FMUSOLVER_SIM_START_TIME__`、`A`、`B`，且 `sim_time == 0.0`。
- 测试输出：`PASS: exact t=0 trend boundary and atomic initial UDP frame`。
- `git diff --check -- Script\DataVisualizerPython.py Script\fmu_player.py` 通过，仅有 Git 的 LF/CRLF 提示。

## 当前工作树状态

- 分支：`dev`。
- 工作树存在大量未提交修改，不能将它们全部视为本阶段新增。
- 本阶段直接修改：`Script\DataVisualizerPython.py`、`Script\fmu_player.py`。
- 当前还存在主界面、版本、黑名单、打包 EXE、轨道结果、构建脚本和旧 handoff 等其他修改。
- 当前源码与 `FmuSolver_Package` 不一定完全一致。遵守约定：不要自动同步或打包。

## 已知问题与注意事项

- 必须完全关闭旧主程序、旧 Worker 和旧看板后再运行源码，否则旧进程仍使用旧代码。
- 如果运行 EXE，2026-08-03 的零时刻修复不会自动进入已打包程序。
- `send_viz_start_marker()` 旧方法仍保留但初始路径已不再调用；不要重新改回“独立开始标记 + 独立数据帧”。
- 初始看板 UDP 包仍按变量数分包；超过 200 变量时只有第一分包携带开始标记，看板会按同一 `sim_time` 合并后续分包。
- 本轮证据来自本机回环地址。现场跨机器 UDP 仍应通过 `rx_err/rx_drop/send_err` 和包级日志判断，不能仅凭曲线缺口断言丢包。
- `visualizer_perf.log` 会持续增长；本轮没有执行日志轮转或 Codex 清理。

## 下一步

1. 完全关闭旧进程，从源码运行 `python C:\Users\木木\.codex\worktrees\eac1\FMUSOLVER\Script\FmuLauncherUniversal.py`。
2. 开启“累积趋势”，运行 20 秒仿真，确认曲线和游标可到 `0.00s` 与 `20.00s`。
3. 检查 `Script\visualizer_perf.log` 是否出现 `exact initial frame accepted`、`first_t=0.000000000`、`trend_first=0.000000000`、`trend_latest=20.000000000`。
4. 若仍非零开始，保存最新截图以及两份日志对应运行段，检查是否运行了旧进程/旧 EXE、是否切换曲线后才开始缓存、或是否存在特定变量的真实 `NaN/Inf`。
5. 用户确认源码实测通过后，只有在明确要求“打包”时才构建；只有明确要求“同步到发布目录”时才更新 `C:\Spaceship\FMUSOLVER`。

## Keep Codex Fast 只读报告

2026-08-05 已按技能要求执行首次只读报告，没有修改 Codex 状态：

- 活跃会话：46；活跃会话文件约 0.190 GB；归档会话约 0.084 GB。
- 标题/首消息元数据明显膨胀：25 个候选；最大字段约 65,724 字符。
- 旧会话候选：16，共约 0.047 GB。
- 陈旧工作树候选：1，约 1.594 GB。
- Codex 日志约 114.4 MB。
- Windows 扩展路径候选：rollout path 14、cwd 6。
- 本次没有执行 `--apply`、元数据修复、归档、移动、删除或日志轮转。

如后续需要维护，应先确认本交接文档可用、关闭 Codex，再单独决定是否运行安全归档；备份可能含私人本地元数据，不应上传或公开分享。
