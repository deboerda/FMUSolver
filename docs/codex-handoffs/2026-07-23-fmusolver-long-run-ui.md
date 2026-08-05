# FmuSolver 长任务交接文档

生成日期：2026-07-23
仓库路径：C:\Users\木木\.codex\worktrees\eac1\FMUSOLVER
当前分支：dev

## 新任务恢复提示词

```text
我们正在继续 FmuSolver 项目。请先阅读：
C:\Users\木木\.codex\worktrees\eac1\FMUSOLVER\docs\codex-handoffs\2026-07-23-fmusolver-long-run-ui.md

读取后请检查当前仓库状态，确认哪些改动已经存在，再继续处理我的新需求。不要依赖旧聊天上下文；以交接文档和当前文件为准。

重要约束：除非我明确说“打包”，不要打包 exe；除非我明确说“同步到发布目录”，不要同步到 C:\Spaceship\FMUSOLVER。日常开发使用 C:\Users\木木\.codex\worktrees\eac1\FMUSOLVER，正式发布目录另行同步。
```

## 当前目标

FmuSolver 要稳定支持长时间生产运行，重点包括：

- 实时仿真、轨道预示、遥测/PE 注入、PE 外发稳定运行。
- 看板不卡顿，交互明确，曲线显示准确。
- 现场测试能明确判断遥测接收状态、注入状态、外发状态。
- 日常开发和发布目录严格分离，避免不同目录功能不一致。

## 用户硬性偏好和约束

- 未明确要求时，不打包 exe。
- 未明确要求时，不同步到 `C:\Spaceship\FMUSOLVER` 发布目录。
- 日常开发目录：`C:\Users\木木\.codex\worktrees\eac1\FMUSOLVER`。
- 发布/打包目录：`C:\Spaceship\FMUSOLVER`，只在用户明确要求时同步/发布。
- 用户希望 UI 风格简洁、自然、有苹果式按压/状态反馈，不要突兀的蓝色徽章。
- 用户希望回答尽量说清楚结论和现场可验证方式。

## 最近已完成的重要改动

### 1. 看板版本号

目的：方便确认当前运行的是不是最新版本。

已改：

- `Script\DataVisualizerPython.py`
  - 新增读取 `build_version.json` 的版本号逻辑。
  - 左上角标题旁显示版本号。
  - 版本样式改为弱文字风格，无蓝底、无边框、无徽章感。
- `Script\FmuLauncherUniversal.py`
  - 主界面版本号样式同步改为弱文字风格。
  - 修复一次 `NameError: muted_text is not defined`，改为主界面自己的 `version_text`。
- 已同步脚本副本到：
  - `FmuSolver_Package\DataVisualizerPython.py`
  - `FmuSolver_Package\FmuLauncherUniversal.py`
  - `FmuSolver_Package\build_version.json`

验证：

- `python -m py_compile Script\DataVisualizerPython.py Script\FmuLauncherUniversal.py`
- `python -m py_compile FmuSolver_Package\DataVisualizerPython.py FmuSolver_Package\FmuLauncherUniversal.py`
- 做过 3 秒启动探针，主界面能进入运行状态。

### 2. 看板 20s 终点显示问题

用户问题：停止时间设置 20s，实测曲线只画到约 19.98s，游标也拖不到 20s。

已做的修复：

- `Script\fmu_player.py`
  - 有限时长仿真结束时强制发送最终精确快照：`sim_time=20.000000000s`。
  - 新增 `send_viz_time_marker(sim_time)`，发送很小的看板专用终点标记包：`__FMUSOLVER_SIM_END_TIME__`。
- `Script\DataVisualizerPython.py`
  - 同一仿真时刻的多个 UDP 分包合并为同一帧。
  - 同帧后续分包到达后也增加 `data_revision` 触发刷新。
  - 新帧会从上一帧继承变量值，终点标记包到达时，已有曲线可沿用上一帧值画到终点。
  - 忽略内部变量名前缀 `__FMUSOLVER_`，避免终点标记污染变量列表。

已同步脚本副本到：

- `FmuSolver_Package\DataVisualizerPython.py`
- `FmuSolver_Package\fmu_player.py`

复测要求：

