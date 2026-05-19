
================================================================================
  MainWindow.xaml 内容 (请将其复制并保存为 MainWindow.xaml)
================================================================================
<Window x:Class="DotNetWinApp.MainWindow"
        xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        xmlns:scott="clr-namespace:ScottPlot;assembly=ScottPlot.WPF"
        Title="柴油机实时监控与数据校验系统" Height="900" Width="1600"
        Background="#0A0E17" WindowStartupLocation="CenterScreen">
    <Grid>
        <Grid.RowDefinitions>
            <RowDefinition Height="60"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="80"/>
        </Grid.RowDefinitions>

        <!-- 顶部标题栏 -->
        <Border Grid.Row="0" Background="#0A0E17">
            <Grid>
                <TextBlock Text=">>>> 柴油机实时监控与数据校验工具 <<<<" 
                           Foreground="#22D3EE" FontSize="24" FontWeight="Bold" 
                           HorizontalAlignment="Center" VerticalAlignment="Center"/>
                <TextBlock x:Name="lblStatus" Text="● 系统就绪" Foreground="#9CA3AF" 
                           FontWeight="Bold" HorizontalAlignment="Right" VerticalAlignment="Center" Margin="0,0,40,0"/>
            </Grid>
        </Border>

        <Grid Grid.Row="1">
            <Grid.ColumnDefinitions>
                <ColumnDefinition Width="320"/>
                <ColumnDefinition Width="*"/>
            </Grid.ColumnDefinitions>

            <!-- 左侧侧边栏 -->
            <Border Grid.Column="0" Background="#111827" BorderBrush="#374151" BorderThickness="1" Margin="10,0,5,10">
                <DockPanel>
                    <Label Content="监测指标体系" DockPanel.Dock="Top" Background="#1F2937" Foreground="#06B6D2" 
                           FontWeight="Bold" Padding="10,8" FontSize="14"/>
                    
                    <!-- 区域切换按钮 -->
                    <UniformGrid DockPanel.Dock="Top" Columns="2" Rows="2" Margin="5" Height="100">
                        <Button x:Name="btnReg1" Content="3#仿真" Click="Region_Click" Background="#1F2937" Foreground="#9CA3AF" BorderThickness="0" Margin="2" Cursor="Hand"/>
                        <Button x:Name="btnReg2" Content="4#仿真" Click="Region_Click" Background="#1F2937" Foreground="#9CA3AF" BorderThickness="0" Margin="2" Cursor="Hand"/>
                        <Button x:Name="btnReg3" Content="3#试验" Click="Region_Click" Background="#1F2937" Foreground="#9CA3AF" BorderThickness="0" Margin="2" Cursor="Hand"/>
                        <Button x:Name="btnReg4" Content="4#试验" Click="Region_Click" Background="#1F2937" Foreground="#9CA3AF" BorderThickness="0" Margin="2" Cursor="Hand"/>
                    </UniformGrid>

                    <TextBlock x:Name="lblSelectionCount" Text="已选: 0 项" DockPanel.Dock="Bottom" 
                               Foreground="#06B6D2" HorizontalAlignment="Center" Margin="10" FontSize="13"/>

                    <!-- 变量列表 -->
                    <ListBox x:Name="lstVariables" Background="Transparent" BorderThickness="0" 
                             ScrollViewer.HorizontalScrollBarVisibility="Disabled" Padding="5">
                        <ListBox.ItemTemplate>
                            <DataTemplate>
                                <Border Background="{Binding BgColor}" Margin="0,2" Padding="12,10" CornerRadius="4" 
                                        PreviewMouseDown="Item_PreviewMouseDown" Cursor="Hand" BorderBrush="#374151" BorderThickness="1">
                                    <Grid Width="260">
                                        <Grid.ColumnDefinitions>
                                            <ColumnDefinition Width="15"/>
                                            <ColumnDefinition Width="*"/>
                                            <ColumnDefinition Width="Auto"/>
                                        </Grid.ColumnDefinitions>
                                        <Ellipse Fill="{Binding ColorBrush}" Width="10" Height="10" VerticalAlignment="Center"/>
                                        <StackPanel Grid.Column="1" Margin="10,0">
                                            <TextBlock Text="{Binding Tag}" Foreground="White" FontWeight="Bold" FontSize="14"/>
                                            <TextBlock Text="{Binding ShortName}" Foreground="#9CA3AF" FontSize="11" Margin="0,2,0,0"/>
                                        </StackPanel>
                                        <CheckBox Grid.Column="2" IsChecked="{Binding IsSelected}" VerticalAlignment="Center" 
                                                  Style="{StaticResource {x:Static ToolBar.CheckBoxStyleKey}}" Visibility="Collapsed"/>
                                    </Grid>
                                </Border>
                            </DataTemplate>
                        </ListBox.ItemTemplate>
                    </ListBox>
                </DockPanel>
            </Border>

            <!-- 右侧主视口 -->
            <Grid Grid.Column="1" Margin="5,0,15,10">
                <Grid.RowDefinitions>
                    <RowDefinition Height="5*"/>
                    <RowDefinition Height="Auto"/>
                    <RowDefinition Height="3*"/>
                </Grid.RowDefinitions>

                <!-- 曲线图 -->
                <Border Grid.Row="0" Background="#111827" BorderBrush="#374151" BorderThickness="1" Margin="0,0,0,5">
                    <DockPanel>
                        <Label Content="曲线监控 · 实时波形" DockPanel.Dock="Top" Background="#1F2937" Foreground="#06B6D2" FontWeight="Bold" Padding="15,8"/>
                        <scott:WpfPlot x:Name="wpfPlot"/>
                    </DockPanel>
                </Border>

                <!-- 分割线 -->
                <GridSplitter Grid.Row="1" Height="6" HorizontalAlignment="Stretch" Background="#0A0E17"/>

                <!-- 数据表格 -->
                <Border Grid.Row="2" Background="#111827" BorderBrush="#374151" BorderThickness="1">
                    <DockPanel>
                        <Label Content="监控数据记录" DockPanel.Dock="Top" Background="#1F2937" Foreground="#06B6D2" FontWeight="Bold" Padding="15,8"/>
                        <DataGrid x:Name="dgData" Background="Transparent" Foreground="White" RowBackground="#111827" 
                                  AutoGenerateColumns="False" IsReadOnly="True" BorderThickness="0" 
                                  HeadersVisibility="Column" GridLinesVisibility="Horizontal" HorizontalGridLinesBrush="#1F2937">
                            <DataGrid.ColumnHeaderStyle>
                                <Style TargetType="DataGridColumnHeader">
                                    <Setter Property="Background" Value="#1F2937"/>
                                    <Setter Property="Foreground" Value="#06B6D2"/>
                                    <Setter Property="Padding" Value="10,5"/>
                                    <Setter Property="FontWeight" Value="Bold"/>
                                    <Setter Property="BorderThickness" Value="0,0,0,1"/>
                                    <Setter Property="BorderBrush" Value="#374151"/>
                                </Style>
                            </DataGrid.ColumnHeaderStyle>
                            <DataGrid.Columns>
                                <DataGridTextColumn Header="区域" Binding="{Binding RegionShort}" Width="100"/>
                                <DataGridTextColumn Header="标签" Binding="{Binding Tag}" Width="180"/>
                                <DataGridTextColumn Header="当前值" Binding="{Binding CurrentValueStr}" Width="*"/>
                                <DataGridTextColumn Header="峰值" Binding="{Binding MaxValueStr}" Width="*"/>
                            </DataGrid.Columns>
                        </DataGrid>
                    </DockPanel>
                </Border>
            </Grid>
        </Grid>

        <!-- 底部工具栏 -->
        <Border Grid.Row="2" Background="#0A0E17" Padding="25,10" BorderBrush="#374151" BorderThickness="0,1,0,0">
            <StackPanel Orientation="Horizontal">
                <Button x:Name="btnStart" Content="启动监控" Width="130" Height="42" Background="#10B981" Foreground="White" 
                        BorderThickness="0" FontWeight="Bold" Click="BtnStart_Click" Cursor="Hand"/>
                
                <TextBlock Text="时间跨度:" Foreground="#9CA3AF" VerticalAlignment="Center" Margin="30,0,10,0" FontSize="13"/>
                <ComboBox x:Name="comboRange" Width="110" Height="32" VerticalContentAlignment="Center" Background="#1F2937" 
                          Foreground="White" SelectionChanged="ComboRange_SelectionChanged">
                    <ComboBoxItem Content="15 秒"/>
                    <ComboBoxItem Content="1 分钟" IsSelected="True"/>
                    <ComboBoxItem Content="5 分钟"/>
                    <ComboBoxItem Content="15 分钟"/>
                    <ComboBoxItem Content="1 小时"/>
                </ComboBox>

                <CheckBox x:Name="cbAutoFollow" Content="自动跟随" Foreground="#9CA3AF" IsChecked="True" VerticalAlignment="Center" Margin="30,0,0,0"/>
                <CheckBox x:Name="cbAutoScaleY" Content="Y轴适应" Foreground="#9CA3AF" IsChecked="True" VerticalAlignment="Center" Margin="25,0,0,0"/>
                <CheckBox x:Name="cbShowCursor" Content="显示游标" Foreground="#9CA3AF" IsChecked="False" VerticalAlignment="Center" Margin="25,0,0,0"/>

                <Button Content="清空数据" Width="110" Height="42" Background="#EF4444" Foreground="White" 
                        BorderThickness="0" Margin="40,0,10,0" FontWeight="Bold" Click="BtnClear_Click" Cursor="Hand"/>
                <Button Content="复位坐标" Width="110" Height="42" Background="#374151" Foreground="White" 
                        BorderThickness="0" FontWeight="Bold" Click="BtnReset_Click" Cursor="Hand"/>
            </StackPanel>
        </Border>
    </Grid>
