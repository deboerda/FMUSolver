using System;
using System.Windows.Forms;
using System.Drawing;
using System.Collections.Generic;
using System.Linq;
using ScottPlot;
using ScottPlot.Plottable;
using System.Diagnostics;

namespace DotNetWinApp
{
    // 核心数据模型 - 保留原始逻辑
    public class ChartVariable
    {
        public string Name { get; set; }
        public string Tag { get; set; }
        public string Region { get; set; }
        public Color Color { get; set; }
        public bool IsSelected { get; set; }
        public double[] Data { get; set; } = new double[150000]; 
        public SignalPlot SignalPlot { get; set; }
        public double CurrentValue { get; set; }
        public double MaxValue { get; set; } = double.MinValue;
    }

    static class Program
    {
        // 全局变量与逻辑 - 严格保留原始定义
        private static readonly List<ChartVariable> variables = new();
        private static FormsPlot formsPlot;
        private static DataGridView dataGridView;
        private static System.Windows.Forms.Timer renderTimer;
        private static UDPClient udpClient; 
        private static int tick = 0;
        private static readonly Dictionary<string, List<ChartVariable>> udpMappings = new(StringComparer.OrdinalIgnoreCase);
        private static AppConfig config;
        private static bool hasNewData = false;
        private static readonly object dataLock = new();
        private static int currentRangePoints = 1800; 
        private static CheckBox cbAutoFollow, cbAutoScaleY, cbShowCursor;
        private static ComboBox comboRange;
        private static Label lblStatus, lblSelectionCount;
        private static VLine vCursorLine;
        private static Annotation vCursorLabel;
        private static int packetCount = 0;
        private static FlowLayoutPanel variableListContainer; // 修正：全局引用列表容器

        // 视觉风格定义
        private static readonly Color ColorBg = Color.FromArgb(10, 14, 23);
        private static readonly Color ColorPanel = Color.FromArgb(17, 24, 39);
        private static readonly Color ColorCard = Color.FromArgb(31, 41, 55);
        private static readonly Color ColorCyan = Color.FromArgb(6, 182, 212);
        private static readonly Color ColorCyanBright = Color.FromArgb(34, 211, 238);
        private static readonly Color ColorAmber = Color.FromArgb(245, 158, 11);
        private static readonly Color ColorMuted = Color.FromArgb(156, 163, 175);
        private static readonly Color ColorRed = Color.FromArgb(239, 68, 68);
        private static readonly Color ColorGreen = Color.FromArgb(16, 185, 129);
        private static readonly Color ColorBorder = Color.FromArgb(55, 65, 81);