- 必须完全关闭旧 FmuSolver 和旧看板后重新打开。
- 运行源码入口：
  `python C:\Users\木木\.codex\worktrees\eac1\FMUSOLVER\Script\FmuLauncherUniversal.py`
- 结束日志应出现：
  `[SNAPSHOT] final precise dashboard frame sent at sim_time=20.000000000s`

注意：如果用户运行 EXE，则这些 Python 源码改动不会进入 EXE，除非用户明确要求打包。

### 3. 曲线游标功能

已实现/调整过：

- 去除看板鼠标左键框选放大功能，改为平移模式。
- 右键画板可选择开启/关闭游标。
- 游标是一条可拖动竖线。
- 显示游标与各曲线交点处的值。
- 数值过近时做错位显示，避免重叠。
- 游标时间显示在 X 时间轴区域，并带半透明背景框。
- 可选游标时间模式：
  - 模型时间
  - 实际计时

相关文件：

- `Script\DataVisualizerPython.py`
- `FmuSolver_Package\DataVisualizerPython.py`

### 4. PE/遥测变量显示与注入关系澄清

已向用户澄清：

- 看板显示的是成功接收并解析的数据，不等于全部都成功注入 FMU。
- 遥测看板变量：收到并解析后，经过 `ParamFilter.xml`、DTS 关系配置过滤/映射后的数据。
- PE 看板变量：FmuSolver 收到并解析的 PE 数据。
- 成功注入 FMU 的变量是看板显示变量的子集。

### 5. PE 注入别名与黑名单管理

用户发现：老版本 `SolarAngle_CJinput[1]` 可注入到 `Environment_A.SolarAngleInput`，新版本没有注入。

已做：

- `Script\fmu_player.py`
  - 新增外部输入别名映射，例如：
    - `SolarAngle_CJinput[1]` -> `Environment_A.SolarAngleInput`
    - `SolarAngle_CJinput[2]` -> `EnvironmentB1.SolarAngleInput`
    - `solar_CJinput[1]` -> `Environment_A.SolarAngleInput`
    - `solar_CJinput[2]` -> `EnvironmentB1.SolarAngleInput`
  - 别名优先于精确匹配。
  - 黑名单中保留 `ShelterRatio_CJinput[1/2]`，移除 SolarAngle 相关项。
- `Script\FmuLauncherUniversal.py`
  - 仿真界面新增“黑名单管理”按钮。
  - 可编辑 `fmu_injection_blacklist.json`。
  - 默认黑名单仍拦截部分敏感变量，但用户可调整。

相关文件：

- `Script\fmu_player.py`
- `Script\FmuLauncherUniversal.py`
- `Script\fmu_injection_blacklist.json`
- `FmuSolver_Package\fmu_injection_blacklist.json`

### 6. 轨道预示与 Orbit_Pre.txt 逻辑

用户最终要求简化为：

- 启动实时仿真时，直接读取当前运行目录下的 `FmuSolver_Package\Orbit_Pre.txt`。
- 如果需要外部替换，用户直接替换这个文件。
- 轨道预示生成后默认复制/替换一份到当前运行目录下的 `FmuSolver_Package\Orbit_Pre.txt`。

历史上曾讨论过运行时工作区 `C:\FmuSolver_Runtime\job_xxxxxxxx`，但用户认为太复杂，偏好上述简化策略。

如后续继续相关问题，要先检查当前代码是否已经完全符合这个最终策略，不要重新引入复杂多副本逻辑。

### 7. C:\FmuSolver_Runtime 管理

用户问是否会越来越多。

已说明：应有清理机制即可，不要求立即改动。

若后续要实现，建议：

- 每次启动新实时仿真/轨道预示前清理旧 `job_*` / `fmu_work_worker*`。
- 避免删除当前正在运行的工作区。
- 保留必要日志或失败现场目录，或按数量/时间限制清理。

### 8. 看板默认样式和按钮反馈

已做或讨论过：

- 看板线条默认粗细调整为 5。
- 默认线条颜色改为基于变量名的随机跳色，便于区分。
- 开始类按钮需要有按下状态反馈：开始预示解答、启动仿真、启动转发引擎等。
- 左上角版本号已更新为主题融合风格。

## 已运行的命令/检查

最近明确跑过：