</Window>


================================================================================
  MainWindow.xaml.cs 内容 (请将其复制并保存为 MainWindow.xaml.cs)
================================================================================
*/

using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using System.Collections.ObjectModel;
using System.ComponentModel;
using ScottPlot;
using ScottPlot.Plottable;

namespace DotNetWinApp
{
    // 数据模型 - 针对 WPF 进行了绑定优化
    public class ChartVariable : INotifyPropertyChanged
    {
        public string Name { get; set; }
        public string Tag { get; set; }
        public string Region { get; set; }
        public System.Drawing.Color Color { get; set; } // 保持 ScottPlot 使用的 Drawing.Color
        public bool IsSelected { get; set; }
        public double[] Data { get; set; } = new double[150000];
        public SignalPlot SignalPlot { get; set; }
        public double CurrentValue { get; set; }
        public double MaxValue { get; set; } = double.MinValue;

        // WPF 绑定所需的辅助属性
        public string ShortName => Name.Contains(":") ? Name.Split(':').Last() : Name;
        public SolidColorBrush ColorBrush => new SolidColorBrush(System.Windows.Media.Color.FromRgb(Color.R, Color.G, Color.B));
        public string RegionShort => Region.Length >= 2 ? Region.Substring(0, 2) : Region;
        public string CurrentValueStr => CurrentValue.ToString("F4");
        public string MaxValueStr => MaxValue.ToString("F4");
        public SolidColorBrush BgColor => IsSelected ? new SolidColorBrush(System.Windows.Media.Color.FromRgb(30, 58, 138)) : new SolidColorBrush(System.Windows.Media.Color.FromRgb(31, 41, 55));

