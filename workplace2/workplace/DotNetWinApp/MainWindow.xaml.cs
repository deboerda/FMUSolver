using Interface_WindowTouchAtPEPlay;
using ScottPlot;
using ScottPlot.Plottable;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Navigation;
using System.Windows.Shapes;
using System.Windows.Threading;

namespace SystemPlots
{
    /// <summary>
    /// MainWindow.xaml 的交互逻辑
    /// </summary>
    public partial class MainWindow : Window
    {
        //所有图表
        List<WpfPlot> wpfPlots = new List<WpfPlot>();

        List<double[]> datas = new List<double[]>();
        List<SignalPlot> signalPlots = new List<SignalPlot>();

        public double[] data1 = new double[1000_000];
        public double[] data2 = new double[1000_000];
        public double[] data3 = new double[1000_000];
        public double[] data4 = new double[1000_000];
        public double[] data5 = new double[1000_000];

        public MainWindow()
        {
            InitializeComponent();
            for (int i = 0; i < 100; i++)
            {
                datas.Add(new double[1000_000]);
            }
        }



        private void Window_Loaded(object sender, RoutedEventArgs e)
        {
            var setWindowParams = new SetWindowParams(this, "PE_CF123");
            //signalPlot_1 = this.plot_1.Plot.AddSignal(data1, 10);

            //signalPlot_2 = this.plot_2.Plot.AddSignal(data2, 10);

            //signalPlot_3 = this.plot_3.Plot.AddSignal(data3, 10);
            //signalPlot_4 = this.plot_4.Plot.AddSignal(data4, 10);

            for (int i = 0; i < 10; i++)
            {
                signalPlots.Add(this.plot_1.Plot.AddSignal(datas[i], 10));
            }

            for (int i = 10; i < 20; i++)
            {
                signalPlots.Add(this.plot_2.Plot.AddSignal(datas[i], 10));
            }

            for (int i = 20; i < 30; i++)
            {
                signalPlots.Add(this.plot_3.Plot.AddSignal(datas[i], 10));
            }

            for (int i = 30; i < 40; i++)
            {
                signalPlots.Add(this.plot_4.Plot.AddSignal(datas[i], 10));
            }

            for (int i = 40; i < 50; i++)
            {
                signalPlots.Add(this.plot_5.Plot.AddSignal(datas[i], 10));
            }

            wpfPlots.Add(this.plot_1);
            wpfPlots.Add(this.plot_2);
            wpfPlots.Add(this.plot_3);
            wpfPlots.Add(this.plot_4);
            wpfPlots.Add(this.plot_5);
            System.Drawing.Color Axis_color = System.Drawing.Color.FromArgb(125, System.Drawing.Color.White);
            System.Drawing.Color Grid_color = System.Drawing.Color.FromArgb(50, System.Drawing.Color.Gray);
            foreach (var plot in wpfPlots)
            {
                // 设置透明背景
                plot.Plot.Style(figureBackground: System.Drawing.Color.Transparent, dataBackground: System.Drawing.Color.Transparent);
                
                // 配置坐标颜色
                //WpfPlot1.Plot.Style( dataBorderThickness: 2);
                plot.Plot.YAxis.Color(color: Axis_color);
                plot.Plot.XAxis.Color(color: Axis_color);
                plot.Plot.XAxis.TickLabelStyle(fontSize: 14,color: System.Drawing.Color.White);
                plot.Plot.YAxis.TickLabelStyle(fontSize: 14, color: System.Drawing.Color.White);

             
                plot.Plot.YAxis2.Line(false);
                plot.Plot.XAxis2.Line(false);

                // 设置网格线样式和显示
                plot.Plot.Grid(color: Grid_color, lineStyle: LineStyle.DashDot);
                plot.Plot.XAxis.Grid(false);
                plot.Refresh();

            }

            // create a timer to update the GUI
            var _renderTimer =  new System.Timers.Timer();
            _renderTimer.Interval = 50;
            _renderTimer.Enabled = true;
            _renderTimer.Elapsed += Render;
         
            _renderTimer.Start();
            Closed += (s, args) =>
            {
                _renderTimer?.Stop();
            };

            var _renderTimer2 = new DispatcherTimer();
            _renderTimer2.Interval = TimeSpan.FromMilliseconds(200);
            _renderTimer2.Tick += Render2;
            _renderTimer2.Start();
            Closed += (s, args) =>
            {
                _renderTimer2?.Stop();
            };
        }
        int tick = 0;
        private void Render(object sender, EventArgs e)
        {
            for (int i = 0; i < 100; i++)
            {
                datas[i][tick] = Math.Sin(tick);
                //datas[i][tick] = Math.Sin(tick) + i * 2;
                //signalPlots[i].MaxRenderIndex = tick;
            }

          

            tick++;
        }

      
        //所有图表刷新
        private void Render2(object sender, EventArgs e)
        {
            foreach (var signalPlot in signalPlots)
            {
                signalPlot.MaxRenderIndex = tick-1;
            }
            foreach (var plot in wpfPlots)
            {
                plot.Plot.AxisAuto();
                plot.Refresh();
            }

            //data1[tick] = Math.Cos(tick * 10);
            //signalPlot_1.MaxRenderIndex = tick;
            //data2[tick] = Math.Sin(tick * 7);
            //signalPlot_2.MaxRenderIndex = tick;
            //data3[tick] = Math.Log10(tick);
            //signalPlot_3.MaxRenderIndex = tick;
            //data4[tick] = tick * 3 + 10;
            //signalPlot_4.MaxRenderIndex = tick;

            
        }

