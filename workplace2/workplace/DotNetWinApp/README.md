# 柴油机实时监控与数据校验系统 (DotNetWinApp) 技术文档

这是一个基于 .NET 6.0 Windows Forms 开发的高性能实时监控工具，专门用于柴油机仿真与试验数据的实时采集、曲线可视化及数据校验。本文档旨在为开发人员及 AI 助手提供深入的技术实现细节，以便进行后续优化。

---

## ? 技术架构与实现细节

### 1. 核心数据模型 (`ChartVariable`)
系统的所有监控指标都封装在 `ChartVariable` 类中：
- **数据缓存**：使用 `double[] Data` 数组预分配 150,000 个点（约支持 1.4 小时连续监控 @ 30Hz），避免频繁分配内存。
- **多窗口联动**：维护 `List<SignalPlot> SignalPlots`，允许同一个变量在多个不同的曲线窗口中同步渲染。
- **持久化**：通过 `ColorHtml` 实现颜色属性的 JSON 序列化。

### 2. 绘图引擎与 UI 组件 (`PlotWindow`)
继承自 `UserControl`，封装了 `ScottPlot.FormsPlot`：
- **动态挂载**：`AddVariable()` 方法可动态向窗口添加曲线。
- **交互逻辑**：
    - **游标 (Cursor)**：实时计算鼠标坐标对应的仿真时间，并通过 `Annotation` 显示该时刻所有变量的具体数值。
    - **误差分析**：内置右键菜单，支持两个变量间的“数值误差”和“百分比误差”实时计算并绘制差值曲线。
    - **拖拽系统**：支持窗口在 `plotHostPanel` 容器内的自由拖动及激活状态切换（高亮边框）。

### 3. 通信层实现 (`UDPClient`)
- **异步监听**：在独立后台线程中运行 `clientListen` 循环，采用 `Socket.ReceiveFrom` 接收数据。
- **协议解析**：
    - 支持 Base64 解码后进行 **Google Protobuf** 反序列化。
    - 解析出的数据通过 `SendData` 事件派发至主线程。

### 4. 主程序核心方法 (`Program.cs`)

#### ? 数据流转与渲染
- `UpdateExternalData(Dictionary<string, double> data)`：
    - **核心逻辑**：基于 `udpMappings`（Tag 到变量的映射字典）进行毫秒级分发。
    - **索引同步**：更新 `v.Data` 的同时更新 `v.SignalPlots` 的 `MaxRenderIndex`，确保渲染线程只绘制有效数据。
- `renderTimer_Tick`：以 ~30FPS 的频率触发 `UpdateAllPlots()` 和 `UpdateTableUI()`，实现 UI 与数据的解耦。

#### ? 指标体系与配置管理
- `ImportVariables / ExportVariables(string filePath)`：支持变量指标体系的批量导入导出（JSON 格式）。
- `RefreshRegionTabs()`：**动态 UI 生成**，根据当前变量池中的 `Region` 字段自动创建左侧切换按钮。
- `UpdateVariableList(string region)`：刷新左侧卡片列表，支持拖拽卡片至绘图区触发 `CreateNewPlotWindow`。

#### ? 布局持久化
- `SaveLayout / LoadLayout`：将所有打开窗口的位置、大小、关联变量 `Tag` 及误差分析状态保存至 `layouts/*.json`。

---

## ? 关键优化点 (供后续开发/AI 参考)

1.  **渲染性能**：
    - 目前使用 `SignalPlot` 渲染大数组，性能极高。
    - 若需进一步提升，可考虑在 `UpdateAllPlots` 中仅针对 `IsVisible` 的窗口调用 `Refresh`。

2.  **编码兼容性**：
    - UI 图标（?, ?, ▲, ▼）已全部替换为 Unicode 转义序列（如 `\u25C4`），避免在非 UTF-8 环境下出现乱码。

3.  **数据映射逻辑**：
    - `udpMappings` 采用了 `StringComparer.OrdinalIgnoreCase` 忽略大小写，增强了对不同数据源命名的兼容性。

4.  **误差分析扩展**：
    - 当前仅支持窗口内前两个变量对比。优化方向：支持通过 UI 选择任意两个已选变量进行对比。

## ? 项目结构概览
- `Program.cs`：主逻辑、配置窗口 `ConfigForm`、全局状态管理。
- `UDPClient.cs`：UDP 原始套接字操作、Protobuf 解析。
- `Ddm.cs`：Protobuf 自动生成的模型定义。
- `variables.json`：默认指标体系存储。
- `layouts/`：用户自定义布局方案文件夹。
