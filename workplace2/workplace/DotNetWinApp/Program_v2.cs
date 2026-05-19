using System;
using System.Windows.Forms;
using System.Drawing;
using System.Collections.Generic;
using System.Linq;
using ScottPlot;
using ScottPlot.Plottable;
using System.Diagnostics;
using System.Text.Json;
using System.IO;
using System.Text;

namespace DotNetWinApp
{
    /// <summary>
    /// 核心数据模型：定义监测变量的所有属性
    /// </summary>
    public class ChartVariable
    {
        public string Name { get; set; }            // 变量显示名称
        public string Tag { get; set; }             // 通信标识符 (Tag)
        public string Region { get; set; }          // 所属区域 (如: 3#柴油机)
        [System.Text.Json.Serialization.JsonIgnore]
        public Color Color { get; set; }            // 曲线颜色
        
        public string ColorHtml 
        { 
            get => ColorTranslator.ToHtml(Color); 
            set => Color = ColorTranslator.FromHtml(value); 
        }

        public bool IsSelected { get; set; }        // 是否已被勾选监控
        public string DataType { get; set; } = "double"; // 变量数据类型 (int/float/double/string)
        
        // 数据缓存：使用数组存储历史点，容量 150000 (约 1.4 小时数据 @ 30Hz)
        [System.Text.Json.Serialization.JsonIgnore]
        public double[] Data { get; set; } = new double[150000]; 
        
        // 该变量可能在多个窗口中同时显示，维护一个 SignalPlot 列表
        [System.Text.Json.Serialization.JsonIgnore]
        public List<SignalPlot> SignalPlots { get; set; } = new List<SignalPlot>(); 

        
        public double CurrentValue { get; set; }    // 当前实时值
        public double MaxValue { get; set; } = double.MinValue; // 历史峰值
    }

    /// <summary>
    /// 动态曲线窗口控件：支持拖拽、缩放、右键菜单分析
    /// </summary>
    public class PlotWindow : UserControl
    {
        // 控件成员
        public FormsPlot PlotControl { get; private set; } // ScottPlot 绘图核心
        public Panel TitleBar { get; private set; }        // 自定义标题栏
        public Label TitleLabel { get; private set; }      // 标题文本
        public Button CloseBtn { get; private set; }       // 关闭按钮
        public Button AxisBtn { get; private set; }        // 坐标设置按钮
        
        // 游标成员
        public VLine CursorLine { get; private set; }
        public Annotation CursorLabel { get; private set; }
        
        // 状态属性
        public bool IsActive { get; private set; }         // 窗口是否处于激活状态（高亮显示）
        public List<ChartVariable> AttachedVariables { get; } = new List<ChartVariable>(); // 当前窗口关联的变量
        
        // 误差分析成员
        public SignalPlot ErrorSignal { get; set; }        // 误差曲线对象
        public double[] ErrorData { get; set; } = new double[150000]; // 误差数据缓存
        public bool ShowError { get; set; } = false;       // 是否显示误差分析
        public string ErrorType { get; set; } = "";        // 误差类型: "Diff" (数值) 或 "Percent" (百分比)

        private bool dragging = false;                     // 拖拽标志位
        private Point dragStart;                           // 拖拽起始坐标

        // 事件回调
        public event Action<PlotWindow> OnSelected;        // 窗口被选中点击时触发
        public event Action<PlotWindow> OnClosed;          // 窗口关闭时触发

        public PlotWindow(string title)
        {
            // 初始化控件样式
            this.Size = new Size(500, 350);
            this.Padding = new Padding(1);
            this.BackColor = Color.FromArgb(55, 65, 81);

            // 构建标题栏
            TitleBar = new Panel { Dock = DockStyle.Top, Height = 30, BackColor = Color.FromArgb(31, 41, 55), Cursor = Cursors.SizeAll };
            TitleLabel = new Label { Text = title, ForeColor = Color.FromArgb(6, 182, 212), Font = new Font("微软雅黑", 9, FontStyle.Bold), Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft, Padding = new Padding(5, 0, 0, 0) };
            
            CloseBtn = new Button { Text = "×", Width = 30, Dock = DockStyle.Right, FlatStyle = FlatStyle.Flat, ForeColor = Color.White, Font = new Font("Arial", 11, FontStyle.Bold) };
            CloseBtn.FlatAppearance.BorderSize = 0;
            CloseBtn.Click += (s, e) => OnClosed?.Invoke(this);

            AxisBtn = new Button { Text = "坐标", Width = 50, Dock = DockStyle.Right, FlatStyle = FlatStyle.Flat, ForeColor = Color.FromArgb(156, 163, 175), Font = new Font("微软雅黑", 9) };
            AxisBtn.FlatAppearance.BorderSize = 0;
            AxisBtn.Click += (s, e) => ShowAxisDialog();

            TitleBar.Controls.Add(TitleLabel);
            TitleBar.Controls.Add(AxisBtn);
            TitleBar.Controls.Add(CloseBtn);

            // 初始化绘图区
            PlotControl = new FormsPlot { Dock = DockStyle.Fill };
            PlotControl.Plot.Style(ScottPlot.Style.Black);
            PlotControl.Configuration.MiddleClickAutoAxis = false;
            PlotControl.Plot.Grid(true, Color.FromArgb(40, 255, 255, 255));
            PlotControl.Plot.XAxis.Label("时间 (秒)");
            
            // 设置图例样式
            var legend = PlotControl.Plot.Legend(true, Alignment.UpperRight);
            legend.FillColor = Color.FromArgb(180, 17, 24, 39);
            legend.FontColor = Color.White;
            legend.OutlineColor = Color.FromArgb(6, 182, 212);

            // 初始化游标对象
            CursorLine = PlotControl.Plot.AddVerticalLine(0, color: Color.FromArgb(245, 158, 11), style: LineStyle.Dash);
            CursorLine.IsVisible = false;
            CursorLabel = PlotControl.Plot.AddAnnotation("", 10, 10);
            CursorLabel.IsVisible = false;
            CursorLabel.BackgroundColor = Color.FromArgb(200, 0, 0, 0);
            CursorLabel.Font.Color = Color.White;

            this.Controls.Add(PlotControl);
            this.Controls.Add(TitleBar);

            // --- 游标逻辑 ---
            PlotControl.MouseMove += (s, e) => {
                if (Program.cbShowCursor == null || !Program.cbShowCursor.Checked) {
                    if (CursorLine.IsVisible) { CursorLine.IsVisible = false; CursorLabel.IsVisible = false; PlotControl.Refresh(); }
                    return;
                }
                (double x, double y) = PlotControl.GetMouseCoordinates();
                CursorLine.X = x;
                CursorLine.IsVisible = true;
                int idx = (int)(x * 30);
                if (idx >= 0 && idx < Program.tick) {
                    var info = string.Join("\n", AttachedVariables.Select(v => $"{v.Tag}: {v.Data[idx]:F2}"));
                    CursorLabel.Label = $"T: {x:F2}s\n{info}";
                    CursorLabel.IsVisible = true;
                } else {
                    CursorLabel.IsVisible = false;
                }
                PlotControl.Refresh();
            };

            // --- 右键菜单 ---
            ContextMenuStrip menu = new ContextMenuStrip();
            var itemDiff = new ToolStripMenuItem("误差分析 (数值误差)");
            var itemPerc = new ToolStripMenuItem("误差分析 (百分比误差)");
            var itemClear = new ToolStripMenuItem("关闭误差曲线");
            
            itemDiff.Click += (s, e) => ToggleErrorAnalysis("Diff");
            itemPerc.Click += (s, e) => ToggleErrorAnalysis("Percent");
            itemClear.Click += (s, e) => { 
                ShowError = false; 
                if (ErrorSignal != null) { PlotControl.Plot.Remove(ErrorSignal); ErrorSignal = null; PlotControl.Refresh(); } 
            };

            menu.Items.AddRange(new ToolStripItem[] { itemDiff, itemPerc, new ToolStripSeparator(), itemClear });
            PlotControl.ContextMenuStrip = menu;
            
            // 菜单弹出前的逻辑检查：至少需要两个变量才能对比
            menu.Opening += (s, e) => {
                bool canAnalyze = AttachedVariables.Count >= 2;
                itemDiff.Enabled = canAnalyze;
                itemPerc.Enabled = canAnalyze;
            };

            // --- 交互逻辑：窗口移动与激活 ---
            MouseEventHandler onDown = (s, e) => {
                if (e.Button == MouseButtons.Middle || (e.Button == MouseButtons.Left && (s == TitleBar || s == TitleLabel))) {
                    dragging = true;
                    dragStart = this.PointToClient(System.Windows.Forms.Cursor.Position);
                    SetActive(true);
                    OnSelected?.Invoke(this);
                    if (this.Dock != DockStyle.None) {
                        this.Dock = DockStyle.None; // 拖动时自动解除停靠
                        this.Size = new Size(500, 350);
                    }
                    ((Control)s).Capture = true; 
                }
                else if (e.Button == MouseButtons.Left && s == PlotControl) {
                    SetActive(true);
                    OnSelected?.Invoke(this);
                }
            };
            MouseEventHandler onMove = (s, e) => {
                if (dragging && this.Parent != null) {
                    Point p = this.Parent.PointToClient(System.Windows.Forms.Cursor.Position);
                    this.Location = new Point(p.X - dragStart.X, p.Y - dragStart.Y);
                }
            };
            MouseEventHandler onUp = (s, e) => {
                if (dragging) { dragging = false; ((Control)s).Capture = false; }
            };

            TitleBar.MouseDown += onDown; TitleBar.MouseMove += onMove; TitleBar.MouseUp += onUp;
            TitleLabel.MouseDown += onDown; TitleLabel.MouseMove += onMove; TitleLabel.MouseUp += onUp;
            PlotControl.MouseDown += onDown; PlotControl.MouseMove += onMove; PlotControl.MouseUp += onUp;

            // --- 交互逻辑：窗口缩放 ---
            Panel resizeGrip = new Panel { Size = new Size(10, 10), BackColor = Color.Transparent, Cursor = Cursors.SizeNWSE, Anchor = AnchorStyles.Bottom | AnchorStyles.Right };
            resizeGrip.Location = new Point(this.Width - 10, this.Height - 10);
            this.Controls.Add(resizeGrip);
            resizeGrip.BringToFront();

            bool resizing = false;
            Point resizeStart = Point.Empty;
            resizeGrip.MouseDown += (s, e) => { if (e.Button == MouseButtons.Left) { resizing = true; resizeStart = e.Location; resizeGrip.Capture = true; } };
            resizeGrip.MouseMove += (s, e) => {
                if (resizing) {
                    int newW = this.Width + (e.X - resizeStart.X);
                    int newH = this.Height + (e.Y - resizeStart.Y);
                    this.Size = new Size(Math.Max(200, newW), Math.Max(150, newH));
                    resizeGrip.Location = new Point(this.Width - 10, this.Height - 10);
                }
            };
            resizeGrip.MouseUp += (s, e) => { resizing = false; resizeGrip.Capture = false; };
        }