        public event PropertyChangedEventHandler PropertyChanged;
        public void NotifyUpdate() {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IsSelected)));
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(BgColor)));
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(CurrentValueStr)));
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(MaxValueStr)));
        }
    }

    public partial class MainWindow : Window
    {
        private readonly List<ChartVariable> variables = new();
        private readonly Dictionary<string, List<ChartVariable>> udpMappings = new(StringComparer.OrdinalIgnoreCase);
        private DispatcherTimer renderTimer;
        private UDPClient udpClient;
        private int tick = 0;
        private bool hasNewData = false;
        private readonly object dataLock = new();
        private int currentRangePoints = 1800;
        private VLine vCursorLine;
        private Annotation vCursorLabel;
        private int packetCount = 0;

        public MainWindow()
        {
            InitializeComponent();
            InitVariables();
            ConfigurePlotStyle();
            
            // WPF 渲染定时器 (33ms ~ 30fps)
            renderTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(33) };
            renderTimer.Tick += RenderTimer_Tick;

            wpfPlot.MouseMove += WpfPlot_MouseMove;
            
            // 默认显示第一个区域
            btnReg1.Background = new SolidColorBrush(System.Windows.Media.Color.FromRgb(15, 118, 110));
            btnReg1.Foreground = Brushes.White;
            UpdateVariableList("3#柴油机仿真数据");

            // 彻底结束进程
            this.Closed += (s, e) => {
                renderTimer.Stop();
                System.Diagnostics.Process.GetCurrentProcess().Kill();
            };
        }

        private void ConfigurePlotStyle()
        {
            wpfPlot.Plot.Style(ScottPlot.Style.Black);
            wpfPlot.Plot.XAxis.Label("时间 (Time/s)", color: System.Drawing.Color.FromArgb(156, 163, 175));
            wpfPlot.Plot.YAxis.Label("幅值 (Amplitude)", color: System.Drawing.Color.FromArgb(156, 163, 175));
            wpfPlot.Plot.Grid(true, System.Drawing.Color.FromArgb(40, 255, 255, 255));
            
            var legend = wpfPlot.Plot.Legend(true, Alignment.UpperRight);
            legend.FillColor = System.Drawing.Color.FromArgb(180, 10, 20, 40);
            legend.OutlineColor = System.Drawing.Color.FromArgb(6, 182, 212);
            legend.FontColor = System.Drawing.Color.White;

            // 初始化游标
            vCursorLine = wpfPlot.Plot.AddVerticalLine(0, color: System.Drawing.Color.FromArgb(245, 158, 11), style: LineStyle.Dash);
            vCursorLine.IsVisible = false;
            vCursorLabel = wpfPlot.Plot.AddAnnotation("", 10, 10);
            vCursorLabel.IsVisible = false;
            vCursorLabel.BackgroundColor = System.Drawing.Color.FromArgb(200, 0, 0, 0);
            vCursorLabel.Font.Color = System.Drawing.Color.White;
        }

        private void Region_Click(object sender, RoutedEventArgs e)
        {
            var btn = sender as Button;
            string region = btn.Content.ToString();
            
            // 重置所有按钮样式
            foreach (var child in ((UniformGrid)btn.Parent).Children) {
                if (child is Button b) {
                    b.Background = new SolidColorBrush(System.Windows.Media.Color.FromRgb(31, 41, 55));
                    b.Foreground = new SolidColorBrush(System.Windows.Media.Color.FromRgb(156, 163, 175));
                }
            }
            btn.Background = new SolidColorBrush(System.Windows.Media.Color.FromRgb(15, 118, 110));
            btn.Foreground = Brushes.White;

            // 映射到完整区域名
            string fullName = region switch {
                "3#仿真" => "3#柴油机仿真数据",
                "4#仿真" => "4#柴油机仿真数据",
                "3#试验" => "3#柴油机试验数据",
                "4#试验" => "4#柴油机试验数据",
                _ => region
            };
            UpdateVariableList(fullName);
        }

        private void UpdateVariableList(string region)
        {
            lstVariables.ItemsSource = variables.Where(v => v.Region == region).ToList();
        }

        private void Item_PreviewMouseDown(object sender, System.Windows.Input.MouseButtonEventArgs e)
        {
            var border = sender as Border;
            var v = border.DataContext as ChartVariable;
            if (v == null) return;

            v.IsSelected = !v.IsSelected;
            
            if (v.IsSelected) {
                v.SignalPlot = wpfPlot.Plot.AddSignal(v.Data, 30, v.Color, v.Tag);
            } else {
                if (v.SignalPlot != null) { wpfPlot.Plot.Remove(v.SignalPlot); v.SignalPlot = null; }
            }

            v.NotifyUpdate();
            dgData.ItemsSource = variables.Where(x => x.IsSelected).ToList();
            lblSelectionCount.Text = $"已选: {variables.Count(x => x.IsSelected)} 项";
            wpfPlot.Refresh();
        }

        private void RenderTimer_Tick(object sender, EventArgs e)
        {
            if (hasNewData) {
                lock (dataLock) {
                    hasNewData = false;
                    if (cbAutoFollow.IsChecked == true) {
                        double xMax = tick / 30.0;
                        wpfPlot.Plot.SetAxisLimitsX(Math.Max(0, xMax - (currentRangePoints / 30.0)), xMax);
                    }
                    if (cbAutoScaleY.IsChecked == true && packetCount % 30 == 0) AutoScaleY();
                    
                    // 更新表格显示
                    foreach (var v in variables.Where(x => x.IsSelected)) v.NotifyUpdate();
                    dgData.Items.Refresh();
                    wpfPlot.Render();
                }
            }
        }

        private void BtnStart_Click(object sender, RoutedEventArgs e)
        {
            if (btnStart.Content.ToString() == "启动监控") {
                try {
                    udpClient = new UDPClient();
                    // 这里假设 config 已经加载，或者直接使用默认值
                    udpClient.UdpClientInite("127.0.0.1", 5810);
                    udpClient.SendData += (t, d) => UpdateExternalData(d);
                    renderTimer.Start();
                    btnStart.Content = "停止监控";
                    btnStart.Background = new SolidColorBrush(System.Windows.Media.Color.FromRgb(239, 68, 68));
                    lblStatus.Text = "● 监控中";
                    lblStatus.Foreground = new SolidColorBrush(System.Windows.Media.Color.FromRgb(16, 185, 129));
                } catch (Exception ex) { MessageBox.Show("UDP 启动失败: " + ex.Message); }
            } else {
                renderTimer.Stop();
                btnStart.Content = "启动监控";
                btnStart.Background = new SolidColorBrush(System.Windows.Media.Color.FromRgb(16, 185, 129));
                lblStatus.Text = "● 已停止";
                lblStatus.Foreground = new SolidColorBrush(System.Windows.Media.Color.FromRgb(239, 68, 68));
            }
        }

        private void UpdateExternalData(Dictionary<string, double> data)
        {
            lock (dataLock) {
                bool updated = false;
                foreach (var kvp in data) {
                    if (udpMappings.TryGetValue(kvp.Key, out var list)) {
                        foreach (var v in list) {
                            v.Data[tick] = kvp.Value;
                            v.CurrentValue = kvp.Value;
                            if (kvp.Value > v.MaxValue) v.MaxValue = kvp.Value;
                            if (v.SignalPlot != null) v.SignalPlot.MaxRenderIndex = tick;
                            updated = true;
                        }
                    }
                }
                if (updated) { tick++; packetCount++; hasNewData = true; }
            }
        }

        private void ComboRange_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            int[] pts = { 450, 1800, 9000, 27000, 108000 };
            if (comboRange != null && comboRange.SelectedIndex >= 0) {
                currentRangePoints = pts[comboRange.SelectedIndex];
                if (cbAutoFollow != null && cbAutoFollow.IsChecked == true) {
                    double xMax = tick / 30.0;
                    wpfPlot?.Plot.SetAxisLimitsX(Math.Max(0, xMax - (currentRangePoints / 30.0)), xMax);
                }
                wpfPlot?.Refresh();
            }
        }

        private void BtnClear_Click(object sender, RoutedEventArgs e)
        {
            lock (dataLock) {
                tick = 0; packetCount = 0;
                foreach (var v in variables) {
                    Array.Clear(v.Data, 0, v.Data.Length);
                    v.MaxValue = double.MinValue;
                    if (v.SignalPlot != null) v.SignalPlot.MaxRenderIndex = 0;
                }
                wpfPlot.Plot.AxisAuto();
                wpfPlot.Refresh();
            }
        }

        private void BtnReset_Click(object sender, RoutedEventArgs e)
        {
            cbAutoFollow.IsChecked = false;
            cbAutoScaleY.IsChecked = false;
            wpfPlot.Plot.AxisAuto();
            wpfPlot.Refresh();
        }

        private void WpfPlot_MouseMove(object sender, System.Windows.Input.MouseEventArgs e)
        {
            if (cbShowCursor.IsChecked != true) return;
            (double x, double y) = wpfPlot.GetMouseCoordinates();
            vCursorLine.X = x; vCursorLine.IsVisible = true;
            int idx = (int)(x * 30);
            if (idx >= 0 && idx < tick) {
                var sels = variables.Where(v => v.IsSelected).ToList();
                if (sels.Any()) {
                    vCursorLabel.Label = $"T:{x:F2}s\n" + string.Join("\n", sels.Select(v => $"{v.Tag}:{v.Data[idx]:F2}"));
                    vCursorLabel.IsVisible = true;
                }
            } else { vCursorLabel.IsVisible = false; vCursorLine.IsVisible = false; }
            wpfPlot.Refresh();
        }

        private void AutoScaleY()
        {
            var selected = variables.Where(v => v.IsSelected).ToList();
            if (!selected.Any()) return;
            double min = double.MaxValue, max = double.MinValue;
            int start = Math.Max(0, tick - currentRangePoints);
            for (int i = start; i < tick; i++) {
                foreach (var v in selected) {
                    if (v.Data[i] < min) min = v.Data[i];
                    if (v.Data[i] > max) max = v.Data[i];
                }
            }
            if (max >= min) {
                double r = (max - min == 0) ? 1 : (max - min);
                wpfPlot.Plot.SetAxisLimitsY(min - r * 0.1, max + r * 0.1);
            }
        }

        private void InitVariables()
        {
            variables.Clear(); udpMappings.Clear();
            var regs = new Dictionary<string, string[]>();
            regs.Add("3#柴油机仿真数据", new[] { "Temp3:主机排气温度", "Z_speed3:A排增压器转速", "Z_SpeedB:B排增压器转速", "A_EgasT:A列增压器废气温度", "B_EgasT:B列增压器废气温度", "As_Temp3:A排空冷器前空气温度", "Be_Temp3:A排空冷器后空气温度", "Be_Pa3:A排空冷器出口空气压力", "FuelRack3:油门", "Power3:柴油机功率", "R_speed3:柴油机转速" });
            regs.Add("4#柴油机仿真数据", new[] { "Temp4:主机排气温度", "Z_Speed4:A排增压器转速", "Z_SpeedB2:B排增压器转速", "A_EgasT2:A列增压器废气温度", "FuelRack4:油门", "Power4:柴油机功率", "R_speed4:柴油机转速" });
            regs.Add("3#柴油机试验数据", new[] { "TempT2:主机排气温度", "Z_SpeedT2:A排增压器转速", "Z_SpeedBT2:B排增压器转速" });
            regs.Add("4#柴油机试验数据", new[] { "TempT:主机排气温度", "Z_SpeedT:A排增压器转速" });

            System.Drawing.Color[] colors = { System.Drawing.Color.Red, System.Drawing.Color.Cyan, System.Drawing.Color.Lime, System.Drawing.Color.Yellow, System.Drawing.Color.Magenta, System.Drawing.Color.Orange, System.Drawing.Color.White, System.Drawing.Color.Pink, System.Drawing.Color.Gold };
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