- `python -m py_compile Script\DataVisualizerPython.py Script\FmuLauncherUniversal.py`
- `python -m py_compile FmuSolver_Package\DataVisualizerPython.py FmuSolver_Package\FmuLauncherUniversal.py`
- `python -m py_compile Script\fmu_player.py FmuSolver_Package\fmu_player.py`
- 3 秒启动探针：启动 `Script\FmuLauncherUniversal.py` 后进程保持运行，说明初始化阶段无 NameError。

## 当前未完成/需复测事项

1. 用户需重新运行源码入口，确认主界面版本号样式已自然融合。
2. 用户需重新打开看板，确认看板左上角版本号显示且不突兀。
3. 用户需复测 20s 仿真：
   - 曲线是否画到 20s。
   - 游标是否可以拖到 20s。
   - 日志是否出现最终快照 `20.000000000s`。
4. 如果用户运行 EXE 发现未生效，提醒必须明确说“打包”后才能进入 EXE。
5. 如果用户要发布到 `C:\Spaceship\FMUSOLVER`，必须等用户明确说“同步到发布目录”。

## 后续建议步骤

1. 让用户关闭旧 FmuSolver/看板后重新运行源码入口。
2. 复测 20s 终点显示。
3. 如果仍不到 20s：
   - 查看 Worker 日志是否出现 `[SNAPSHOT] final precise dashboard frame sent at sim_time=20.000000000s`。
   - 查看 `visualizer_perf.log` 是否有丢包/队列积压。
   - 检查看板是否实际运行的是 `Script\DataVisualizerPython.py`，而不是已打包 EXE。
4. 确认版本号 UI 样式符合用户审美。
5. 用户明确要求时再打包或同步发布目录。

## 重要提醒

- 这个仓库当前有大量已修改文件，不要随意回滚不相关文件。
- 不要擅自提交、推送、打包、同步发布目录。
- 文件换行有 Git 提示 `LF will be replaced by CRLF`，目前只是警告。
- 交接后新任务应以当前文件实际内容为准，先检查再修改。

## 2026-07-23 补充：20s 终点仍不到位的进一步修复

用户确认 Worker 已输出：`[SNAPSHOT] final precise dashboard frame sent at sim_time=20.000000000s`，但看板曲线和游标仍停在 19.98。

进一步定位：

- 普通实时曲线已可通过终点标记继承上一帧画到 20s。
- 但用户截图中可能开启了“累计趋势”。累计趋势使用 `trend_times/trend_store` 桶缓存，不走普通 `data_store` 终点继承逻辑。
- 终点标记包之前会导致趋势桶最后仍停在 19.98，或者同一 20s 分包更新不到已有趋势点。

已修复：

- `Script\DataVisualizerPython.py`
  - `append_trend_sample()`：如果同一时间点已存在，直接更新最后一个趋势点，而不是新建重复点。
  - 新增 `append_trend_boundary(t)`：终点标记到达时，强制刷新趋势桶并落一个精确终点，例如 20.0。
  - `process_data()`：累计趋势开启且收到 `__FMUSOLVER_SIM_END_TIME__` 时，调用 `append_trend_boundary(t)`。
- 已同步到 `FmuSolver_Package\DataVisualizerPython.py`。

已做自测：

- 模拟普通曲线：19.98 -> 20.0，结果最后时间为 20.0。
- 模拟累计趋势：19.98 -> 20.0 + 终点标记，结果 `trend_times == [20.0]`。
- `python -m py_compile Script\DataVisualizerPython.py FmuSolver_Package\DataVisualizerPython.py` 通过。

复测提醒：必须完全关闭旧看板后重新打开，否则旧进程仍使用旧代码。

## 2026-07-23 再补充：终点标记已收到但 UI 仍停在 19.98

用户截图显示看板版本已更新，并且 `visualizer_perf.log` 中确认：

`[SNAPSHOT][VIZ] final time marker received: sim_time=20.000000000s vars=1 idx=97`

进一步根因：

- 终点标记已经被看板收到。
- 但累计趋势模式为了省性能，有 `accumulate_update_stride=10` 的跳帧刷新逻辑。
- 当终点到达时 `current_idx` 约为 97/98，不是 10 的倍数，于是最后一次绘图刷新被跳过。
- 所以数据层有机会收到 20s，但 UI 曲线和游标仍停留在上一次已绘制的 19.98。