        /// <summary>
        /// 开启/切换误差分析曲线
        /// </summary>
        public void ToggleErrorAnalysis(string type)
        {
            if (AttachedVariables.Count < 2) return;
            ErrorType = type;
            ShowError = true;
            
            if (ErrorSignal != null) PlotControl.Plot.Remove(ErrorSignal);
            
            string label = type == "Diff" ? "误差(Abs)" : "误差(%)";
            // 添加一条新的信号线，使用白色高亮细虚线样式
            ErrorSignal = PlotControl.Plot.AddSignal(ErrorData, 30, Color.White, label);
            ErrorSignal.LineWidth = 1.5f;
            ErrorSignal.LineStyle = LineStyle.Dash;
            ErrorSignal.YAxisIndex = 1; // 使用右侧 Y 轴 (Index 1)
            
            // 配置右侧坐标轴显示
            PlotControl.Plot.YAxis2.Ticks(true);
            PlotControl.Plot.YAxis2.Label(label, Color.White);
            PlotControl.Plot.YAxis2.Color(Color.White);
            
            // 全量刷新历史数据计算
            for (int i = 0; i <= Program.tick; i++) UpdateErrorBuffer(i); 
            PlotControl.Refresh();
        }


        /// <summary>
        /// 更新误差缓冲区中的单个数据点
        /// </summary>
        public void UpdateErrorBuffer(int currentTick)
        {
            if (!ShowError || AttachedVariables.Count < 2) return;
            var v1 = AttachedVariables[0];
            var v2 = AttachedVariables[1];
            
            if (ErrorType == "Diff") {
                ErrorData[currentTick] = Math.Abs(v1.Data[currentTick] - v2.Data[currentTick]);
            } else {
                double baseVal = Math.Abs(v1.Data[currentTick]);
                ErrorData[currentTick] = (baseVal < 1e-9) ? 0 : (Math.Abs(v1.Data[currentTick] - v2.Data[currentTick]) / baseVal) * 100.0;
            }
            
            if (ErrorSignal != null) ErrorSignal.MaxRenderIndex = currentTick;
        }

        /// <summary>
        /// 弹出 Y 轴坐标设置对话框
        /// </summary>
        private void ShowAxisDialog()
        {
            Form f = new Form { Text = "坐标范围设置", Width = 300, Height = 200, StartPosition = FormStartPosition.CenterParent, BackColor = Color.FromArgb(17, 24, 39), ForeColor = Color.White, FormBorderStyle = FormBorderStyle.FixedToolWindow };
            Label l1 = new Label { Text = "Y轴最小值:", Location = new Point(20, 20), AutoSize = true };
            TextBox t1 = new TextBox { Text = PlotControl.Plot.GetAxisLimits().YMin.ToString(), Location = new Point(120, 18), Width = 120, BackColor = Color.FromArgb(31, 41, 55), ForeColor = Color.White, BorderStyle = BorderStyle.FixedSingle };
            Label l2 = new Label { Text = "Y轴最大值:", Location = new Point(20, 60), AutoSize = true };
            TextBox t2 = new TextBox { Text = PlotControl.Plot.GetAxisLimits().YMax.ToString(), Location = new Point(120, 58), Width = 120, BackColor = Color.FromArgb(31, 41, 55), ForeColor = Color.White, BorderStyle = BorderStyle.FixedSingle };
            Button btn = new Button { Text = "应用", Location = new Point(100, 110), Width = 100, Height = 30, BackColor = Color.FromArgb(6, 182, 212), FlatStyle = FlatStyle.Flat };
            btn.Click += (s, e) => {
                if (double.TryParse(t1.Text, out double min) && double.TryParse(t2.Text, out double max)) {
                    PlotControl.Plot.SetAxisLimitsY(min, max);
                    PlotControl.Refresh();
                    f.Close();
                }
            };
            f.Controls.AddRange(new Control[] { l1, t1, l2, t2, btn });
            f.ShowDialog();
        }