        public class AppConfig { public NetworkConfig Network { get; set; } }
        public class NetworkConfig { public string LocalIP { get; set; } public int LocalPort { get; set; } }

        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            try 
            {
                LoadConfig();
                InitVariables(); 

                Form mainForm = new() { 
                    Text = "柴油机实时监控与数据校验系统", 
                    Width = 1600, 
                    Height = 900, 
                    BackColor = ColorBg, 
                    StartPosition = FormStartPosition.CenterScreen 
                };

                // 防止文件锁定的核心逻辑
                mainForm.FormClosed += (s, e) => {
                    renderTimer?.Stop();
                    if (udpClient != null) { try { (udpClient as IDisposable)?.Dispose(); } catch { } }
                    Process.GetCurrentProcess().Kill(); // 暴力但有效，确保进程彻底结束
                };

                // --- 布局构建 ---
                
                // 顶部：标题栏
                Panel titleBar = new() { Dock = DockStyle.Top, Height = 60, BackColor = ColorBg };
                Label lblTitle = new() { 
                    Text = ">>>> 柴油机实时监控与数据校验工具 <<<<", 
                    ForeColor = ColorCyanBright, 
                    Font = new Font("微软雅黑", 18, FontStyle.Bold), 
                    TextAlign = ContentAlignment.MiddleCenter, 
                    Dock = DockStyle.Fill 
                };
                lblStatus = new Label { Text = "● 系统就绪", ForeColor = ColorMuted, AutoSize = true, Font = new Font("微软雅黑", 10, FontStyle.Bold), Anchor = AnchorStyles.Right, Location = new Point(1480, 20) };
                titleBar.Controls.Add(lblStatus);
                titleBar.Controls.Add(lblTitle);

                // 左侧：指标体系面板
                Panel leftPanel = new() { Width = 320, Dock = DockStyle.Left, Padding = new Padding(10, 0, 5, 10), BackColor = ColorBg };
                Panel leftBorder = new() { Dock = DockStyle.Fill, BackColor = ColorBorder, Padding = new Padding(1) };
                Panel leftContent = new() { Dock = DockStyle.Fill, BackColor = ColorPanel };
                
                Label lblLeftTitle = new() { Text = "监测指标体系", Dock = DockStyle.Top, Height = 40, BackColor = ColorCard, ForeColor = ColorCyan, TextAlign = ContentAlignment.MiddleLeft, Padding = new Padding(10,0,0,0), Font = new Font("微软雅黑", 10, FontStyle.Bold) };
                
                // 区域切换按钮 (Grid布局)
                TableLayoutPanel tabGrid = new() { Dock = DockStyle.Top, Height = 80, ColumnCount = 2, RowCount = 2, Padding = new Padding(5) };
                tabGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50f));
                tabGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50f));
                string[] regionList = { "3#柴油机仿真数据", "4#柴油机仿真数据", "3#柴油机试验数据", "4#柴油机试验数据" };
                Button[] tabBtns = new Button[4];
                for (int i = 0; i < 4; i++) {
                    int idx = i;
                    tabBtns[i] = new Button { 
                        Text = regionList[i].Replace("柴油机", ""), 
                        Dock = DockStyle.Fill, FlatStyle = FlatStyle.Flat, 
                        BackColor = ColorCard, ForeColor = ColorMuted, 
                        Font = new Font("微软雅黑", 9, FontStyle.Bold), Margin = new Padding(2) 
                    };
                    tabBtns[i].FlatAppearance.BorderSize = 0;
                    tabBtns[idx].Click += (s, e) => {
                        foreach (var b in tabBtns) { b.BackColor = ColorCard; b.ForeColor = ColorMuted; }
                        tabBtns[idx].BackColor = Color.FromArgb(15, 118, 110); tabBtns[idx].ForeColor = Color.White;
                        UpdateVariableList(regionList[idx]);
                    };
                    tabGrid.Controls.Add(tabBtns[i], i % 2, i / 2);
                }

                variableListContainer = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoScroll = true, FlowDirection = FlowDirection.TopDown, WrapContents = false, Padding = new Padding(5) };
                lblSelectionCount = new Label { Text = "已选: 0 项", Dock = DockStyle.Bottom, Height = 30, ForeColor = ColorCyan, TextAlign = ContentAlignment.MiddleCenter, Font = new Font("微软雅黑", 9) };

                leftContent.Controls.Add(variableListContainer);
                leftContent.Controls.Add(tabGrid);
                leftContent.Controls.Add(lblSelectionCount);
                leftContent.Controls.Add(lblLeftTitle);
                leftBorder.Controls.Add(leftContent);
                leftPanel.Controls.Add(leftBorder);

                // 右侧：绘图与表格
                Panel rightPanel = new() { Dock = DockStyle.Fill, Padding = new Padding(5, 0, 10, 10), BackColor = ColorBg };
                SplitContainer split = new() { Dock = DockStyle.Fill, Orientation = System.Windows.Forms.Orientation.Horizontal, SplitterDistance = 500, SplitterWidth = 6 };
                
                // 绘图区
                Panel chartBorder = new() { Dock = DockStyle.Fill, BackColor = ColorBorder, Padding = new Padding(1) };
                Panel chartContent = new() { Dock = DockStyle.Fill, BackColor = ColorPanel };
                Label lblChartTitle = new() { Text = "曲线监控 · 实时波形", Dock = DockStyle.Top, Height = 35, BackColor = ColorCard, ForeColor = ColorCyan, TextAlign = ContentAlignment.MiddleLeft, Padding = new Padding(10,0,0,0), Font = new Font("微软雅黑", 10, FontStyle.Bold) };
                formsPlot = new FormsPlot { Dock = DockStyle.Fill };
                ConfigurePlotStyle();
                
                chartContent.Controls.Add(formsPlot);
                chartContent.Controls.Add(lblChartTitle);
                chartBorder.Controls.Add(chartContent);
                split.Panel1.Controls.Add(chartBorder);

                // 表格区
                Panel tableBorder = new() { Dock = DockStyle.Fill, BackColor = ColorBorder, Padding = new Padding(1) };
                Panel tableContent = new() { Dock = DockStyle.Fill, BackColor = ColorPanel };
                Label lblTableTitle = new() { Text = "监控数据记录", Dock = DockStyle.Top, Height = 35, BackColor = ColorCard, ForeColor = ColorCyan, TextAlign = ContentAlignment.MiddleLeft, Padding = new Padding(10,0,0,0), Font = new Font("微软雅黑", 10, FontStyle.Bold) };
                dataGridView = new DataGridView { 
                    Dock = DockStyle.Fill, BackgroundColor = ColorPanel, BorderStyle = BorderStyle.None,
                    AllowUserToAddRows = false, RowHeadersVisible = false, ReadOnly = true, SelectionMode = DataGridViewSelectionMode.FullRowSelect,
                    AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill, EnableHeadersVisualStyles = false
                };
                dataGridView.ColumnHeadersDefaultCellStyle = new DataGridViewCellStyle { BackColor = ColorCard, ForeColor = ColorCyan, Font = new Font("微软雅黑", 10, FontStyle.Bold) };
                dataGridView.DefaultCellStyle = new DataGridViewCellStyle { BackColor = ColorPanel, ForeColor = Color.White, Font = new Font("Consolas", 11) };
                dataGridView.Columns.Add("Reg", "区域"); dataGridView.Columns.Add("Tag", "标签"); dataGridView.Columns.Add("Val", "当前值"); dataGridView.Columns.Add("Max", "峰值");

                tableContent.Controls.Add(dataGridView);
                tableContent.Controls.Add(lblTableTitle);
                tableBorder.Controls.Add(tableContent);
                split.Panel2.Controls.Add(tableBorder);
                rightPanel.Controls.Add(split);

                // 底部控制栏
                Panel bottomBar = new() { Dock = DockStyle.Bottom, Height = 70, BackColor = ColorBg, Padding = new Padding(20, 10, 20, 10) };
                FlowLayoutPanel ctrlFlow = new() { Dock = DockStyle.Fill, FlowDirection = FlowDirection.LeftToRight };

                Button btnStart = new Button { Text = "启动监控", Width = 120, Height = 40, BackColor = ColorGreen, ForeColor = Color.White, FlatStyle = FlatStyle.Flat, Font = new Font("微软雅黑", 10, FontStyle.Bold) };
                btnStart.FlatAppearance.BorderSize = 0;

                comboRange = new ComboBox { Width = 100, DropDownStyle = ComboBoxStyle.DropDownList, BackColor = ColorCard, ForeColor = Color.White, FlatStyle = FlatStyle.Flat, Font = new Font("微软雅黑", 10) };
                comboRange.Items.AddRange(new object[] { "15 秒", "1 分钟", "5 分钟", "15 分钟", "1 小时" }); comboRange.SelectedIndex = 1;

                cbAutoFollow = new CheckBox { Text = "自动跟随", ForeColor = ColorMuted, Checked = true, AutoSize = true, Margin = new Padding(10, 12, 0, 0) };
                cbAutoScaleY = new CheckBox { Text = "Y轴适应", ForeColor = ColorMuted, Checked = true, AutoSize = true, Margin = new Padding(10, 12, 0, 0) };
                cbShowCursor = new CheckBox { Text = "显示游标", ForeColor = ColorMuted, Checked = false, AutoSize = true, Margin = new Padding(10, 12, 0, 0) };
                
                Button btnClear = new Button { Text = "清空数据", Width = 100, Height = 40, BackColor = ColorRed, ForeColor = Color.White, FlatStyle = FlatStyle.Flat, Margin = new Padding(20, 0, 0, 0) };
                Button btnReset = new Button { Text = "复位坐标", Width = 100, Height = 40, BackColor = ColorBorder, ForeColor = Color.White, FlatStyle = FlatStyle.Flat };

                ctrlFlow.Controls.AddRange(new Control[] { btnStart, new Label{Text="跨度:", ForeColor=ColorMuted, Width=40, Margin=new Padding(20,12,0,0)}, comboRange, cbAutoFollow, cbAutoScaleY, cbShowCursor, btnClear, btnReset });
                bottomBar.Controls.Add(ctrlFlow);

                mainForm.Controls.Add(rightPanel);
                mainForm.Controls.Add(leftPanel);
                mainForm.Controls.Add(bottomBar);
                mainForm.Controls.Add(titleBar);

                // --- 交互逻辑绑定 ---

                btnStart.Click += (s, e) => {
                    if (btnStart.Text == "启动监控") {
                        try {
                            udpClient = new UDPClient();
                            udpClient.UdpClientInite(config.Network.LocalIP, config.Network.LocalPort);
                            udpClient.SendData += (t, d) => UpdateExternalData(d);
                            renderTimer.Start();
                            btnStart.Text = "停止监控"; btnStart.BackColor = ColorRed;
                            lblStatus.Text = "● 监控中"; lblStatus.ForeColor = ColorGreen;
                        } catch (Exception ex) { MessageBox.Show("UDP启动失败: " + ex.Message); }
                    } else {
                        renderTimer.Stop();
                        btnStart.Text = "启动监控"; btnStart.BackColor = ColorGreen;
                        lblStatus.Text = "● 已停止"; lblStatus.ForeColor = ColorRed;
                    }
                };

                btnClear.Click += (s, e) => {
                    lock(dataLock) {
                        tick = 0; packetCount = 0;
                        foreach (var v in variables) { Array.Clear(v.Data, 0, v.Data.Length); v.MaxValue = double.MinValue; if(v.SignalPlot != null) v.SignalPlot.MaxRenderIndex = 0; }
                        formsPlot.Plot.AxisAuto(); formsPlot.Refresh();
                    }
                };

                btnReset.Click += (s, e) => { formsPlot.Plot.AxisAuto(); formsPlot.Refresh(); };

                // 初始化游标
                vCursorLine = formsPlot.Plot.AddVerticalLine(0, color: ColorAmber, style: LineStyle.Dash); vCursorLine.IsVisible = false;
                vCursorLabel = formsPlot.Plot.AddAnnotation("", 10, 10); vCursorLabel.IsVisible = false;
                vCursorLabel.BackgroundColor = Color.FromArgb(200, 0, 0, 0); vCursorLabel.Font.Color = Color.White;

                formsPlot.MouseMove += (s, e) => {
                    if (!cbShowCursor.Checked) return;
                    (double x, double y) = formsPlot.GetMouseCoordinates();
                    vCursorLine.X = x; vCursorLine.IsVisible = true;
                    int idx = (int)(x * 30);
                    if (idx >= 0 && idx < tick) {
                        var sels = variables.Where(v => v.IsSelected).ToList();
                        if (sels.Any()) {
                            vCursorLabel.Label = $"T:{x:F2}s\n" + string.Join("\n", sels.Select(v => $"{v.Tag}:{v.Data[idx]:F2}"));
                            vCursorLabel.IsVisible = true;
                        }
                    } else { vCursorLabel.IsVisible = false; vCursorLine.IsVisible = false; }
                    formsPlot.Refresh();
                };

                renderTimer = new System.Windows.Forms.Timer { Interval = 33 };
                renderTimer.Tick += (s, e) => {
                    if (hasNewData) {
                        lock (dataLock) {
                            hasNewData = false;
                            if (cbAutoFollow.Checked) { double xMax = tick / 30.0; formsPlot.Plot.SetAxisLimitsX(Math.Max(0, xMax - (currentRangePoints / 30.0)), xMax); }
                            if (cbAutoScaleY.Checked && packetCount % 30 == 0) AutoScaleY();
                            UpdateTableUI(); formsPlot.Render();
                        }
                    }
                };

                tabBtns[0].PerformClick();
                Application.Run(mainForm);
            } catch (Exception ex) { MessageBox.Show(ex.Message); }
        }

        // --- 逻辑函数 ---

        private static void UpdateVariableList(string region) {
            variableListContainer.SuspendLayout();
            variableListContainer.Controls.Clear();
            var filtered = variables.Where(v => v.Region == region).ToList();
            foreach (var v in filtered) {
                Panel item = new Panel { Width = 280, Height = 55, BackColor = v.IsSelected ? Color.FromArgb(30, 58, 138) : ColorCard, Margin = new Padding(0, 2, 0, 2) };
                
                CheckBox cb = new CheckBox { Checked = v.IsSelected, Location = new Point(250, 18), AutoSize = true };
                Label lt = new Label { Text = v.Tag, ForeColor = Color.White, Font = new Font("微软雅黑", 10, FontStyle.Bold), Location = new Point(35, 5), AutoSize = true };
                Label ln = new Label { Text = v.Name.Split(':').Last(), ForeColor = ColorMuted, Font = new Font("微软雅黑", 8), Location = new Point(35, 25), AutoSize = true };
                Panel ind = new Panel { BackColor = v.Color, Size = new Size(10, 10), Location = new Point(15, 22) };

                cb.CheckedChanged += (s, e) => {
                    v.IsSelected = cb.Checked;
                    item.BackColor = v.IsSelected ? Color.FromArgb(30, 58, 138) : ColorCard;
                    if (v.IsSelected) {
                        v.SignalPlot = formsPlot.Plot.AddSignal(v.Data, 30, v.Color, v.Tag);
                        dataGridView.Rows.Add(v.Region.Substring(0, 2), v.Tag, "0.00", "0.00");
                    } else {
                        if (v.SignalPlot != null) { formsPlot.Plot.Remove(v.SignalPlot); v.SignalPlot = null; }
                        for (int i = dataGridView.Rows.Count - 1; i >= 0; i--) if (dataGridView.Rows[i].Cells[1].Value?.ToString() == v.Tag) dataGridView.Rows.RemoveAt(i);
                    }
                    lblSelectionCount.Text = $"已选: {variables.Count(x => x.IsSelected)} 项";
                    formsPlot.Refresh();
                };

                item.Controls.AddRange(new Control[] { cb, lt, ln, ind });
                variableListContainer.Controls.Add(item);
            }
            variableListContainer.ResumeLayout();
        }

        private static void AutoScaleY() {
            var selected = variables.Where(v => v.IsSelected).ToList();
            if (!selected.Any()) return;
            double min = double.MaxValue, max = double.MinValue;
            int start = Math.Max(0, tick - currentRangePoints);
            for (int i = start; i < tick; i++) foreach (var v in selected) { if (v.Data[i] < min) min = v.Data[i]; if (v.Data[i] > max) max = v.Data[i]; }
            if (max >= min) { double r = (max - min == 0) ? 1 : (max - min); formsPlot.Plot.SetAxisLimitsY(min - r * 0.1, max + r * 0.1); }
        }

        private static void UpdateTableUI() {
            foreach (DataGridViewRow row in dataGridView.Rows) {
                var v = variables.FirstOrDefault(x => x.Tag == row.Cells[1].Value?.ToString());
                if (v != null) {
                    row.Cells[2].Value = v.CurrentValue.ToString("F4");
                    row.Cells[3].Value = v.MaxValue.ToString("F4");
                    row.DefaultCellStyle.ForeColor = v.Color;
                }
            }
        }

        private static void UpdateExternalData(Dictionary<string, double> data) {
            lock (dataLock) {
                bool updated = false;
                foreach (var kvp in data) {
                    if (udpMappings.TryGetValue(kvp.Key, out var list)) {
                        foreach (var v in list) {
                            v.Data[tick] = kvp.Value; v.CurrentValue = kvp.Value;
                            if (kvp.Value > v.MaxValue) v.MaxValue = kvp.Value;
                            if (v.SignalPlot != null) v.SignalPlot.MaxRenderIndex = tick;
                            updated = true;
                        }
                    }
                }
                if (updated) { tick++; packetCount++; hasNewData = true; }
            }
        }

        private static void ConfigurePlotStyle() {
            formsPlot.Plot.Style(ScottPlot.Style.Black);
            formsPlot.Plot.XAxis.Label("时间 (Time/s)", ColorMuted);
            formsPlot.Plot.YAxis.Label("幅值 (Amplitude)", ColorMuted);
            formsPlot.Plot.Grid(true, Color.FromArgb(40, 255, 255, 255));
            formsPlot.Plot.Legend(true, Alignment.UpperRight).FillColor = Color.FromArgb(150, 0, 0, 0);
        }

        private static void LoadConfig() { config = new AppConfig { Network = new NetworkConfig { LocalIP = "127.0.0.1", LocalPort = 5810 } }; }

        private static void InitVariables() {
            variables.Clear(); udpMappings.Clear();
            var regs = new Dictionary<string, string[]>();
            
            // 严格按照您的截图中文名称还原字典
            regs.Add("3#柴油机仿真数据", new[] { 
                "Temp3:主机排气温度", "Z_speed3:A排增压器转速", "Z_SpeedB:B排增压器转速", 
                "A_EgasT:A列增压器废气温度", "B_EgasT:B列增压器废气温度", "As_Temp3:A排空冷器前空气温度",
                "Be_Temp3:A排空冷器后空气温度", "Be_Pa3:A排空冷器出口空气压力", "FuelRack3:油门", 
                "Power3:柴油机功率", "R_speed3:柴油机转速" 
            });
            regs.Add("4#柴油机仿真数据", new[] { 
                "Temp4:主机排气温度", "Z_Speed4:A排增压器转速", "Z_SpeedB2:B排增压器转速", 
                "A_EgasT2:A列增压器废气温度", "FuelRack4:油门", "Power4:柴油机功率", "R_speed4:柴油机转速" 
            });
            regs.Add("3#柴油机试验数据", new[] { "TempT2:主机排气温度", "Z_SpeedT2:A排增压器转速", "Z_SpeedBT2:B排增压器转速" });
            regs.Add("4#柴油机试验数据", new[] { "TempT:主机排气温度", "Z_SpeedT:A排增压器转速" });

            Color[] colors = { Color.Red, Color.Cyan, Color.Lime, Color.Yellow, Color.Magenta, Color.Orange, Color.White, Color.Pink, Color.Gold };
            int cIdx = 0;
            foreach (var r in regs) {
                foreach (var e in r.Value) {
                    var v = new ChartVariable { Name = e, Tag = e.Split(':')[0], Region = r.Key, Color = colors[cIdx++ % colors.Length] };
                    variables.Add(v);
                    if (!udpMappings.ContainsKey(v.Tag)) udpMappings[v.Tag] = new List<ChartVariable>();
                    udpMappings[v.Tag].Add(v);
                }
            }
        }
    }
}