已修复：

- `Script\DataVisualizerPython.py`
  - 新增 `force_curve_update_revision`。
  - 收到 `__FMUSOLVER_SIM_END_TIME__` 时，把下一次 `data_revision` 标记为强制刷新。
  - 累计趋势跳帧逻辑遇到强制刷新时不再跳过。
  - 性能日志增加 `rev / force_rev / latest_t / trend_latest`，下次可直接判断数据层和趋势层是否到达 20.0。
- 已同步到 `FmuSolver_Package\DataVisualizerPython.py`。

自测结果：

- 模拟 `current_idx=97`、累计趋势开启、终点标记 `20.0`。
- 结果：`current_idx=98`、`last_time=20.0`、`trend_times=[19.98, 20.0]`、`would_skip=False`。

复测仍需完全关闭旧看板后重新打开。

## 2026-07-23 补充：曲线到终点但游标实际计时显示 19.98

用户确认曲线已经能绘制到仿真终点，但游标下方“实际计时”仍显示 `00:00:19.98`，不是 `00:00:20.00`。

根因：

- 看板的“实际计时”显示逻辑用了 `cursor_x - base_sim_time`。
- `base_sim_time` 是从第一帧带 Year/Mon/Day/Hour/Min/Sec 的数据包中记录的，而实时仿真第一帧通常是 `step=0.02s`。
- 因此当 cursor_x 实际已经是 20.0 时，显示成 `20.0 - 0.02 = 19.98`。
- 这不是 FMU 仿真终点不准，也不是数据没到 20s，而是游标显示基准错误。

已修复：

- `Script\DataVisualizerPython.py`
  - “实际计时”模式改为直接显示 `cursor_x`，即仿真从 0s 开始后的经过时间。
  - 保留绝对时间/模型时间模式原逻辑，不影响 X 轴北京时间显示。
- 已同步到 `FmuSolver_Package\DataVisualizerPython.py`。
- `python -m py_compile Script\DataVisualizerPython.py FmuSolver_Package\DataVisualizerPython.py` 通过。

复测：

- 关闭旧看板后重新打开。
- 游标时间模式选“实际计时”。
- 拖到终点应显示 `00:00:20.00`。

## 2026-07-24 补充：黑名单取消拦截保存无效

用户反馈：仿真前或仿真中取消黑名单变量拦截，点击“保存并应用”后无效；再次打开黑名单管理仍显示被拦截。

根因：

- 旧 UI 取消勾选后直接从 JSON 删除变量，没有保存“明确允许”状态。
- Worker 旧逻辑只在仿真启动时读取一次黑名单，运行中保存不会热加载。
- 如果放开变量后触发 FMU set/doStep 异常，Worker 的自动保护逻辑可能再次把变量写回黑名单。

已修复：

- `Script\FmuLauncherUniversal.py`
  - 黑名单 JSON 现在保存所有行，包含 `blocked: true/false`。
  - 再次打开黑名单管理时，会按 `blocked` 状态恢复勾选/取消勾选。
  - “保存并应用”后，如果 Worker 正在运行，会发送 `__reload_injection_blacklist` 控制命令。
  - 变量注入监听的控制键白名单加入 `__reload_injection_blacklist`，避免误转为 PE 变量。
- `Script\fmu_player.py`
  - `load_injection_blacklist()` 现在返回 blocked/allowed 两类状态。
  - `blocked: false` 的变量进入 allowlist，不参与拦截。
  - 收到 `__reload_injection_blacklist` 后运行中热加载配置。
  - 自动加黑名单时，如果变量已被用户明确 `blocked:false`，不会重新加回黑名单。

已同步到：

- `FmuSolver_Package\FmuLauncherUniversal.py`
- `FmuSolver_Package\fmu_player.py`

验证：

- `python -m py_compile Script\FmuLauncherUniversal.py Script\fmu_player.py` 通过。
- `python -m py_compile FmuSolver_Package\FmuLauncherUniversal.py FmuSolver_Package\fmu_player.py` 通过。
- 临时 JSON 自测：`A blocked:false` 被识别为 allowed，自动加黑名单不会覆盖它；`C` 可正常自动加入 blocked。

注意：如果使用 EXE，需要重新打包后才进入正式可执行文件。