        /// <summary>
        /// 设置窗口激活状态及其视觉反馈
        /// </summary>
        public void SetActive(bool active)
        {
            IsActive = active;
            this.BackColor = active ? Color.FromArgb(6, 182, 212) : Color.FromArgb(55, 65, 81);
            TitleBar.BackColor = active ? Color.FromArgb(15, 118, 110) : Color.FromArgb(31, 41, 55);
        }

        /// <summary>
        /// 向窗口添加新的监测变量
        /// </summary>
        public void AddVariable(ChartVariable v, int tick)
        {
            if (AttachedVariables.Contains(v)) return;
            AttachedVariables.Add(v);
            
            // 如果是窗口的第一个变量，将标题颜色设为该变量颜色
            if (AttachedVariables.Count == 1) TitleLabel.ForeColor = v.Color;
            
            var sp = PlotControl.Plot.AddSignal(v.Data, 30, v.Color, v.Tag);
            sp.LineWidth = 1.5f;
            sp.MaxRenderIndex = tick;
            v.SignalPlots.Add(sp);
            PlotControl.Refresh();
        }

        /// <summary>
        /// 从窗口移除监测变量
        /// </summary>
        public void RemoveVariable(ChartVariable v)
        {
            AttachedVariables.Remove(v);
            var sp = v.SignalPlots.FirstOrDefault(p => PlotControl.Plot.GetPlottables().Contains(p));
            if (sp != null) { PlotControl.Plot.Remove(sp); v.SignalPlots.Remove(sp); }
            PlotControl.Refresh();
        }
    }

    /// <summary>
    /// 变量配置管理窗口：支持新增、修改、删除和变量类型选择
    /// </summary>
    public class ConfigForm : Form
    {
        private List<ChartVariable> vars;
        private Action onSaved;
        private ListBox lbVars;
        private TextBox tbTag, tbName, tbRegion;
        private ComboBox cbType; // 新增类型选择
        private Panel pColor;

        public ConfigForm(List<ChartVariable> variables, Action saveCallback)
        {
            this.vars = variables;
            this.onSaved = saveCallback;
            this.Text = "监控指标配置与自定义添加";
            this.Width = 600; this.Height = 550;
            this.BackColor = Color.FromArgb(10, 14, 23);
            this.ForeColor = Color.White;
            this.Font = new Font("微软雅黑", 9);
            this.StartPosition = FormStartPosition.CenterParent;

            // 左侧列表展示
            Panel left = new Panel { Dock = DockStyle.Left, Width = 250, Padding = new Padding(10) };
            lbVars = new ListBox { Dock = DockStyle.Fill, BackColor = Color.FromArgb(31, 41, 55), ForeColor = Color.White, BorderStyle = BorderStyle.None };
            lbVars.SelectedIndexChanged += LbVars_SelectedIndexChanged;
            left.Controls.Add(lbVars);

            // 右侧属性编辑
            Panel right = new Panel { Dock = DockStyle.Fill, Padding = new Padding(20) };
            Label l1 = new Label { Text = "标签 (Tag):", Location = new Point(20, 20), AutoSize = true };
            tbTag = new TextBox { Location = new Point(120, 18), Width = 200, BackColor = Color.FromArgb(31, 41, 55), ForeColor = Color.White };
            
            Label l2 = new Label { Text = "名称 (Name):", Location = new Point(20, 60), AutoSize = true };
            tbName = new TextBox { Location = new Point(120, 58), Width = 200, BackColor = Color.FromArgb(31, 41, 55), ForeColor = Color.White };
            
            Label l3 = new Label { Text = "区域 (Region):", Location = new Point(20, 100), AutoSize = true };
            tbRegion = new TextBox { Location = new Point(120, 98), Width = 200, BackColor = Color.FromArgb(31, 41, 55), ForeColor = Color.White };
            
            // --- 新增：变量类型选择 ---
            Label lType = new Label { Text = "数据类型:", Location = new Point(20, 140), AutoSize = true };
            cbType = new ComboBox { Location = new Point(120, 138), Width = 200, BackColor = Color.FromArgb(31, 41, 55), ForeColor = Color.White, DropDownStyle = ComboBoxStyle.DropDownList };
            cbType.Items.AddRange(new object[] { "double", "float", "int", "long", "string" });
            cbType.SelectedIndex = 0;

            Label l4 = new Label { Text = "线条颜色:", Location = new Point(20, 180), AutoSize = true };
            pColor = new Panel { Location = new Point(120, 178), Size = new Size(30, 20), BorderStyle = BorderStyle.FixedSingle, Cursor = Cursors.Hand };
            pColor.Click += (s, e) => { ColorDialog cd = new ColorDialog(); if (cd.ShowDialog() == DialogResult.OK) pColor.BackColor = cd.Color; };

            Button btnAdd = new Button { Text = "新增", Location = new Point(20, 240), Width = 70, Height = 30, BackColor = Color.FromArgb(16, 185, 129), FlatStyle = FlatStyle.Flat };
            btnAdd.Click += BtnAdd_Click;
            Button btnSave = new Button { Text = "修改", Location = new Point(100, 240), Width = 70, Height = 30, BackColor = Color.FromArgb(6, 182, 212), FlatStyle = FlatStyle.Flat };
            btnSave.Click += BtnUpdate_Click;
            Button btnDel = new Button { Text = "删除", Location = new Point(180, 240), Width = 70, Height = 30, BackColor = Color.FromArgb(239, 68, 68), FlatStyle = FlatStyle.Flat };
            btnDel.Click += BtnDel_Click;

            Button btnFinalSave = new Button { Text = "保存全量配置至文件", Location = new Point(20, 300), Width = 230, Height = 40, BackColor = Color.FromArgb(139, 92, 246), FlatStyle = FlatStyle.Flat, Font = new Font("微软雅黑", 10, FontStyle.Bold) };
            btnFinalSave.Click += (s, e) => {
                Program.SaveVariables();
                MessageBox.Show("变量配置已持久化保存！");
            };

            right.Controls.AddRange(new Control[] { l1, tbTag, l2, tbName, l3, tbRegion, lType, cbType, l4, pColor, btnAdd, btnSave, btnDel, btnFinalSave });

            this.Controls.Add(right);
            this.Controls.Add(left);
            RefreshList();
        }

        private void RefreshList() { lbVars.Items.Clear(); foreach (var v in vars) lbVars.Items.Add($"{v.Region} | {v.Tag}"); }
        
        private void LbVars_SelectedIndexChanged(object sender, EventArgs e) {
            if (lbVars.SelectedIndex >= 0) {
                var v = vars[lbVars.SelectedIndex];
                tbTag.Text = v.Tag; tbName.Text = v.Name; tbRegion.Text = v.Region; 
                pColor.BackColor = v.Color;
                cbType.SelectedItem = v.DataType ?? "double";
            }
        }

        private void BtnAdd_Click(object sender, EventArgs e) {
            if (string.IsNullOrEmpty(tbTag.Text)) return;
            vars.Add(new ChartVariable { 
                Tag = tbTag.Text, Name = tbName.Text, Region = tbRegion.Text, 
                Color = pColor.BackColor, DataType = cbType.SelectedItem.ToString() 
            });
            Program.UpdateUdpMappings();
            RefreshList(); onSaved?.Invoke();
        }