        private void CheckBox_Checked(object sender, RoutedEventArgs e)
        {
            var ck = sender as CheckBox;
            var allPlottables = this.plot_1.Plot.GetPlottables();
            if (ck != null && ck.IsChecked == true)
            {
                
                foreach (var plottable in allPlottables)
                {
                    plottable.IsVisible = true;
                }
                this.plot_1.Visibility = Visibility.Visible;
            }
            else
            {
                
                
                foreach (var plottable in allPlottables)
                {
                    plottable.IsVisible = false;    
                }

                this.plot_1.Visibility = Visibility.Collapsed;

            }
        }

        private void CheckBox_Checked_1(object sender, RoutedEventArgs e)
        {
            var ck = sender as CheckBox;
            var allPlottables = this.plot_2.Plot.GetPlottables();
            if (ck != null && ck.IsChecked == true)
            {
                
                foreach (var plottable in allPlottables)
                {
                    plottable.IsVisible = true;
                }
                this.plot_2.Visibility = Visibility.Visible;
            }
            else
            {
                foreach (var plottable in allPlottables)
                {
                    plottable.IsVisible = false;
                }

                this.plot_2.Visibility = Visibility.Collapsed;

            }
        }

        private void CheckBox_Checked_2(object sender, RoutedEventArgs e)
        {
            var ck = sender as CheckBox;
            var allPlottables = this.plot_3.Plot.GetPlottables();
            if (ck != null && ck.IsChecked == true)
            {
               
                foreach (var plottable in allPlottables)
                {
                    plottable.IsVisible = true;
                }
                this.plot_3.Visibility = Visibility.Visible;
            }
            else
            {
             

                foreach (var plottable in allPlottables)
                {
                    plottable.IsVisible = false;
                }

                this.plot_3.Visibility = Visibility.Collapsed;
            }
        }

        private void CheckBox_Checked_3(object sender, RoutedEventArgs e)
        {
            var ck = sender as CheckBox;
            var allPlottables = this.plot_4.Plot.GetPlottables();
            if (ck != null && ck.IsChecked == true)
            {
                
                foreach (var plottable in allPlottables)
                {
                    plottable.IsVisible = true;
                }

                this.plot_4.Visibility = Visibility.Visible;
            }
            else
            {
                foreach (var plottable in allPlottables)
                {
                    plottable.IsVisible = false;
                }
                this.plot_4.Visibility = Visibility.Collapsed;
            }
        }
    }
}