        private void BtnUpdate_Click(object sender, EventArgs e) {
            if (lbVars.SelectedIndex >= 0) {
                var v = vars[lbVars.SelectedIndex];
                v.Tag = tbTag.Text; v.Name = tbName.Text; v.Region = tbRegion.Text; 
                v.Color = pColor.BackColor; v.DataType = cbType.SelectedItem.ToString();
                Program.UpdateUdpMappings();
                RefreshList(); onSaved?.Invoke();
            }
        }

        private void BtnDel_Click(object sender, EventArgs e) {
            if (lbVars.SelectedIndex >= 0) {
                vars.RemoveAt(lbVars.SelectedIndex);
                Program.UpdateUdpMappings();
                RefreshList(); onSaved?.Invoke();
            }
        }
    }

    /// <summary>
    /// 主程序入口：负责全局状态管理、UDP 通信和 UI 布局
    /// </summary>
    static class Program
    {
        private static Form mainForm;
        private static List<ChartVariable> variables = new();        // 全局变量池
        private static Panel plotHostPanel;                          // 绘图窗口容器
        private static List<PlotWindow> plotWindows = new();         // 活跃的曲线窗口列表
        private static PlotWindow activePlotWindow = null;           // 当前激活的窗口
        private static DataGridView dataGridView;                    // 底部数据表
        private static System.Windows.Forms.Timer renderTimer;       // 渲染定时器 (约 30FPS)
        private static UDPClient udpClient;                          // UDP 接收客户端
        internal static int tick = 0;                                // 仿真时间步长 (30Hz)
        
        // 存储 Tag 与变量对象的映射，用于快速数据分发
        private static readonly Dictionary<string, List<ChartVariable>> udpMappings = new(StringComparer.OrdinalIgnoreCase);
        
        private static AppConfig config;                             // 通信配置
        private static bool hasNewData = false;                      // 数据更新标志
        private static readonly object dataLock = new();             // 线程锁
        private static int currentRangePoints = 1800;                // 当前时间跨度点数 (默认 1分钟)
        
        // UI 控件引用
        internal static CheckBox cbAutoFollow, cbAutoScaleY, cbAutoScaleAll, cbShowCursor;
        private static ComboBox comboRange, comboConfigs;
        private static Label lblStatus, lblSelectionCount;
        private static int packetCount = 0;
        private static FlowLayoutPanel variableListContainer;
        private static Button[] tabBtns;
        private static string currentRegion = "";

        // 配置保存路径
        private static readonly string LayoutDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "layouts");
        private static readonly string VarsPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "variables.json");

        // 全局配色方案 (Modern Dark UI)

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

        // 基础配置模型
        public class AppConfig { public NetworkConfig Network { get; set; } }
        public class NetworkConfig { public string LocalIP { get; set; } public int LocalPort { get; set; } }

        // 布局序列化模型
        public class LayoutConfig { public List<WindowConfig> Windows { get; set; } = new(); }
        public class WindowConfig {
            public string Title { get; set; }
            public int X { get; set; }
            public int Y { get; set; }
            public int W { get; set; }
            public int H { get; set; }
            public List<string> Tags { get; set; } = new();
            public bool ShowError { get; set; }
            public string ErrorType { get; set; }
        }

        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            try 
            {
                // 初始化配置与数据源
                LoadConfig();
                InitVariables(); 

                // 初始化主窗口
                mainForm = new Form { 
                    Text = "柴油机实时监控与数据校验系统 - 增强布局版", 
                    Width = 1600, Height = 900, 
                    BackColor = ColorBg, StartPosition = FormStartPosition.CenterScreen 
                };

                mainForm.FormClosed += (s, e) => {
                    renderTimer?.Stop();
                    if (udpClient != null) { try { (udpClient as IDisposable)?.Dispose(); } catch { } }
                    Process.GetCurrentProcess().Kill(); 
                };

                // --- 1. 顶部标题栏 ---
                Panel titleBar = new Panel { Dock = DockStyle.Top, Height = 60, BackColor = ColorBg };
                Label lblTitle = new Label { 
                    Text = ">>>> 柴油机实时监控与数据校验工具 <<<<", 
                    ForeColor = ColorCyanBright, Font = new Font("微软雅黑", 18, FontStyle.Bold), 
                    TextAlign = ContentAlignment.MiddleCenter, Dock = DockStyle.Fill 
                };
                lblStatus = new Label { Text = "● 系统就绪", ForeColor = ColorMuted, AutoSize = true, Font = new Font("微软雅黑", 10, FontStyle.Bold), Anchor = AnchorStyles.Right, Location = new Point(mainForm.Width - 150, 20) };
                titleBar.Controls.Add(lblStatus);
                titleBar.Controls.Add(lblTitle);

                // --- 2. 底部控制栏 ---
                Panel bottomBar = new Panel { Dock = DockStyle.Bottom, Height = 70, BackColor = ColorBg, Padding = new Padding(20, 10, 20, 10) };
                FlowLayoutPanel ctrlFlow = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.LeftToRight };
                
                Button btnStart = CreateStyledButton("启动监控", ColorGreen);
                
                comboRange = new ComboBox { Width = 100, DropDownStyle = ComboBoxStyle.DropDownList, BackColor = ColorCard, ForeColor = Color.White, FlatStyle = FlatStyle.Flat, Font = new Font("微软雅黑", 10), Margin = new Padding(0, 5, 0, 0) };
                comboRange.Items.AddRange(new object[] { "15 秒", "1 分钟", "5 分钟", "15 分钟", "1 小时" }); 
                comboRange.SelectedIndex = 1;
                comboRange.SelectedIndexChanged += (s, e) => {
                    int[] pts = { 450, 1800, 9000, 27000, 108000 };
                    if (comboRange.SelectedIndex >= 0) {
                        currentRangePoints = pts[comboRange.SelectedIndex];
                        foreach (var pw in plotWindows) UpdateXAxisRange(pw);
                    }
                };

                cbAutoFollow = new CheckBox { Text = "自动跟随", ForeColor = ColorMuted, Checked = true, AutoSize = true, Margin = new Padding(15, 12, 0, 0) };
                cbAutoScaleY = new CheckBox { Text = "Y轴适应", ForeColor = ColorMuted, Checked = true, AutoSize = true, Margin = new Padding(15, 12, 0, 0) };
                cbAutoScaleAll = new CheckBox { Text = "全自动缩放", ForeColor = ColorMuted, Checked = false, AutoSize = true, Margin = new Padding(15, 12, 0, 0) };
                cbShowCursor = new CheckBox { Text = "显示游标", ForeColor = ColorMuted, Checked = false, AutoSize = true, Margin = new Padding(15, 12, 0, 0) };
                
                Button btnClear = CreateStyledButton("清空数据", ColorRed);
                Button btnReset = CreateStyledButton("复位坐标", ColorBorder);
                Button btnConfig = CreateStyledButton("指标配置", ColorAmber);
                
                // 方案选择下拉框
                comboConfigs = new ComboBox { Width = 150, DropDownStyle = ComboBoxStyle.DropDownList, BackColor = ColorCard, ForeColor = Color.White, FlatStyle = FlatStyle.Flat, Font = new Font("微软雅黑", 9), Margin = new Padding(15, 8, 0, 0) };
                comboConfigs.SelectedIndexChanged += (s, e) => {
                    if (comboConfigs.SelectedIndex > 0) LoadLayout(Path.Combine(LayoutDir, comboConfigs.SelectedItem.ToString() + ".json"));
                };

                // 修改后的保存/加载按钮
                Button btnSaveCfg = CreateStyledButton("保存配置...", Color.FromArgb(139, 92, 246));
                Button btnLoadCfg = CreateStyledButton("导入配置...", Color.FromArgb(16, 185, 129));
                
                ctrlFlow.Controls.AddRange(new Control[] { btnStart, new Label{Text="跨度:", ForeColor=ColorMuted, Width=40, Margin=new Padding(10,12,0,0)}, comboRange, cbAutoFollow, cbAutoScaleY, cbAutoScaleAll, cbShowCursor, btnClear, btnReset, btnConfig, btnSaveCfg, btnLoadCfg, new Label{Text="方案:", ForeColor=ColorMuted, Width=40, Margin=new Padding(15,12,0,0)}, comboConfigs });
                bottomBar.Controls.Add(ctrlFlow);

                // --- 3. 左侧面板：监测指标体系 ---
                Panel leftPanel = new Panel { Width = 320, Dock = DockStyle.Left, Padding = new Padding(10, 0, 0, 0), BackColor = ColorBg };
                Button btnHideLeft = new Button { Text = "▼", Width = 20, Height = 60, FlatStyle = FlatStyle.Flat, BackColor = ColorCard, ForeColor = ColorCyan, Dock = DockStyle.Right };
                btnHideLeft.FlatAppearance.BorderSize = 0;
                
                Panel leftBorder = new Panel { Dock = DockStyle.Fill, BackColor = ColorBorder, Padding = new Padding(1) };
                Panel leftContent = new Panel { Dock = DockStyle.Fill, BackColor = ColorPanel };
                Label lblLeftTitle = new Label { Text = "监测指标体系 (拖拽创建)", Dock = DockStyle.Top, Height = 40, BackColor = ColorCard, ForeColor = ColorCyan, TextAlign = ContentAlignment.MiddleLeft, Padding = new Padding(10,0,0,0), Font = new Font("微软雅黑", 10, FontStyle.Bold) };
                
                // 区域切换 Tab
                TableLayoutPanel tabGrid = new TableLayoutPanel { Dock = DockStyle.Top, Height = 80, ColumnCount = 2, RowCount = 2, Padding = new Padding(5) };
                tabGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50f));
                tabGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50f));
                string[] regionList = { "3#柴油机仿真数据", "4#柴油机仿真数据", "3#柴油机试验数据", "4#柴油机试验数据" };
                tabBtns = new Button[4];
                for (int i = 0; i < 4; i++) {
                    int idx = i;
                    tabBtns[i] = new Button { Text = regionList[i].Replace("柴油机数据", ""), Dock = DockStyle.Fill, FlatStyle = FlatStyle.Flat, BackColor = ColorCard, ForeColor = ColorMuted, Font = new Font("微软雅黑", 8, FontStyle.Bold), Margin = new Padding(2) };
                    tabBtns[i].FlatAppearance.BorderSize = 0;
                    tabBtns[idx].Click += (s, e) => {
                        foreach (var b in tabBtns) { b.BackColor = ColorCard; b.ForeColor = ColorMuted; }
                        tabBtns[idx].BackColor = Color.FromArgb(15, 118, 110); tabBtns[idx].ForeColor = Color.White;
                        currentRegion = regionList[idx];
                        UpdateVariableList(currentRegion);
                    };
                    tabGrid.Controls.Add(tabBtns[i], i % 2, i / 2);
                }
                
                variableListContainer = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoScroll = true, FlowDirection = FlowDirection.TopDown, WrapContents = false, Padding = new Padding(5), BackColor = ColorPanel };
                lblSelectionCount = new Label { Text = "已选: 0 项", Dock = DockStyle.Bottom, Height = 30, ForeColor = ColorCyan, TextAlign = ContentAlignment.MiddleCenter, Font = new Font("微软雅黑", 9), BackColor = ColorCard };
                
                leftContent.Controls.Add(variableListContainer);
                leftContent.Controls.Add(tabGrid);
                leftContent.Controls.Add(lblSelectionCount);
                leftContent.Controls.Add(lblLeftTitle);
                leftBorder.Controls.Add(leftContent);
                leftPanel.Controls.Add(leftBorder);
                leftPanel.Controls.Add(btnHideLeft);

                // 侧边栏收缩逻辑
                btnHideLeft.Click += (s, e) => {
                    if (leftPanel.Width > 50) { leftPanel.Width = 35; btnHideLeft.Text = "▼"; }
                    else { leftPanel.Width = 320; btnHideLeft.Text = "▼"; }
                };

                // --- 4. 右侧内容区：曲线与表格 ---
                Panel rightPanel = new Panel { Dock = DockStyle.Fill, Padding = new Padding(5, 0, 10, 0), BackColor = ColorBg };
                SplitContainer split = new SplitContainer { Dock = DockStyle.Fill, Orientation = System.Windows.Forms.Orientation.Horizontal, SplitterDistance = 500, SplitterWidth = 6 };

                
                // 曲线区域
                Panel chartBorder = new Panel { Dock = DockStyle.Fill, BackColor = ColorBorder, Padding = new Padding(1) };
                plotHostPanel = new Panel { Dock = DockStyle.Fill, BackColor = ColorPanel, AllowDrop = true };
                Label lblChartTitle = new Label { Text = "曲线监控区域 (拖拽变量至此)", Dock = DockStyle.Top, Height = 35, BackColor = ColorCard, ForeColor = ColorCyan, TextAlign = ContentAlignment.MiddleLeft, Padding = new Padding(10,0,0,0), Font = new Font("微软雅黑", 10, FontStyle.Bold) };
                
                // 底部面板折叠按钮
                Button btnHideBottom = new Button { Text = "▼", Width = 30, Dock = DockStyle.Right, FlatStyle = FlatStyle.Flat, BackColor = ColorCard, ForeColor = ColorCyan };
                btnHideBottom.FlatAppearance.BorderSize = 0;
                lblChartTitle.Controls.Add(btnHideBottom);
                btnHideBottom.BringToFront();
                btnHideBottom.Click += (s, e) => {
                    split.Panel2Collapsed = !split.Panel2Collapsed;
                    btnHideBottom.Text = split.Panel2Collapsed ? "▲" : "▼";
                };

                chartBorder.Controls.Add(plotHostPanel);
                chartBorder.Controls.Add(lblChartTitle);
                split.Panel1.Controls.Add(chartBorder);

                // 数据表区域
                Panel tableBorder = new Panel { Dock = DockStyle.Fill, BackColor = ColorBorder, Padding = new Padding(1) };
                Panel tableContent = new Panel { Dock = DockStyle.Fill, BackColor = ColorPanel };
                Label lblTableTitle = new Label { Text = "监控数据记录", Dock = DockStyle.Top, Height = 35, BackColor = ColorCard, ForeColor = ColorCyan, TextAlign = ContentAlignment.MiddleLeft, Padding = new Padding(10,0,0,0), Font = new Font("微软雅黑", 10, FontStyle.Bold) };
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

                mainForm.Controls.Add(rightPanel);
                mainForm.Controls.Add(leftPanel);
                mainForm.Controls.Add(bottomBar);
                mainForm.Controls.Add(titleBar);

                // --- 交互与生命周期事件 ---
                btnSaveCfg.Click += (s, e) => SaveLayout();
                btnLoadCfg.Click += (s, e) => LoadLayout();
                btnConfig.Click += (s, e) => { 
                    new ConfigForm(variables, () => { for(int i=0; i<4; i++) if(tabBtns[i].BackColor != ColorCard) tabBtns[i].PerformClick(); }).ShowDialog(); 
                };

                // 拖拽落点逻辑：释放鼠标生成新窗口
                plotHostPanel.DragEnter += (s, e) => { if (e.Data.GetDataPresent(typeof(ChartVariable))) e.Effect = DragDropEffects.Copy; };
                plotHostPanel.DragDrop += (s, e) => {
                    ChartVariable v = e.Data.GetData(typeof(ChartVariable)) as ChartVariable;
                    if (v != null) CreateNewPlotWindow(v, plotHostPanel.PointToClient(new Point(e.X, e.Y)));
                };

                // 监控启停逻辑
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

                // 清空数据重置仿真状态
                btnClear.Click += (s, e) => {
                    lock(dataLock) {
                        tick = 0; packetCount = 0;
                        foreach (var v in variables) { Array.Clear(v.Data, 0, v.Data.Length); v.MaxValue = double.MinValue; v.SignalPlots.Clear(); }
                        foreach (var pw in plotWindows) { pw.PlotControl.Plot.Clear(); pw.PlotControl.Refresh(); }
                    }
                };

                btnReset.Click += (s, e) => { 
                    cbAutoFollow.Checked = false; cbAutoScaleY.Checked = false;
                    foreach (var pw in plotWindows) { pw.PlotControl.Plot.AxisAuto(); pw.PlotControl.Refresh(); }
                };

                // 主渲染定时器
                renderTimer = new System.Windows.Forms.Timer { Interval = 33 }; // 约 30FPS
                renderTimer.Tick += (s, e) => {
                    if (hasNewData) {
                        lock (dataLock) {
                            hasNewData = false;
                            UpdateAllPlots();
                            UpdateTableUI();
                        }
                    }
                };

                // 默认加载第一个 Tab
                tabBtns[0].PerformClick();
                RefreshConfigList();
                Application.Run(mainForm);
            } catch (Exception ex) { MessageBox.Show(ex.Message); }
        }

        /// <summary>
        /// 功能1：保存曲线配置至自定义文件
        /// </summary>
        private static void SaveLayout()
        {
            try {
                if (!Directory.Exists(LayoutDir)) Directory.CreateDirectory(LayoutDir);
                SaveFileDialog sfd = new SaveFileDialog { 
                    Filter = "JSON 配置文件|*.json", 
                    Title = "保存曲线布局配置",
                    InitialDirectory = LayoutDir
                };
                if (sfd.ShowDialog() == DialogResult.OK) {
                    var config = new LayoutConfig();
                    foreach (var pw in plotWindows) {
                        config.Windows.Add(new WindowConfig {
                            Title = pw.TitleLabel.Text,
                            X = pw.Location.X, Y = pw.Location.Y, W = pw.Width, H = pw.Height,
                            Tags = pw.AttachedVariables.Select(v => v.Tag).ToList(),
                            ShowError = pw.ShowError, ErrorType = pw.ErrorType
                        });
                    }
                    File.WriteAllText(sfd.FileName, JsonSerializer.Serialize(config, new JsonSerializerOptions { WriteIndented = true }));
                    RefreshConfigList();
                    MessageBox.Show("配置保存成功！");
                }
            } catch (Exception ex) { MessageBox.Show("保存失败: " + ex.Message); }
        }

        /// <summary>
        /// 刷新底部方案列表
        /// </summary>
        private static void RefreshConfigList()
        {
            if (comboConfigs == null) return;
            comboConfigs.Items.Clear();
            comboConfigs.Items.Add("-- 请选择方案 --");
            if (Directory.Exists(LayoutDir)) {
                var files = Directory.GetFiles(LayoutDir, "*.json");
                foreach (var f in files) comboConfigs.Items.Add(Path.GetFileNameWithoutExtension(f));
            }
            comboConfigs.SelectedIndex = 0;
        }

        /// <summary>
        /// 功能1：从自定义文件导入曲线配置
        /// </summary>
        private static void LoadLayout(string specificPath = null)
        {
            try {
                string path = specificPath;
                if (string.IsNullOrEmpty(path)) {
                    OpenFileDialog ofd = new OpenFileDialog { Filter = "JSON 配置文件|*.json", Title = "导入曲线布局配置", InitialDirectory = LayoutDir };
                    if (ofd.ShowDialog() == DialogResult.OK) path = ofd.FileName;
                }
                
                if (string.IsNullOrEmpty(path) || !File.Exists(path)) return;
                
                var cfg = JsonSerializer.Deserialize<LayoutConfig>(File.ReadAllText(path));
                if (cfg == null) return;

                // 清空当前所有窗口
                foreach (var pw in plotWindows.ToList()) pw.CloseBtn.PerformClick();
                
                // 恢复窗口布局
                foreach (var wc in cfg.Windows) {
                    if (wc.Tags.Count == 0) continue;
                    var firstVar = variables.FirstOrDefault(v => v.Tag == wc.Tags[0]);
                    if (firstVar == null) continue;
                    
                    var pw = new PlotWindow(wc.Title) { Location = new Point(wc.X, wc.Y), Size = new Size(wc.W, wc.H) };
                    
                    // 注册窗口事件
                    pw.OnSelected += (win) => { foreach (var w in plotWindows) w.SetActive(w == win); activePlotWindow = win; };
                    pw.OnClosed += (win) => {
                        plotWindows.Remove(win); plotHostPanel.Controls.Remove(win);
                        if (activePlotWindow == win) activePlotWindow = plotWindows.LastOrDefault();
                        
                        foreach(var av in win.AttachedVariables.ToList()) {
                            av.SignalPlots.RemoveAll(p => win.PlotControl.Plot.GetPlottables().Contains(p));
                            bool stillInUse = plotWindows.Any(w => w.AttachedVariables.Contains(av));
                            if (!stillInUse) {
                                av.IsSelected = false;
                                RemoveVariableFromTable(av);
                            }
                        }
                        UpdateVariableList(currentRegion);
                        lblSelectionCount.Text = $"已选: {variables.Count(x => x.IsSelected)} 项";
                    };

                    plotWindows.Add(pw); plotHostPanel.Controls.Add(pw); pw.BringToFront();
                    
                    // 恢复变量挂载
                    foreach (var tag in wc.Tags) {
                        var v = variables.FirstOrDefault(x => x.Tag == tag);
                        if (v != null) { pw.AddVariable(v, tick); AddVariableToTable(v); v.IsSelected = true; }
                    }
                    
                    // 恢复误差分析状态
                    if (wc.ShowError) pw.ToggleErrorAnalysis(wc.ErrorType);
                }
                
                // 刷新 UI 状态
                if (tabBtns != null) {
                    foreach (var btn in tabBtns) if (btn.BackColor != ColorCard) { UpdateVariableList(btn.Text + "数据"); break; }
                }
            } catch (Exception ex) { MessageBox.Show("加载失败: " + ex.Message); }
        }

        /// <summary>
        /// 核心方法：创建并初始化新的曲线绘图窗口
        /// </summary>
        private static void CreateNewPlotWindow(ChartVariable v, Point pos)
        {
            var pw = new PlotWindow(v.Tag + " 曲线窗口") { Location = pos };
            pw.OnSelected += (win) => { foreach (var w in plotWindows) w.SetActive(w == win); activePlotWindow = win; };
            pw.OnClosed += (win) => {
                plotWindows.Remove(win); plotHostPanel.Controls.Remove(win);
                if (activePlotWindow == win) activePlotWindow = plotWindows.LastOrDefault();
                
                foreach(var av in win.AttachedVariables.ToList()) {
                    av.SignalPlots.RemoveAll(p => win.PlotControl.Plot.GetPlottables().Contains(p));
                    // 检查该变量是否还在其他活跃窗口中
                    bool stillInUse = plotWindows.Any(w => w.AttachedVariables.Contains(av));
                    if (!stillInUse) {
                        av.IsSelected = false;
                        RemoveVariableFromTable(av);
                    }
                }
                UpdateVariableList(currentRegion);
                lblSelectionCount.Text = $"已选: {variables.Count(x => x.IsSelected)} 项";
            };
            plotWindows.Add(pw); plotHostPanel.Controls.Add(pw); pw.BringToFront();
            v.IsSelected = true;
            pw.AddVariable(v, tick); AddVariableToTable(v); pw.SetActive(true); activePlotWindow = pw;
            UpdateVariableList(currentRegion);
            lblSelectionCount.Text = $"已选: {variables.Count(x => x.IsSelected)} 项";
            
            foreach (var w in plotWindows.Where(x => x != pw)) w.SetActive(false);
            
            // 初始化 X 轴范围
            UpdateXAxisRange(pw);
        }

        /// <summary>
        /// 统一更新 X 轴时间显示范围
        /// </summary>
        private static void UpdateXAxisRange(PlotWindow pw)
        {
            if (cbAutoScaleAll != null && cbAutoScaleAll.Checked) {
                // 【全自动缩放】：强制 X 轴从 0 开始适应当前数据跨度，Y 轴自动缩放
                double xMax = Math.Max(0.1, tick / 30.0);
                pw.PlotControl.Plot.SetAxisLimitsX(0, xMax);
                pw.PlotControl.Plot.AxisAutoY();
            } else {
                // 【普通模式】：遵循“时间跨度”下拉框的选择（如仅显示最后 15s）
                double rangeSec = currentRangePoints / 30.0;
                double xMax = Math.Max(tick / 30.0, rangeSec);
                double xMin = xMax - rangeSec;
                pw.PlotControl.Plot.SetAxisLimitsX(xMin, xMax);
            }
            pw.PlotControl.Refresh();
        }

        /// <summary>
        /// 实时重建 UDP 标签与变量的映射关系，确保新增变量能立即接收数据
        /// </summary>
        public static void UpdateUdpMappings()
        {
            lock (dataLock) {
                udpMappings.Clear();
                foreach (var v in variables) {
                    if (string.IsNullOrEmpty(v.Tag)) continue;
                    if (!udpMappings.ContainsKey(v.Tag)) udpMappings[v.Tag] = new List<ChartVariable>();
                    udpMappings[v.Tag].Add(v);
                }
            }
        }

        /// <summary>
        /// 每一帧刷新所有曲线窗口的坐标系与渲染
        /// </summary>
        private static void UpdateAllPlots()
        {
            foreach (var pw in plotWindows) {
                // 如果开启了误差分析，实时更新误差点
                if (pw.ShowError) pw.UpdateErrorBuffer(tick > 0 ? tick - 1 : 0);
                
                // 处理全自动缩放或自动跟随
                if (cbAutoScaleAll.Checked || cbAutoFollow.Checked) {
                    UpdateXAxisRange(pw);
                }
                
                // 如果未开启全自动模式，但开启了 Y 轴适应，则按原逻辑执行周期性 Y 轴缩放
                if (!cbAutoScaleAll.Checked && cbAutoScaleY.Checked && packetCount % 30 == 0 && pw.AttachedVariables.Any()) {
                    double min = double.MaxValue, max = double.MinValue;
                    int start = Math.Max(0, tick - currentRangePoints);
                    for (int i = start; i < tick; i++) {
                        foreach (var v in pw.AttachedVariables) { 
                            if (v.Data[i] < min) min = v.Data[i]; 
                            if (v.Data[i] > max) max = v.Data[i]; 
                        }
                    }
                    if (max >= min) { 
                        double r = (max - min == 0) ? 1 : (max - min); 
                        pw.PlotControl.Plot.SetAxisLimitsY(min - r * 0.15, max + r * 0.15); 
                    }
                }
                pw.PlotControl.Render(); // 触发 ScottPlot 内部重绘
            }
        }

        /// <summary>
        /// 将变量信息注册到下方的监控列表表格中
        /// </summary>
        private static void AddVariableToTable(ChartVariable v)
        {
            foreach (DataGridViewRow row in dataGridView.Rows) if (row.Cells[1].Value?.ToString() == v.Tag) return;
            dataGridView.Rows.Add(v.Region.Substring(0, 2), v.Tag, "0.0000", "0.0000");
        }

        private static void RemoveVariableFromTable(ChartVariable v)
        {
            for (int i = dataGridView.Rows.Count - 1; i >= 0; i--) {
                if (dataGridView.Rows[i].Cells[1].Value?.ToString() == v.Tag) {
                    dataGridView.Rows.RemoveAt(i);
                }
            }
        }

        /// <summary>
        /// 刷新左侧变量指标卡片列表
        /// </summary>
        private static void UpdateVariableList(string region) {
            variableListContainer.SuspendLayout();
            variableListContainer.Controls.Clear();
            foreach (var v in variables.Where(v => v.Region == region)) {
                Panel item = new Panel { Width = 280, Height = 55, BackColor = v.IsSelected ? Color.FromArgb(30, 58, 138) : ColorCard, Margin = new Padding(5, 2, 0, 2), Cursor = Cursors.Hand };
                CheckBox cb = new CheckBox { Checked = v.IsSelected, Location = new Point(250, 18), AutoSize = true };
                Label lt = new Label { Text = v.Tag, ForeColor = v.Color, Font = new Font("微软雅黑", 10, FontStyle.Bold), Location = new Point(35, 5), AutoSize = true };
                
                // 辅助显示变量类型
                Label ln = new Label { Text = $"{v.DataType} | {v.Name?.Split(':').Last()}", ForeColor = ColorMuted, Font = new Font("微软雅黑", 8), Location = new Point(35, 25), AutoSize = true };
                Panel ind = new Panel { BackColor = v.Color, Size = new Size(10, 10), Location = new Point(15, 22) };

                // 变量勾选逻辑
                cb.CheckedChanged += (s, e) => {
                    v.IsSelected = cb.Checked;
                    item.BackColor = v.IsSelected ? Color.FromArgb(30, 58, 138) : ColorCard;
                    if (v.IsSelected) {
                        if (activePlotWindow == null) { CreateNewPlotWindow(v, new Point(10, 10)); activePlotWindow.Dock = DockStyle.Fill; }
                        else activePlotWindow.AddVariable(v, tick);
                        AddVariableToTable(v);
                    } else {
                        foreach (var pw in plotWindows) pw.RemoveVariable(v);
                        RemoveVariableFromTable(v);
                    }
                    lblSelectionCount.Text = $"已选: {variables.Count(x => x.IsSelected)} 项";
                };

                // --- 交互设计：支持直接拖拽卡片创建窗口 ---
                Point dragStartPos = Point.Empty;
                item.MouseDown += (s, e) => { if (e.Button == MouseButtons.Left) dragStartPos = e.Location; };
                item.MouseMove += (s, e) => {
                    if (e.Button == MouseButtons.Left && dragStartPos != Point.Empty) {
                        if (Math.Abs(e.X - dragStartPos.X) > SystemInformation.DragSize.Width || Math.Abs(e.Y - dragStartPos.Y) > SystemInformation.DragSize.Height) {
                            item.DoDragDrop(v, DragDropEffects.Copy); dragStartPos = Point.Empty;
                        }
                    }
                };
                item.MouseUp += (s, e) => { if (e.Button == MouseButtons.Left && dragStartPos != Point.Empty) { cb.Checked = !cb.Checked; dragStartPos = Point.Empty; } };

                item.Controls.AddRange(new Control[] { cb, lt, ln, ind });
                // 子控件联动
                foreach(Control c in item.Controls) if (!(c is CheckBox)) {
                    c.MouseDown += (ss, ee) => { if (ee.Button == MouseButtons.Left) dragStartPos = item.PointToClient(c.PointToScreen(ee.Location)); };
                    c.MouseMove += (ss, ee) => {
                        if (ee.Button == MouseButtons.Left && dragStartPos != Point.Empty) {
                            Point curr = item.PointToClient(c.PointToScreen(ee.Location));
                            if (Math.Abs(curr.X - dragStartPos.X) > SystemInformation.DragSize.Width || Math.Abs(curr.Y - dragStartPos.Y) > SystemInformation.DragSize.Height) {
                                item.DoDragDrop(v, DragDropEffects.Copy); dragStartPos = Point.Empty;
                            }
                        }
                    };
                    c.MouseUp += (ss, ee) => { if (ee.Button == MouseButtons.Left && dragStartPos != Point.Empty) { cb.Checked = !cb.Checked; dragStartPos = Point.Empty; } };
                }
                variableListContainer.Controls.Add(item);
            }
            variableListContainer.ResumeLayout();
        }

        /// <summary>
        /// 更新底部数据表的实时数值与峰值
        /// </summary>
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

        /// <summary>
        /// 通信回调：接收 UDP 数据分发至对应的变量缓存
        /// </summary>
        private static void UpdateExternalData(Dictionary<string, double> data) {
            lock (dataLock) {
                bool updated = false;
                foreach (var kvp in data) {
                    if (udpMappings.TryGetValue(kvp.Key, out var list)) {
                        foreach (var v in list) {
                            v.Data[tick] = kvp.Value; 
                            v.CurrentValue = kvp.Value;
                            if (kvp.Value > v.MaxValue) v.MaxValue = kvp.Value;
                            // 同步更新所有绘图对象的显示范围索引
                            foreach(var sp in v.SignalPlots) sp.MaxRenderIndex = tick;
                            updated = true;
                        }
                    }
                }
                if (updated) { tick++; packetCount++; hasNewData = true; }
            }
        }

        /// <summary>
        /// UI 辅助方法：创建美化的扁平化按钮
        /// </summary>
        private static Button CreateStyledButton(string text, Color color) {
            return new Button { 
                Text = text, Width = 100, Height = 40, BackColor = color, ForeColor = Color.White, 
                FlatStyle = FlatStyle.Flat, Font = new Font("微软雅黑", 10, FontStyle.Bold), Cursor = Cursors.Hand 
            };
        }

        private static void LoadConfig() { config = new AppConfig { Network = new NetworkConfig { LocalIP = "127.0.0.1", LocalPort = 5810 } }; }
        
        /// <summary>
        /// 将当前变量池配置持久化保存到 JSON 文件
        /// </summary>
        public static void SaveVariables()
        {
            try {
                var json = JsonSerializer.Serialize(variables, new JsonSerializerOptions { WriteIndented = true });
                File.WriteAllText(VarsPath, json);
            } catch (Exception ex) { MessageBox.Show("变量保存失败: " + ex.Message); }
        }

        /// <summary>
        /// 初始化内置的指标体系 (优先从文件加载)
        /// </summary>
        private static void InitVariables() {
            variables.Clear(); udpMappings.Clear();
            
            if (File.Exists(VarsPath)) {
                try {
                    var savedVars = JsonSerializer.Deserialize<List<ChartVariable>>(File.ReadAllText(VarsPath));
                    if (savedVars != null) {
                        variables.AddRange(savedVars);
                        UpdateUdpMappings();
                        return;
                    }
                } catch { /* 如果加载失败，回退到默认初始化 */ }
            }

            // 默认初始化逻辑 (仅在无配置文件时执行)
            var regs = new Dictionary<string, string[]>();
            regs.Add("3#柴油机仿真数据", new[] { "Temp3:主机排气温度", "Z_speed3:A排增压器转速", "Z_SpeedB:B排增压器转速", "A_EgasT:A列增压器废气温度", "B_EgasT:B列增压器废气温度", "As_Temp3:A排空冷器前空气温度", "Be_Temp3:A排空冷器后空气温度", "Be_Pa3:A排空冷器出口空气压力", "FuelRack3:油门", "Power3:柴油机功率", "R_speed3:柴油机转速" });
            regs.Add("4#柴油机仿真数据", new[] { "Temp4:主机排气温度", "Z_Speed4:A排增压器转速", "Z_SpeedB2:B排增压器转速", "A_EgasT2:A列增压器废气温度", "B_EgasT2:B列增压器废气温度", "As_Temp4:A排空冷器前空气温度", "Be_Temp4:A排空冷器后空气温度", "Be_Pa4:A排空冷器出口空气压力", "FuelRack4:油门", "Power4:柴油机功率", "R_speed4:柴油机功率" });
            regs.Add("3#柴油机试验数据", new[] { "TempT2:主机排气温度", "Z_SpeedT2:A排增压器转速", "Z_SpeedBT2:B排增压器转速", "A_EgasT4:A列增压器废气温度", "B_EgasT4:B列增压器废气温度", "As_TempT2:A排空冷器前空气温度", "Be_TempT2:A排空冷器后空气温度", "Be_PaT2:A排空冷器出口空气压力", "FuelRackT2:油门", "PowerT2:柴油机功率", "R_speedT2:柴油机功率" });
            regs.Add("4#柴油机试验数据", new[] { "TempT:主机排气温度", "Z_SpeedT:A排增压器转速", "Z_SpeedBT:B排增压器转速", "A_EgasT3:A列增压器废气温度", "B_EgasT3:B列增压器废气温度", "As_TempT:A排空冷器前空气温度", "Be_TempT2:A排空冷器后空气温度", "Be_PaT2:A排空冷器出口空气压力", "FuelRackT2:油门", "PowerT2:柴油机功率", "R_speedT2:柴油机功率" });
            
            Color[] colors = { Color.Red, Color.Cyan, Color.Lime, Color.Yellow, Color.Magenta, Color.Orange, Color.White, Color.Pink, Color.Gold, Color.LightBlue, Color.SpringGreen, Color.Aqua, Color.DeepPink, Color.Chartreuse, Color.Violet, Color.Tomato };
            int cIdx = 0;
            foreach (var r in regs) {
                foreach (var e in r.Value) {
                    variables.Add(new ChartVariable { 
                        Name = e, Tag = e.Split(':')[0], Region = r.Key, 
                        Color = colors[cIdx++ % colors.Length], DataType = "double" 
                    });
                }
            }
            UpdateUdpMappings();
            SaveVariables(); // 第一次初始化后自动保存
        }

    }
}
