using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Data;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Threading;

namespace 测试send
{
    // 新增Windows API导入（补充层级控制）
    public static class User32
    {
        [StructLayout(LayoutKind.Sequential)]
        public struct RECT
        {
            public int Left;
            public int Top;
            public int Right;
            public int Bottom;

            public int Width => Right - Left;
            public int Height => Bottom - Top;
        }

        [DllImport("user32.dll", SetLastError = true)]
        public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

        [DllImport("user32.dll")]
        public static extern bool IsWindowVisible(IntPtr hWnd);

        [DllImport("user32.dll")]
        public static extern IntPtr SetParent(IntPtr hWndChild, IntPtr hWndNewParent);

        [DllImport("user32.dll")]
        public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

        [DllImport("user32.dll")]
        public static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll")]
        public static extern bool SetForegroundWindow(IntPtr hWnd);

        // 窗口层级常量
        public static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
        public static readonly IntPtr HWND_NOTOPMOST = new IntPtr(-2);
        public static readonly IntPtr HWND_TOP = new IntPtr(0);
        public static readonly IntPtr HWND_BOTTOM = new IntPtr(1);

        // SetWindowPos参数
        public const uint SWP_NOSIZE = 0x0001;
        public const uint SWP_NOMOVE = 0x0002;
        public const uint SWP_NOZORDER = 0x0004;
        public const uint SWP_NOACTIVATE = 0x0010;
        public const uint SWP_FRAMECHANGED = 0x0020;
        public const uint SWP_SHOWWINDOW = 0x0040;
        public const uint SWP_HIDEWINDOW = 0x0080;
        public const uint SWP_NOOWNERZORDER = 0x0200;
        public const uint SWP_NOREPOSITION = 0x0200;
    }

    #region 变量配置中心（核心）
    public static class VariableConfig
    {
        // ==================== 变量定义配置 ====================
        // 在这里定义或修改所有变量名称，一处修改，全局生效

        // 原始变量名（内部使用，代码中引用这些名称发动机参数温度监控参数 (11个) ====================
        public const string ExhaustTemp = "ExhaustTemp";            //主机排气温度
        public const string TurboASpeed = "TurboASpeed";            //A排增压器转速
        public const string TurboBSpeed = "TurboBSpeed";            //B排增压器转速
        public const string TurboAGasTemp = "TurboAGasTemp";        //A列增压器废气温度 ℃
        public const string TurboBGasTemp = "TurboBGasTemp";        //B列增压器废气温度 ℃
        public const string AirTempBefore = "AirTempBefore";        //A排空冷器前空气温度 ℃
        public const string AirTempAfter = "AirTempAfter";          //A排空冷器后空气温度 ℃
        public const string AirPressure = "AirPressure";            //A排空冷器出口空气压力
        public const string YM = "YM";                              //油门
        public const string PowerValue = "PowerValue";              //柴油机功率
        public const string EngineSpeed = "EngineSpeed";            //柴油机转速

        public const string Test1_1 = "Test1_1";
        public const string Test1_2 = "Test1_2";
        public const string Test1_3 = "Test1_3";
        public const string Test1_4 = "Test1_4";
        public const string Test1_5 = "Test1_5";
        // ==================== 区域2：发动机参数 (11个) ====================
        public const string OilPressure = "OilPressure";             // 主机排气温度 
        public const string CoolantInTemp = "CoolantInTemp";         // A排增压器转速
        public const string FuelInTemp = "FuelInTemp";               // B排增压器转速  
        public const string OilOutTemp = "OilOutTemp";               // A列增压器废气温度
        public const string CoolantOutTemp = "CoolantOutTemp";       // B列增压器废气温度
        public const string FuelOutTemp = "FuelOutTemp";             // A排空冷器前空气温度
        public const string AmbientTemp = "AmbientTemp";             // A排空冷器后空气温度
        public const string IntakeAirTemp = "IntakeAirTemp";         // A排空冷器出口空气压力
        public const string ExhaustManifoldTemp = "ExhaustManifoldTemp"; // 油门
        public const string CylinderHeadTemp = "CylinderHeadTemp";   // 柴油机功率
        public const string OilPanTemp = "OilPanTemp";               // 柴油机转速

        public const string Test2_1 = "Test2_1";
        public const string Test2_2 = "Test2_2";
        public const string Test2_3 = "Test2_3";
        public const string Test2_4 = "Test2_4";
        public const string Test2_5 = "Test2_5";


        // ==================== 区域3：发动机参数 (11个) ====================
        public const string OilInTemp = "OilInTemp";                 // 主机排气温度
        public const string ExhaustBackPressure = "ExhaustBackPressure"; // A排增压器转速
        public const string CoolantPressure = "CoolantPressure";     // B排增压器转速
        public const string TurboAInPressure = "TurboAInPressure";   // A列增压器废气温度
        public const string TurboAOutPressure = "TurboAOutPressure"; // B列增压器废气温度
        public const string TurboBInPressure = "TurboBInPressure";   // A排空冷器前空气温度
        public const string TurboBOutPressure = "TurboBOutPressure"; // A排空冷器后空气温度
        public const string CrankcasePressure = "CrankcasePressure"; // A排空冷器出口空气压力
        public const string CompressionPressure = "CompressionPressure"; // 油门
        public const string FuelPressure = "FuelPressure";           // 柴油机功率
        public const string IntakePressure = "IntakePressure";       // 柴油机功率


        public const string Test3_1 = "Test3_1";
        public const string Test3_2 = "Test3_2";
        public const string Test3_3 = "Test3_3";
        public const string Test3_4 = "Test3_4";
        public const string Test3_5 = "Test3_5";

        // ==================== 区域4：发动机参数 (11个) ====================
        public const string Voltage = "Voltage";                     // 主机排气温度
        public const string Current = "Current";                     // A排增压器转速
        public const string Frequency = "Frequency";                 // B排增压器转速
        public const string BatteryVoltage = "BatteryVoltage";       // A列增压器废气温度
        public const string GeneratorPower = "GeneratorPower";       // B列增压器废气温度
        public const string PowerFactor = "PowerFactor";             // A排空冷器前空气温度
        public const string FuelLevel = "FuelLevel";                 // A排空冷器后空气温度
        public const string OilLevel = "OilLevel";                   // A排空冷器出口空气压力
        public const string CoolantLevel = "CoolantLevel";           // 油门
        public const string RunningHours = "RunningHours";           // 柴油机功率
        public const string EngineLoad = "EngineLoad";               // 柴油机功率

        public const string Test4_1 = "Test4_1";
        public const string Test4_2 = "Test4_2";
        public const string Test4_3 = "Test4_3";
        public const string Test4_4 = "Test4_4";
        public const string Test4_5 = "Test4_5";


        // ==================== 显示名称配置 ====================
        // 修改这里来更改界面显示的名称
        private static readonly Dictionary<string, string> _displayNames = new Dictionary<string, string>
        {
            // 区域1发动机
            { ExhaustTemp, "主机排气温度" },
            { TurboASpeed, "A排增压器转速" },
            { TurboBSpeed, "B排增压器转速" },
            { TurboAGasTemp, "A列增压器废气温度" },
            { TurboBGasTemp, "B列增压器废气温度" },
            { AirTempBefore, "A排空冷器前空气温度" },
            { AirTempAfter, "A排空冷器后空气温度" },
            { AirPressure, "A排空冷器出口空气压力" },
            { YM, "油门" },
            { PowerValue, "柴油机功率" },
            { EngineSpeed, "柴油机转速" },
            { Test1_1, "测试变量" },
            { Test1_2, "测试变量" },
            { Test1_3, "测试变量" },
            { Test1_4, "测试变量" },
            { Test1_5, "测试变量" },


            // 区域2发动机
            { OilPressure, "主机排气温度" },
            { CoolantInTemp, "A排增压器转速" },
            { FuelInTemp, "B排增压器转速" },
            { OilOutTemp, "A列增压器废气温度" },
            { CoolantOutTemp, "B列增压器废气温度" },
            { FuelOutTemp, "A排空冷器前空气温度" },
            { AmbientTemp, "A排空冷器后空气温度" },
            { IntakeAirTemp, "A排空冷器出口空气压力" },
            { ExhaustManifoldTemp, "油门" },
            { CylinderHeadTemp, "柴油机功率" },
            { OilPanTemp, "柴油机转速" },

            { Test2_1, "测试变量" },
            { Test2_2, "测试变量" },
            { Test2_3, "测试变量" },
            { Test2_4, "测试变量" },
            { Test2_5, "测试变量" },



        
            // 区域3发动机参数
            { OilInTemp, "主机排气温度" },
            { ExhaustBackPressure, "A排增压器转速" },
            { CoolantPressure, "B排增压器转速" },
            { TurboAInPressure, "A列增压器废气温度" },
            { TurboAOutPressure, "B列增压器废气温度" },
            { TurboBInPressure, "A排空冷器前空气温度" },
            { TurboBOutPressure, "A排空冷器后空气温度" },
            { CrankcasePressure, "A排空冷器出口空气压力" },
            { CompressionPressure, "油门" },
            { FuelPressure, "柴油机功率" },
            { IntakePressure, "柴油机功率" },

            { Test3_1, "测试变量" },
            { Test3_2, "测试变量" },
            { Test3_3, "测试变量" },
            { Test3_4, "测试变量" },
            { Test3_5, "测试变量" },


            // 区域4发动机参数
            { Voltage, "主机排气温度" },
            { Current, "A排增压器转速" },
            { Frequency, "B排增压器转速" },
            { BatteryVoltage, "A列增压器废气温度" },
            { GeneratorPower, "B列增压器废气温度" },
            { PowerFactor, "A排空冷器前空气温度" },
            { FuelLevel, "A排空冷器后空气温度" },
            { OilLevel, "A排空冷器出口空气压力" },
            { CoolantLevel, "油门" },
            { RunningHours, "柴油机功率" },
            { EngineLoad, "柴油机功率" },

            { Test4_1, "测试变量" },
            { Test4_2, "测试变量" },
            { Test4_3, "测试变量" },
            { Test4_4, "测试变量" },
            { Test4_5, "测试变量" },


        };

        // ==================== UDP映射配置 ====================
        // 修改这里来更改UDP接收的键名
        private static readonly Dictionary<string, List<string>> _udpMappings = new Dictionary<string, List<string>>(StringComparer.Ordinal)
        {
            // 区域1 - 发动机参数
            { ExhaustTemp, new List<string> { "Temp3", "主机排气温度" } },
            { TurboASpeed, new List<string> { "Z_speed3", "A排增压器转速" } },
            { TurboBSpeed, new List<string> { "Z_SpeedB", "B排增压器转速" } },
            { TurboAGasTemp, new List<string> { "A_EgasT", "A列增压器废气温度" } },
            { TurboBGasTemp, new List<string> { "B_EgasT", "B列增压器废气温度"} },
            { AirTempBefore, new List<string> { "As_Temp3", "A排空冷器前空气温度" } },
            { AirTempAfter, new List<string> { "Be_Temp3", "A排空冷器后空气温度" } },
            { AirPressure, new List<string> { "Be_Pa3", "A排空冷器出口空气压力" } },
            { YM, new List<string> { "FuelRack3", "油门"} },
            { PowerValue, new List<string> { "Power3", "柴油机功率" } },
            { EngineSpeed, new List<string> { "R_speed3", "柴油机转速"} },
         //   { Test1_1, new List<string> { "Temp3", "测试变量"} },
          //  { Test1_2, new List<string> { "Z_speed3", "测试变量"} },
          //  { Test1_3, new List<string> { "E_High", "测试变量"} },
          //  { Test1_4, new List<string> { "f_consumption3", "测试变量"} },
          //  { Test1_5, new List<string> { "m_air", "测试变量"} },





            // 区域2 - 发动机2参数映射
            { OilPressure, new List<string> { "Temp4", "主机排气温度" } },
            { CoolantInTemp, new List<string> { "Z_Speed4", "A排增压器转速" } },
            { FuelInTemp, new List<string> { "Z_SpeedB2", "B排增压器转速" } },
            { OilOutTemp, new List<string> { "A_EgasT2", "A列增压器废气温度" } },
            { CoolantOutTemp, new List<string> { "B_EgasT2", "B列增压器废气温度" } },
            { FuelOutTemp, new List<string> { "As_Temp4", "A排空冷器前空气温度" } },
            { AmbientTemp, new List<string> { "Be_Temp4", "A排空冷器后空气温度" } },
            { IntakeAirTemp, new List<string> { "Be_Pa4", "A排空冷器出口空气压力" } },
            { ExhaustManifoldTemp, new List<string> { "FuelRack4", "油门" } },
            { CylinderHeadTemp, new List<string> { "Power4", "柴油机功率" } },
            { OilPanTemp, new List<string> { "R_speed4", "柴油机功率" } },

          //  { Test2_1, new List<string> { "aa", "测试变量"} },
           // { Test2_2, new List<string> { "bb", "测试变量"} },
           // { Test2_3, new List<string> { "E_High2", "测试变量"} },
           // { Test2_4, new List<string> { "dd", "测试变量"} },
           // { Test2_5, new List<string> { "ee", "测试变量"} },

             // 区域3 - 发动机3参数映射
            { OilInTemp, new List<string> { "TempT2", "主机排气温度" } },
            { ExhaustBackPressure, new List<string> { "Z_SpeedT2", "A排增压器转速" } },
            { CoolantPressure, new List<string> { "Z_SpeedBT2", "B排增压器转速" } },
            { TurboAInPressure, new List<string> { "A_EgasT4", "A列增压器废气温度" } },
            { TurboAOutPressure, new List<string> { "B_EgasT4", "B列增压器废气温度" } },
            { TurboBInPressure, new List<string> { "As_TempT2", "A排空冷器前空气温度" } },
            { TurboBOutPressure, new List<string> { "Be_TempT2", "A排空冷器后空气温度" } },
            { CrankcasePressure, new List<string> { "Be_PaT2", "A排空冷器出口空气压力" } },
            { CompressionPressure, new List<string> { "FuelRackT2", "油门" } },
            { FuelPressure, new List<string> { "PowerT2", "柴油机功率" } },
            { IntakePressure, new List<string> { "R_speedT2", "柴油机功率" } },

           // { Test3_1, new List<string> { "aaa", "测试变量"} },
           // { Test3_2, new List<string> { "bbb", "测试变量"} },
           // { Test3_3, new List<string> { "E_HighT2", "测试变量"} },
           // { Test3_4, new List<string> { "ddd", "测试变量"} },
           // { Test3_5, new List<string> { "eee", "测试变量"} },


             // 区域4 - 发动机4参数映射
            { Voltage, new List<string> { "TempT", "主机排气温度" } },
            { Current, new List<string> { "Z_SpeedT", "A排增压器转速" } },
            { Frequency, new List<string> { "Z_SpeedBT", "B排增压器转速" } },
            { BatteryVoltage, new List<string> { "A_EgasT3", "A列增压器废气温度" } },
            { GeneratorPower, new List<string> { "B_EgasT3", "B列增压器废气温度" } },
            { PowerFactor, new List<string> { "As_TempT", "A排空冷器前空气温度" } },
            { FuelLevel, new List<string> { "Be_TempT2", "A排空冷器后空气温度" } },
            { OilLevel, new List<string> { "Be_PaT2", "A排空冷器出口空气压力" } },
            { CoolantLevel, new List<string> { "FuelRackT2", "油门" } },
            { RunningHours, new List<string> { "PowerT2", "柴油机功率" } },
            { EngineLoad, new List<string> { "R_speedT2", "柴油机功率" } },

           //{ Test4_1, new List<string> { "aaaa", "测试变量"} },
            //{ Test4_2, new List<string> { "bbbb", "测试变量"} },
            //{ Test4_3, new List<string> { "E_HighT", "测试变量"} },
           // { Test4_4, new List<string> { "dddd", "测试变量"} },
           // { Test4_5, new List<string> { "eeee", "测试变量"} },











        };

        // ==================== 参数配置 ====================
        // 修改这里来更改各变量的最大值、单位等
        private static readonly Dictionary<string, VariableParam> _variableParams = new Dictionary<string, VariableParam>
        {
              // 区域1 - 发动机参数
            { ExhaustTemp, new VariableParam(800, "°C", true) },      // 最大值, 单位, 是否指针类型
            { TurboASpeed, new VariableParam(28000, "rpm", true) },
            { TurboBSpeed, new VariableParam(28000, "rpm", true) },
            { TurboAGasTemp, new VariableParam(800, "°C", false) },
            { TurboBGasTemp, new VariableParam(800, "°C", false) },
            { AirTempBefore, new VariableParam(300, "°C", false) },
            { AirTempAfter, new VariableParam(100, "°C", false) },
            { AirPressure, new VariableParam(0.6, "kPa", false) },
            { YM, new VariableParam(100, "%", false) },               // 环形图类型在ViewModel中特殊处理
            { PowerValue, new VariableParam(100, "Kw", false) },
            { EngineSpeed, new VariableParam(100, "rpm", false) },
            { Test1_1, new VariableParam(500, "", false) },
            { Test1_2, new VariableParam(500, "", false) },
            { Test1_3, new VariableParam(5000000, "", false) },
            { Test1_4, new VariableParam(500, "", false) },
            { Test1_5, new VariableParam(500, "", false) },
            // 区域2 - 发动机参数
            { OilPressure, new VariableParam(800, "MPa", false) },
            { CoolantInTemp, new VariableParam(28000, "°C", false) },
            { FuelInTemp, new VariableParam(28000, "°C", false) },
            { OilOutTemp, new VariableParam(200, "°C", false) },
            { CoolantOutTemp, new VariableParam(200, "°C", false) },
            { FuelOutTemp, new VariableParam(200, "°C", false) },
            { AmbientTemp, new VariableParam(200, "°C", false) },
            { IntakeAirTemp, new VariableParam(200, "°C", false) },
            { ExhaustManifoldTemp, new VariableParam(100, "°C", false) },
            { CylinderHeadTemp, new VariableParam(100, "°C", false) },
            { OilPanTemp, new VariableParam(100, "°C", false) },

            { Test2_1, new VariableParam(500, "", false) },
            { Test2_2, new VariableParam(500, "", false) },
            { Test2_3, new VariableParam(5000000, "", false) },
            { Test2_4, new VariableParam(500, "", false) },
            { Test2_5, new VariableParam(500, "", false) },

             // 区域3 - 发动机参数
            { OilInTemp, new VariableParam(800, "°C", false) },
            { ExhaustBackPressure, new VariableParam(28000, "kPa", false) },
            { CoolantPressure, new VariableParam(28000, "MPa", false) },
            { TurboAInPressure, new VariableParam(200, "kPa", false) },
            { TurboAOutPressure, new VariableParam(200, "kPa", false) },
            { TurboBInPressure, new VariableParam(200, "kPa", false) },
            { TurboBOutPressure, new VariableParam(200, "kPa", false) },
            { CrankcasePressure, new VariableParam(200, "kPa", false) },
            { CompressionPressure, new VariableParam(100, "MPa", false) },
            { FuelPressure, new VariableParam(100, "MPa", false) },
            { IntakePressure, new VariableParam(100, "kPa", false) },

            { Test3_1, new VariableParam(500, "", false) },
            { Test3_2, new VariableParam(500, "", false) },
            { Test3_3, new VariableParam(5000000, "", false) },
            { Test3_4, new VariableParam(500, "", false) },
            { Test3_5, new VariableParam(500, "", false) },

             // 区域4 - 发动机参数
            { Voltage, new VariableParam(800, "V", true) },
            { Current, new VariableParam(28000, "A", true) },
            { Frequency, new VariableParam(28000, "Hz", true) },
            { BatteryVoltage, new VariableParam(200, "V", false) },
            { GeneratorPower, new VariableParam(200, "W", false) },
            { PowerFactor, new VariableParam(200, "", false) },
            { FuelLevel, new VariableParam(200, "%", false) },
            { OilLevel, new VariableParam(200, "%", false) },
            { CoolantLevel, new VariableParam(100, "%", false) },
            { RunningHours, new VariableParam(100, "h", false) },
            { EngineLoad, new VariableParam(100, "%", false) },


            { Test4_1, new VariableParam(500, "", false) },
            { Test4_2, new VariableParam(500, "", false) },
            { Test4_3, new VariableParam(5000000, "", false) },
            { Test4_4, new VariableParam(500, "", false) },
            { Test4_5, new VariableParam(500, "", false) },
        
        
        
        
        
        
        
        
        
        
        


         // 区域4 - 电气/其他参数
        };
        // ==================== 根据区域获取变量列表 ====================
        public static List<string> GetVariablesByArea(int area)
        {
            switch (area)
            {
                case 1:
                    return new List<string>
            {
                ExhaustTemp, TurboASpeed, TurboBSpeed,
                TurboAGasTemp, TurboBGasTemp, AirTempBefore,
                AirTempAfter, AirPressure, YM, PowerValue, EngineSpeed,
                Test1_1,Test1_2,Test1_3,Test1_4,Test1_5
            };
                case 2:
                    return new List<string>
            {
                CoolantInTemp, CoolantOutTemp, OilInTemp, OilOutTemp,
                FuelInTemp, FuelOutTemp, AmbientTemp, IntakeAirTemp,
                ExhaustManifoldTemp, CylinderHeadTemp, OilPanTemp,
                Test2_1,Test2_2,Test2_3,Test2_4,Test2_5
            };
                case 3:
                    return new List<string>
            {
                OilPressure, FuelPressure, IntakePressure, ExhaustBackPressure,
                CoolantPressure, TurboAInPressure, TurboAOutPressure,
                TurboBInPressure, TurboBOutPressure, CrankcasePressure,
                CompressionPressure,
                Test3_1,Test3_2,Test3_3,Test3_4,Test3_5
            };
                case 4:
                    return new List<string>
            {
                Voltage, Current, Frequency, BatteryVoltage,
                GeneratorPower, PowerFactor, FuelLevel, OilLevel,
                CoolantLevel, RunningHours, EngineLoad,
                Test4_1,Test4_2,Test4_3,Test4_4,Test4_5
            };
                default:
                    return new List<string>();
            }
        }

        // 参数结构


        public class VariableParam
        {
            public double MaxValue { get; set; }
            public string Unit { get; set; }
            public bool IsPointer { get; set; }

            public VariableParam(double maxValue, string unit, bool isPointer)
            {
                MaxValue = maxValue;
                Unit = unit;
                IsPointer = isPointer;
            }
        }

        // ==================== 公共方法 ====================
        public static string GetDisplayName(string variableName)
        {
            return _displayNames.TryGetValue(variableName, out string name) ? name : variableName;
        }

        public static VariableParam GetParam(string variableName)
        {
            return _variableParams.TryGetValue(variableName, out var param) ? param : new VariableParam(100, "", false);
        }

        public static string GetVariableFromUdpKey(string udpKey)
        {
            if (string.IsNullOrEmpty(udpKey)) return null;
            foreach (var mapping in _udpMappings)
            {
                if (mapping.Value.Contains(udpKey)) // 移除ToLower()，严格匹配
                {
                    return mapping.Key;
                }
            }
            return null;
        }

        public static double Clamp(string variableName, double value)
        {
            var param = GetParam(variableName);
            return value < 0 ? 0 : value > param.MaxValue ? param.MaxValue : value;
        }

        // ==================== 扩展方法：添加新变量 ====================
        public static void AddVariable(string variableName, string displayName, VariableParam param, List<string> udpKeys = null)
        {
            _displayNames[variableName] = displayName;
            _variableParams[variableName] = param;

            if (udpKeys != null)
            {
                _udpMappings[variableName] = udpKeys;
            }

            Console.WriteLine($"[配置] 已添加新变量: {variableName} -> {displayName}");
        }

        // ==================== 快速重命名示例 ====================
        public static void RenameVariable(string oldName, string newName)
        {
            if (_displayNames.ContainsKey(oldName))
            {
                _displayNames[newName] = _displayNames[oldName];
                _displayNames.Remove(oldName);

                // 同样的方式更新其他字典...
                Console.WriteLine($"[配置] 已将变量 {oldName} 重命名为 {newName}");
            }
        }
    }
    #endregion
    public class GaugeGradientConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            if (!(value is double progress)) return Brushes.Gray;

            // 将进度0-1映射到角度0-360
            double angle = progress * 360;

            // 创建线性渐变，根据角度变化
            var brush = new LinearGradientBrush
            {
                StartPoint = new Point(0, 0),
                EndPoint = new Point(1, 1),
                // 根据进度设置渐变颜色
                GradientStops = new GradientStopCollection
            {
                new GradientStop(ColorFromProgress(progress, 0.0), 0.0),
                new GradientStop(ColorFromProgress(progress, 0.5), 0.5),
                new GradientStop(ColorFromProgress(progress, 1.0), 1.0)
            },
                Transform = new RotateTransform(angle, 0.5, 0.5)
            };

            return brush;
        }

        private Color ColorFromProgress(double progress, double position)
        {
            // 示例：根据进度和位置计算颜色
            // 这里可以根据需要自定义颜色逻辑
            if (progress < 0.3)
                return Color.FromRgb((byte)(255 * position), (byte)(128 * position), 50);
            else if (progress < 0.7)
                return Color.FromRgb((byte)(200 * position), (byte)(200 * position), 50);
            else
                return Color.FromRgb((byte)(50 * position), (byte)(255 * position), 50);
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        {
            throw new NotImplementedException();
        }
    }
    public class DynamicGradientConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            if (!(value is double currentValue)) return Brushes.Transparent;

            // 根据温度值创建渐变（0-200°C）
            double progress = Math.Min(currentValue / 200.0, 1.0);

            // 从绿色到红色的渐变
            var brush = new LinearGradientBrush
            {
                StartPoint = new Point(0, 0.5),  // 从左侧开始
                EndPoint = new Point(1, 0.5),    // 到右侧结束
                GradientStops = new GradientStopCollection
            {
                // 根据进度值动态调整颜色
                new GradientStop(Colors.LimeGreen, 0.0),
                new GradientStop(Colors.Yellow, 0.5),
                new GradientStop(Colors.Red, 1.0)
            }
            };

            return brush;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        {
            throw new NotImplementedException();
        }
    }
    #region 转换器（适配新配置）
    public class SemiCircleFillConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            double currentValue = (double)value;
            double maxValue = 800; // 指针固定最大值
            double percentage = Math.Max(0, Math.Min(1, currentValue / maxValue));

            if (percentage <= 0.001) return Geometry.Empty;

            double centerX = 40;
            double centerY = 40;
            double radius = 30;
            double startX = centerX - radius;
            double startY = centerY;

            string pathData;

            if (percentage <= 0.5)
            {
                double angle = 180 - (percentage * 180);
                double rad = angle * Math.PI / 180.0;
                double endX = centerX + radius * Math.Cos(rad);
                double endY = centerY - radius * Math.Sin(rad);
                pathData = $"M{startX},{startY} A{radius},{radius} 0 0 1 {endX:F2},{endY:F2}";
            }
            else
            {
                double midAngle = 90;
                double midRad = midAngle * Math.PI / 180.0;
                double midX = centerX + radius * Math.Cos(midRad);
                double midY = centerY - radius * Math.Sin(midRad);

                double endAngle = 180 - (percentage * 180);
                double endRad = endAngle * Math.PI / 180.0;
                double endX = centerX + radius * Math.Cos(endRad);
                double endY = centerY - radius * Math.Sin(endRad);

                pathData = $"M{startX},{startY} A{radius},{radius} 0 0 1 {midX:F2},{midY:F2} " +
                          $"A{radius},{radius} 0 0 1 {endX:F2},{endY:F2}";
            }

            return Geometry.Parse(pathData);
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        {
            throw new NotImplementedException();
        }
    }

    public class SemiCircleFillConverter1 : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            double currentValue = (double)value;
            double maxValue = 28000; // 指针固定最大值
            double percentage = Math.Max(0, Math.Min(1, currentValue / maxValue));

            if (percentage <= 0.001) return Geometry.Empty;

            double centerX = 40;
            double centerY = 40;
            double radius = 30;
            double startX = centerX - radius;
            double startY = centerY;

            string pathData;

            if (percentage <= 0.5)
            {
                double angle = 180 - (percentage * 180);
                double rad = angle * Math.PI / 180.0;
                double endX = centerX + radius * Math.Cos(rad);
                double endY = centerY - radius * Math.Sin(rad);
                pathData = $"M{startX},{startY} A{radius},{radius} 0 0 1 {endX:F2},{endY:F2}";
            }
            else
            {
                double midAngle = 90;
                double midRad = midAngle * Math.PI / 180.0;
                double midX = centerX + radius * Math.Cos(midRad);
                double midY = centerY - radius * Math.Sin(midRad);

                double endAngle = 180 - (percentage * 180);
                double endRad = endAngle * Math.PI / 180.0;
                double endX = centerX + radius * Math.Cos(endRad);
                double endY = centerY - radius * Math.Sin(endRad);

                pathData = $"M{startX},{startY} A{radius},{radius} 0 0 1 {midX:F2},{midY:F2} " +
                          $"A{radius},{radius} 0 0 1 {endX:F2},{endY:F2}";
            }

            return Geometry.Parse(pathData);
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        {
            throw new NotImplementedException();
        }
    }
    public class DialColorConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            double currentValue = (double)value;

            // 0-50: 绿色
            if (currentValue <= 50) return Brushes.LimeGreen;
            // 51-100: 黄色
            else if (currentValue <= 100) return Brushes.Yellow;
            // 101-150: 橙色
            else if (currentValue <= 150) return Brushes.Orange;
            // 151-200: 红色
            else return Brushes.Red;
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        {
            throw new NotImplementedException();
        }
    }

    public class PointerAngleConverter : IValueConverter
    {
        public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        {
            try
            {
                double currentValue = (double)value;
                double maxValue = double.Parse(parameter.ToString());
                double normalized = Math.Max(0, Math.Min(1, currentValue / maxValue));
                return -90 + (normalized * 180);
            }
            catch
            {
                return -90;
            }
        }

        public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        {
            throw new NotImplementedException();
        }
    }
    #endregion

    #region 智能ViewModel（自动适配配置）
    public class MainViewModel : INotifyPropertyChanged
    {


        #region 私有字段 - 使用VariableConfig中的常量名称
        private double _exhaustTemp = 0;     // 主机排气温度 
        private double _turboASpeed = 0;     // A排增压器转速
        private double _turboBSpeed = 0;    // B排增压器转速  
        private double _turboAGasTemp = 0;   // A列增压器废气温度
        private double _turboBGasTemp = 0;   // B列增压器废气温度
        private double _airTempBefore = 0;   // A排空冷器前空气温度
        private double _airTempAfter = 0;    // A排空冷器后空气温度
        private double _airPressure = 0;     // A排空冷器出口空气压力
        private double _ym = 0;             // 油门
        private double _powerValue = 0;     // 柴油机功率
        private double _engineSpeed = 0;     // 柴油机转速

        private double _test1_1 = 0;
        private double _test1_2 = 0;
        private double _test1_3 = 0;
        private double _test1_4 = 0;
        private double _test1_5 = 0;

        #region 私有字段 - 区域2：发动机参数
        private double _oilPressure = 0;            // 主机排气温度 
        private double _coolantInTemp = 0;         // A排增压器转速
        private double _fuelInTemp = 0;            // B排增压器转速  
        private double _oilOutTemp = 0;            // A列增压器废气温度
        private double _coolantOutTemp = 0;        // B列增压器废气温度
        private double _fuelOutTemp = 0;           // A排空冷器前空气温度
        private double _ambientTemp = 0;           // A排空冷器后空气温度
        private double _intakeAirTemp = 0;         // A排空冷器出口空气压力
        private double _exhaustManifoldTemp = 0;   // 油门
        private double _cylinderHeadTemp = 0;      // 柴油机功率
        private double _oilPanTemp = 0;            // 柴油机转速

        private double _test2_1 = 0;
        private double _test2_2 = 0;
        private double _test2_3 = 0;
        private double _test2_4 = 0;
        private double _test2_5 = 0;



        //取余2


        #endregion

        #region 私有字段 - 区域3：发动机参数
        private double _oilInTemp = 0;                 // 主机排气温度 
        private double _exhaustBackPressure = 0;       // A排增压器转速
        private double _coolantPressure = 0;          // B排增压器转速  
        private double _turboAInPressure = 0;        // A列增压器废气温度
        private double _turboAOutPressure = 0;          // B列增压器废气温度
        private double _turboBInPressure = 0;           // A排空冷器前空气温度
        private double _turboBOutPressure = 0;          // A排空冷器后空气温度
        private double _crankcasePressure = 0;          // A排空冷器出口空气压力
        private double _compressionPressure = 0;       // 油门
        private double _fuelPressure = 0;             // 柴油机功率
        private double _intakePressure = 0;             // 柴油机转速

        private double _test3_1 = 0;
        private double _test3_2 = 0;
        private double _test3_3 = 0;
        private double _test3_4 = 0;
        private double _test3_5 = 0;

        #endregion

        #region 私有字段 - 区域4：电气/其他参数
        private double _voltage = 0;                      // 主机排气温度 
        private double _current = 0;                         // A排增压器转速
        private double _frequency = 0;                    // B排增压器转速  
        private double _batteryVoltage = 0;               // A列增压器废气温度
        private double _generatorPower = 0;                  // B列增压器废气温度
        private double _powerFactor =0;                  // A排空冷器前空气温度
        private double _fuelLevel = 0;                       // A排空冷器后空气温度
        private double _oilLevel = 0;                        // A排空冷器出口空气压力
        private double _coolantLevel = 0;                    // 油门
        private double _runningHours = 0;                    // 柴油机功率
        private double _engineLoad = 0;                      // 柴油机转速

        private double _test4_1 = 0;
        private double _test4_2 = 0;
        private double _test4_3 = 0;
        private double _test4_4 = 0;
        private double _test4_5 = 0;
        #endregion



        private UDPClient _udpClient;
        private readonly Dispatcher _dispatcher;
        #endregion

        #region 构造函数

        public double CoolantInTemp
        {
            get => _coolantInTemp;
            set
            {
                double oldValue = _coolantInTemp;
                _coolantInTemp = VariableConfig.Clamp(VariableConfig.CoolantInTemp, value);
                if (Math.Abs(_coolantInTemp - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.CoolantInTemp)}: {oldValue} -> {_coolantInTemp}");
                    OnPropertyChanged();
                }
            }
        }
        public double CoolantOutTemp
        {
            get => _coolantOutTemp;
            set
            {
                double oldValue = _coolantOutTemp;
                _coolantOutTemp = VariableConfig.Clamp(VariableConfig.CoolantOutTemp, value);
                if (Math.Abs(_coolantOutTemp - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.CoolantOutTemp)}: {oldValue} -> {_coolantOutTemp}");
                    OnPropertyChanged();
                }
            }
        }
        public double OilInTemp
        {
            get => _oilInTemp;
            set
            {
                double oldValue = _oilInTemp;
                _oilInTemp = VariableConfig.Clamp(VariableConfig.OilInTemp, value);
                if (Math.Abs(_oilInTemp - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.OilInTemp)}: {oldValue} -> {_oilInTemp}");
                    OnPropertyChanged();
                }
            }
        }
        public double OilOutTemp
        {
            get => _oilOutTemp;
            set
            {
                double oldValue = _oilOutTemp;
                _oilOutTemp = VariableConfig.Clamp(VariableConfig.OilOutTemp, value);
                if (Math.Abs(_oilOutTemp - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.OilOutTemp)}: {oldValue} -> {_oilOutTemp}");
                    OnPropertyChanged();
                }
            }
        }
        public double FuelInTemp
        {
            get => _fuelInTemp;
            set
            {
                double oldValue = _fuelInTemp;
                _fuelInTemp = VariableConfig.Clamp(VariableConfig.FuelInTemp, value);
                if (Math.Abs(_fuelInTemp - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.FuelInTemp)}: {oldValue} -> {_fuelInTemp}");
                    OnPropertyChanged();
                }
            }
        }
        public double FuelOutTemp
        {
            get => _fuelOutTemp;
            set
            {
                double oldValue = _fuelOutTemp;
                _fuelOutTemp = VariableConfig.Clamp(VariableConfig.FuelOutTemp, value);
                if (Math.Abs(_fuelOutTemp - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.FuelOutTemp)}: {oldValue} -> {_fuelOutTemp}");
                    OnPropertyChanged();
                }
            }
        }

        public double AmbientTemp
        {
            get => _ambientTemp;
            set
            {
                double oldValue = _ambientTemp;
                _ambientTemp = VariableConfig.Clamp(VariableConfig.AmbientTemp, value);
                if (Math.Abs(_ambientTemp - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.AmbientTemp)}: {oldValue} -> {_ambientTemp}");
                    OnPropertyChanged();
                }
            }
        }

        public double IntakeAirTemp
        {
            get => _intakeAirTemp;
            set
            {
                double oldValue = _intakeAirTemp;
                _intakeAirTemp = VariableConfig.Clamp(VariableConfig.IntakeAirTemp, value);
                if (Math.Abs(_intakeAirTemp - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.IntakeAirTemp)}: {oldValue} -> {_intakeAirTemp}");
                    OnPropertyChanged();
                }
            }
        }
        ///区域2环形
        public double ExhaustManifoldTemp
        {
            get => _exhaustManifoldTemp;
            set
            {
                double oldValue = _exhaustManifoldTemp;
                _exhaustManifoldTemp = VariableConfig.Clamp(VariableConfig.ExhaustManifoldTemp, value);
                if (Math.Abs(_exhaustManifoldTemp - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.ExhaustManifoldTemp)}: {oldValue} -> {_exhaustManifoldTemp}");
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(ExhaustManifoldTempRingPath));
                }
            }
        }





        public double CylinderHeadTemp
        {
            get => _cylinderHeadTemp;
            set
            {
                double oldValue = _cylinderHeadTemp;
                _cylinderHeadTemp = VariableConfig.Clamp(VariableConfig.CylinderHeadTemp, value);
                if (Math.Abs(_cylinderHeadTemp - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.CylinderHeadTemp)}: {oldValue} -> {_cylinderHeadTemp}");
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(CylinderHeadTempRingPath));
                }
            }
        }

        public double OilPanTemp
        {
            get => _oilPanTemp;
            set
            {
                double oldValue = _oilPanTemp;
                _oilPanTemp = VariableConfig.Clamp(VariableConfig.OilPanTemp, value);
                if (Math.Abs(_oilPanTemp - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.OilPanTemp)}: {oldValue} -> {_oilPanTemp}");
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(OilPanTempRingPath));
                }
            }
        }



        public double OilPressure { get => _oilPressure; set => SetProperty(ref _oilPressure, value, VariableConfig.OilPressure); }
        //public double FuelPressure { get => _fuelPressure; set => SetProperty(ref _fuelPressure, value, VariableConfig.FuelPressure); }
        //public double IntakePressure { get => _intakePressure; set => SetProperty(ref _intakePressure, value, VariableConfig.IntakePressure); }
        public double ExhaustBackPressure { get => _exhaustBackPressure; set => SetProperty(ref _exhaustBackPressure, value, VariableConfig.ExhaustBackPressure); }
        public double CoolantPressure { get => _coolantPressure; set => SetProperty(ref _coolantPressure, value, VariableConfig.CoolantPressure); }
        public double TurboAInPressure { get => _turboAInPressure; set => SetProperty(ref _turboAInPressure, value, VariableConfig.TurboAInPressure); }
        public double TurboAOutPressure { get => _turboAOutPressure; set => SetProperty(ref _turboAOutPressure, value, VariableConfig.TurboAOutPressure); }
        public double TurboBInPressure { get => _turboBInPressure; set => SetProperty(ref _turboBInPressure, value, VariableConfig.TurboBInPressure); }
        public double TurboBOutPressure { get => _turboBOutPressure; set => SetProperty(ref _turboBOutPressure, value, VariableConfig.TurboBOutPressure); }
        public double CrankcasePressure { get => _crankcasePressure; set => SetProperty(ref _crankcasePressure, value, VariableConfig.CrankcasePressure); }
        //public double CompressionPressure { get => _compressionPressure; set => SetProperty(ref _compressionPressure, value, VariableConfig.CompressionPressure); }
        public double CompressionPressure
        {
            get => _compressionPressure;
            set
            {
                double oldValue = _compressionPressure;
                _compressionPressure = VariableConfig.Clamp(VariableConfig.CompressionPressure, value);
                if (Math.Abs(_compressionPressure - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.CompressionPressure)}: {oldValue} -> {_compressionPressure}");
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(CompressionPressureRingPath));
                }
            }
        }

        public double FuelPressure
        {
            get => _fuelPressure;
            set
            {
                double oldValue = _fuelPressure;
                _fuelPressure = VariableConfig.Clamp(VariableConfig.FuelPressure, value);
                if (Math.Abs(_fuelPressure - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.FuelPressure)}: {oldValue} -> {_fuelPressure}");
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(FuelPressureRingPath));
                }
            }
        }

         public double IntakePressure
         {
             get => _intakePressure;
             set
             {
                 double oldValue = _intakePressure;
                 _intakePressure = VariableConfig.Clamp(VariableConfig.IntakePressure, value);
                 if (Math.Abs(_intakePressure - oldValue) > 0.001)
                 {
                     Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.IntakePressure)}: {oldValue} -> {_intakePressure}");
                     OnPropertyChanged();
                     OnPropertyChanged(nameof(IntakePressureRingPath));
                 }
             }
         }


        public double CoolantLevel
        {
            get => _coolantLevel;
            set
            {
                double oldValue = _coolantLevel;
                _coolantLevel = VariableConfig.Clamp(VariableConfig.CoolantLevel, value);
                if (Math.Abs(_coolantLevel - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.CoolantLevel)}: {oldValue} -> {_coolantLevel}");
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(CoolantLevelRingPath));
                }
            }
        }

        public double RunningHours
        {
            get => _runningHours;
            set
            {
                double oldValue = _runningHours;
                _runningHours = VariableConfig.Clamp(VariableConfig.RunningHours, value);
                if (Math.Abs(_runningHours - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.RunningHours)}: {oldValue} -> {_runningHours}");
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(RunningHoursRingPath));
                }
            }
        }


        public double EngineLoad
        {
            get => _engineLoad;
            set
            {
                double oldValue = _engineLoad;
                _engineLoad = VariableConfig.Clamp(VariableConfig.EngineLoad, value);
                if (Math.Abs(_engineLoad - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.EngineLoad)}: {oldValue} -> {_engineLoad}");
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(EngineLoadRingPath));
                }
            }
        }


        public double Voltage { get => _voltage; set => SetProperty(ref _voltage, value, VariableConfig.Voltage); }
        public double Current { get => _current; set => SetProperty(ref _current, value, VariableConfig.Current); }
        public double Frequency { get => _frequency; set => SetProperty(ref _frequency, value, VariableConfig.Frequency); }
        public double BatteryVoltage { get => _batteryVoltage; set => SetProperty(ref _batteryVoltage, value, VariableConfig.BatteryVoltage); }
        public double GeneratorPower { get => _generatorPower; set => SetProperty(ref _generatorPower, value, VariableConfig.GeneratorPower); }
        public double PowerFactor { get => _powerFactor; set => SetProperty(ref _powerFactor, value, VariableConfig.PowerFactor); }
        public double FuelLevel { get => _fuelLevel; set => SetProperty(ref _fuelLevel, value, VariableConfig.FuelLevel); }
        public double OilLevel { get => _oilLevel; set => SetProperty(ref _oilLevel, value, VariableConfig.OilLevel); }
        //public double CoolantLevel { get => _coolantLevel; set => SetProperty(ref _coolantLevel, value, VariableConfig.CoolantLevel); }
        //public double RunningHours { get => _runningHours; set => SetProperty(ref _runningHours, value, VariableConfig.RunningHours); }
        //public double EngineLoad { get => _engineLoad; set => SetProperty(ref _engineLoad, value, VariableConfig.EngineLoad); }

        private void SetProperty(ref double field, double value, string variableName)
        {
            double oldValue = field;
            double clampedValue = VariableConfig.Clamp(variableName, value);

            if (Math.Abs(field - clampedValue) > 0.001)
            {
                field = clampedValue;
                Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(variableName)}: {oldValue} -> {field}");
                OnPropertyChanged(variableName);
            }
        }
        public MainViewModel()
        {
            _dispatcher = Dispatcher.CurrentDispatcher;
            InitializeUdpClient();

            Console.WriteLine($"[VM] ViewModel已初始化，使用变量配置:");
            foreach (var variable in GetVariableList())
            {
                var param = VariableConfig.GetParam(variable);
                Console.WriteLine($"[VM]   {variable}: {VariableConfig.GetDisplayName(variable)} " +
                                $"(最大值:{param.MaxValue}{param.Unit}, 指针:{param.IsPointer})");
            }
        }

        private List<string> GetVariableList()
        {

            var allVariables = new List<string>();

            // 区域1变量
            allVariables.AddRange(VariableConfig.GetVariablesByArea(1));

            // 区域2变量
            allVariables.AddRange(VariableConfig.GetVariablesByArea(2));

            // 区域3变量
            allVariables.AddRange(VariableConfig.GetVariablesByArea(3));

            // 区域4变量
            allVariables.AddRange(VariableConfig.GetVariablesByArea(4));

            // 测试变量
            //allVariables.Add(VariableConfig.Test1_1);

            return allVariables;
            //return new List<string>
            //{
            //    VariableConfig.ExhaustTemp,
            //    VariableConfig.TurboASpeed,
            //    VariableConfig.TurboBSpeed,
            //    VariableConfig.TurboAGasTemp,
            //    VariableConfig.TurboBGasTemp,
            //    VariableConfig.AirTempBefore,
            //    VariableConfig.AirTempAfter,
            //    VariableConfig.AirPressure,
            //    VariableConfig.YM,
            //    VariableConfig.PowerValue,
            //    VariableConfig.EngineSpeed,
            //    VariableConfig.Voltage,


            //    VariableConfig.Test
            //};
        }
        #endregion

        #region 属性定义 - 使用VariableConfig统一管理
        // ==================== 指针型变量 ====================
        public double Test1_1
        {
            get => _test1_1;
            set
            {
                double oldValue = _test1_1;
                _test1_1 = VariableConfig.Clamp(VariableConfig.Test1_1, value); // 自动限制数值范围
                //_test1_1 = value; // 自动限制数值范围
                if (Math.Abs(_test1_1 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test1_1)}: {oldValue} -> {_test1_1}");
                OnPropertyChanged(); // 通知UI更新
                }
            }
        }
        public double Test1_2
        {
            get => _test1_2;
            set
            {
                double oldValue = _test1_2;
                _test1_2 = VariableConfig.Clamp(VariableConfig.Test1_2, value); // 自动限制数值范围
                if (Math.Abs(_test1_2 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test1_2)}: {oldValue} -> {_test1_2}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }
        public double Test1_3
        {
            get => _test1_3;
            set
            {
                double oldValue = _test1_3;
                _test1_3 = VariableConfig.Clamp(VariableConfig.Test1_3, value); // 自动限制数值范围
                if (Math.Abs(_test1_3 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test1_3)}: {oldValue} -> {_test1_3}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }
        public double Test1_4
        {
            get => _test1_4;
            set
            {
                double oldValue = _test1_4;
                _test1_4 = VariableConfig.Clamp(VariableConfig.Test1_4, value); // 自动限制数值范围
                if (Math.Abs(_test1_4 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test1_4)}: {oldValue} -> {_test1_4}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }
        public double Test1_5
        {
            get => _test1_5;
            set
            {
                double oldValue = _test1_5;
                _test1_5 = VariableConfig.Clamp(VariableConfig.Test1_5, value); // 自动限制数值范围
                if (Math.Abs(_test1_5 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test1_5)}: {oldValue} -> {_test1_5}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }
        public double Test2_1
        {
            get => _test2_1;
            set
            {
                double oldValue = _test2_1;
                _test2_1 = VariableConfig.Clamp(VariableConfig.Test2_1, value); // 自动限制数值范围
                if (Math.Abs(_test2_1 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test2_1)}: {oldValue} -> {_test2_1}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }

        public double Test2_2
        {
            get => _test2_2;
            set
            {
                double oldValue = _test2_2;
                _test2_2 = VariableConfig.Clamp(VariableConfig.Test2_2, value); // 自动限制数值范围
                if (Math.Abs(_test2_2 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test2_2)}: {oldValue} -> {_test2_2}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }

        public double Test2_3
        {
            get => _test2_3;
            set
            {
                double oldValue = _test2_3;
                _test2_3 = VariableConfig.Clamp(VariableConfig.Test2_3, value); // 自动限制数值范围
                if (Math.Abs(_test2_3 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test2_3)}: {oldValue} -> {_test2_3}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }

        public double Test2_4
        {
            get => _test2_4;
            set
            {
                double oldValue = _test2_4;
                _test2_4 = VariableConfig.Clamp(VariableConfig.Test2_4, value); // 自动限制数值范围
                if (Math.Abs(_test2_4 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test2_4)}: {oldValue} -> {_test2_4}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }

        public double Test2_5
        {
            get => _test2_5;
            set
            {
                double oldValue = _test2_5;
                _test2_5 = VariableConfig.Clamp(VariableConfig.Test2_5, value); // 自动限制数值范围
                if (Math.Abs(_test2_5 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test2_5)}: {oldValue} -> {_test2_5}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }

        public double Test3_1
        {
            get => _test3_1;
            set
            {
                double oldValue = _test3_1;
                _test3_1 = VariableConfig.Clamp(VariableConfig.Test3_1, value); // 自动限制数值范围
                if (Math.Abs(_test3_1 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test3_1)}: {oldValue} -> {_test3_1}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }
        public double Test3_2
        {
            get => _test3_2;
            set
            {
                double oldValue = _test3_2;
                _test3_2 = VariableConfig.Clamp(VariableConfig.Test3_2, value); // 自动限制数值范围
                if (Math.Abs(_test3_2 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test3_2)}: {oldValue} -> {_test3_2}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }
        public double Test3_3
        {
            get => _test3_3;
            set
            {
                double oldValue = _test3_3;
                _test3_3 = VariableConfig.Clamp(VariableConfig.Test3_3, value); // 自动限制数值范围
                if (Math.Abs(_test3_3 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test3_3)}: {oldValue} -> {_test3_3}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }
        public double Test3_4
        {
            get => _test3_4;
            set
            {
                double oldValue = _test3_4;
                _test3_4 = VariableConfig.Clamp(VariableConfig.Test3_4, value); // 自动限制数值范围
                if (Math.Abs(_test3_4 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test3_4)}: {oldValue} -> {_test3_4}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }

        public double Test3_5
        {
            get => _test3_5;
            set
            {
                double oldValue = _test3_5;
                _test3_5 = VariableConfig.Clamp(VariableConfig.Test3_5, value); // 自动限制数值范围
                if (Math.Abs(_test3_5 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test3_5)}: {oldValue} -> {_test3_5}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }

        public double Test4_1
        {
            get => _test4_1;
            set
            {
                double oldValue = _test4_1;
                _test4_1 = VariableConfig.Clamp(VariableConfig.Test4_1, value); // 自动限制数值范围
                if (Math.Abs(_test4_1 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test4_1)}: {oldValue} -> {_test4_1}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }
        public double Test4_2
        {
            get => _test4_2;
            set
            {
                double oldValue = _test4_2;
                _test4_2 = VariableConfig.Clamp(VariableConfig.Test4_2, value); // 自动限制数值范围
                if (Math.Abs(_test4_2 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test4_2)}: {oldValue} -> {_test4_2}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }
        public double Test4_3
        {
            get => _test4_3;
            set
            {
                double oldValue = _test4_3;
                _test4_3 = VariableConfig.Clamp(VariableConfig.Test4_3, value); // 自动限制数值范围
                if (Math.Abs(_test4_3 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test4_3)}: {oldValue} -> {_test4_3}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }
        public double Test4_4
        {
            get => _test4_4;
            set
            {
                double oldValue = _test4_4;
                _test4_4 = VariableConfig.Clamp(VariableConfig.Test4_4, value); // 自动限制数值范围
                if (Math.Abs(_test4_4 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test4_4)}: {oldValue} -> {_test4_4}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }

        public double Test4_5
        {
            get => _test4_5;
            set
            {
                double oldValue = _test4_5;
                _test4_5 = VariableConfig.Clamp(VariableConfig.Test4_5, value); // 自动限制数值范围
                if (Math.Abs(_test4_5 - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.Test4_5)}: {oldValue} -> {_test4_5}");
                    OnPropertyChanged(); // 通知UI更新
                }
            }
        }

        public double ExhaustTemp
        {
            get => _exhaustTemp;
            set
            {
                double oldValue = _exhaustTemp;
                _exhaustTemp = VariableConfig.Clamp(VariableConfig.ExhaustTemp, value);
                if (Math.Abs(_exhaustTemp - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.ExhaustTemp)}: {oldValue} -> {_exhaustTemp}");
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(ExhaustTempPointerAngle));
                }
            }
        }

        public double TurboASpeed
        {
            get => _turboASpeed;
            set
            {
                double oldValue = _turboASpeed;
                _turboASpeed = VariableConfig.Clamp(VariableConfig.TurboASpeed, value);
                if (Math.Abs(_turboASpeed - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.TurboASpeed)}: {oldValue} -> {_turboASpeed}");
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(TurboASpeedPointerAngle));
                }
            }
        }

        public double TurboBSpeed
        {
            get => _turboBSpeed;
            set
            {
                double oldValue = _turboBSpeed;
                _turboBSpeed = VariableConfig.Clamp(VariableConfig.TurboBSpeed, value);
                if (Math.Abs(_turboBSpeed - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.TurboBSpeed)}: {oldValue} -> {_turboBSpeed}");
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(TurboBSpeedPointerAngle));
                }
            }
        }

        // ==================== 温度压力变量 ====================
        public double TurboAGasTemp
        {
            get => _turboAGasTemp;
            set
            {
                double oldValue = _turboAGasTemp;
                _turboAGasTemp = VariableConfig.Clamp(VariableConfig.TurboAGasTemp, value);
                if (Math.Abs(_turboAGasTemp - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.TurboAGasTemp)}: {oldValue} -> {_turboAGasTemp}");
                    OnPropertyChanged();
                }
            }
        }

        public double TurboBGasTemp
        {
            get => _turboBGasTemp;
            set
            {
                double oldValue = _turboBGasTemp;
                _turboBGasTemp = VariableConfig.Clamp(VariableConfig.TurboBGasTemp, value);
                if (Math.Abs(_turboBGasTemp - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.TurboBGasTemp)}: {oldValue} -> {_turboBGasTemp}");
                    OnPropertyChanged();
                }
            }
        }

        public double AirTempBefore
        {
            get => _airTempBefore;
            set
            {
                double oldValue = _airTempBefore;
                _airTempBefore = VariableConfig.Clamp(VariableConfig.AirTempBefore, value);
                if (Math.Abs(_airTempBefore - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.AirTempBefore)}: {oldValue} -> {_airTempBefore}");
                    OnPropertyChanged();
                }
            }
        }

        public double AirTempAfter
        {
            get => _airTempAfter;
            set
            {
                double oldValue = _airTempAfter;
                _airTempAfter = VariableConfig.Clamp(VariableConfig.AirTempAfter, value);
                if (Math.Abs(_airTempAfter - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.AirTempAfter)}: {oldValue} -> {_airTempAfter}");
                    OnPropertyChanged();
                }
            }
        }

        public double AirPressure
        {
            get => _airPressure;
            set
            {
                double oldValue = _airPressure;
                _airPressure = VariableConfig.Clamp(VariableConfig.AirPressure, value);
                if (Math.Abs(_airPressure - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.AirPressure)}: {oldValue} -> {_airPressure}");
                    OnPropertyChanged();
                }
            }
        }

        // ==================== 环形图变量 ====================
        public double YM
        {
            get => _ym;
            set
            {
                double oldValue = _ym;
                _ym = VariableConfig.Clamp(VariableConfig.YM, value);
                if (Math.Abs(_ym - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.YM)}: {oldValue} -> {_ym}");
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(YMRingPath));
                }
            }
        }

        public double PowerValue
        {
            get => _powerValue;
            set
            {
                double oldValue = _powerValue;
                _powerValue = VariableConfig.Clamp(VariableConfig.PowerValue, value);
                if (Math.Abs(_powerValue - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.PowerValue)}: {oldValue} -> {_powerValue}");
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(PowerRingPath));
                }
            }
        }

        public double EngineSpeed
        {
            get => _engineSpeed;
            set
            {
                double oldValue = _engineSpeed;
                _engineSpeed = VariableConfig.Clamp(VariableConfig.EngineSpeed, value);
                if (Math.Abs(_engineSpeed - oldValue) > 0.001)
                {
                    Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(VariableConfig.EngineSpeed)}: {oldValue} -> {_engineSpeed}");
                    OnPropertyChanged();
                    OnPropertyChanged(nameof(SpeedRingPath));
                }
            }
        }
      
        #endregion

        #region 计算属性（XAML绑定用）
        // 指针角度
        public double ExhaustTempPointerAngle => -90 + ((_exhaustTemp / VariableConfig.GetParam(VariableConfig.ExhaustTemp).MaxValue) * 180);
        public double TurboASpeedPointerAngle => -90 + ((_turboASpeed / VariableConfig.GetParam(VariableConfig.TurboASpeed).MaxValue) * 180);
        public double TurboBSpeedPointerAngle => -90 + ((_turboBSpeed / VariableConfig.GetParam(VariableConfig.TurboBSpeed).MaxValue) * 180);
        // 区域4指针角度
        public double VoltagePointerAngle => -90 + ((_voltage / VariableConfig.GetParam(VariableConfig.Voltage).MaxValue) * 180);
        public double CurrentPointerAngle => -90 + ((_current / VariableConfig.GetParam(VariableConfig.Current).MaxValue) * 180);
        public double FrequencyPointerAngle => -90 + ((_frequency / VariableConfig.GetParam(VariableConfig.Frequency).MaxValue) * 180);

        // 环形图路径（特殊处理）
        public string YMRingPath => GenerateRingPath(_ym, VariableConfig.GetParam(VariableConfig.YM).MaxValue, 50, 50, 30, 28);
        public string PowerRingPath => GenerateRingPath(_powerValue, VariableConfig.GetParam(VariableConfig.PowerValue).MaxValue, 50, 50, 20, 18);
        public string SpeedRingPath => GenerateRingPath(_engineSpeed, VariableConfig.GetParam(VariableConfig.EngineSpeed).MaxValue, 50, 50, 10, 8);

        // ==================== 区域2：电气参数 ====================

        // 环形图路径

        public string ExhaustManifoldTempRingPath => GenerateRingPath(_exhaustManifoldTemp, VariableConfig.GetParam(VariableConfig.ExhaustManifoldTemp).MaxValue, 50, 50, 30, 28);
        public string CylinderHeadTempRingPath => GenerateRingPath(_cylinderHeadTemp, VariableConfig.GetParam(VariableConfig.CylinderHeadTemp).MaxValue, 50, 50, 20, 18);
        public string OilPanTempRingPath => GenerateRingPath(_oilPanTemp, VariableConfig.GetParam(VariableConfig.OilPanTemp).MaxValue, 50, 50, 10, 8);
        //public string ExhaustManifoldTempRingPath => GenerateRingPath(_exhaustManifoldTemp, VariableConfig.GetParam(VariableConfig.ExhaustManifoldTemp).MaxValue, 50, 50, 50, 47);
        //public string CurrentRingPath => GenerateRingPath(_current, VariableConfig.GetParam(VariableConfig.Current).MaxValue, 50, 50, 42, 39);
        //public string FrequencyRingPath => GenerateRingPath(_frequency, VariableConfig.GetParam(VariableConfig.Frequency).MaxValue, 50, 50, 34, 31);

        // ==================== 区域3：冷却参数 ====================
        // 指针角度
        public double OilPressurePointerAngle => -90 + ((_oilPressure / VariableConfig.GetParam(VariableConfig.OilPressure).MaxValue) * 180);
        public double CoolantTempPointerAngle => -90 + ((_coolantInTemp / VariableConfig.GetParam(VariableConfig.CoolantInTemp).MaxValue) * 180);
        public double FuelTempPointerAngle => -90 + ((_fuelInTemp / VariableConfig.GetParam(VariableConfig.FuelInTemp).MaxValue) * 180);

        // 环形图路径
        public string OilPressureRingPath => GenerateRingPath(_oilPressure, VariableConfig.GetParam(VariableConfig.OilPressure).MaxValue, 50, 50, 30, 28);
        public string CoolantTempRingPath => GenerateRingPath(_coolantInTemp, VariableConfig.GetParam(VariableConfig.CoolantInTemp).MaxValue, 50, 50, 20, 18);
        public string FuelTempRingPath => GenerateRingPath(_fuelInTemp, VariableConfig.GetParam(VariableConfig.FuelInTemp).MaxValue, 50, 50, 10, 8);

        // ==================== 区域4：性能参数 ====================
        // 指针角度
        public double OilInTempPointerAngle => -90 + ((_oilInTemp / VariableConfig.GetParam(VariableConfig.OilInTemp).MaxValue) * 180);
        public double ExhaustBackPressurePointerAngle => -90 + ((_exhaustBackPressure / VariableConfig.GetParam(VariableConfig.ExhaustBackPressure).MaxValue) * 180);
        public double CoolantPressurePointerAngle => -90 + ((_coolantPressure / VariableConfig.GetParam(VariableConfig.CoolantPressure).MaxValue) * 180);

        // 环形图路径
        public string CompressionPressureRingPath => GenerateRingPath(_compressionPressure, VariableConfig.GetParam(VariableConfig.CompressionPressure).MaxValue, 50, 50, 30, 28);
        public string FuelPressureRingPath => GenerateRingPath(_fuelPressure, VariableConfig.GetParam(VariableConfig.FuelPressure).MaxValue, 50, 50, 20, 18);
        public string IntakePressureRingPath => GenerateRingPath(_intakePressure, VariableConfig.GetParam(VariableConfig.IntakePressure).MaxValue, 50, 50, 10, 8);

        // 环形图路径
        public string CoolantLevelRingPath => GenerateRingPath(_coolantLevel, VariableConfig.GetParam(VariableConfig.CoolantLevel).MaxValue, 50, 50, 30, 28);
        public string RunningHoursRingPath => GenerateRingPath(_runningHours, VariableConfig.GetParam(VariableConfig.RunningHours).MaxValue, 50, 50, 20, 18);
        public string EngineLoadRingPath => GenerateRingPath(_engineLoad, VariableConfig.GetParam(VariableConfig.EngineLoad).MaxValue, 50, 50, 10, 8);

        private string GenerateRingPath(double value, double max, double centerX, double centerY, double outerRadius, double innerRadius)
        {
            // 绝对简单的版本
            double percent = Math.Min(99.9, value / max * 100);

            // 如果为0，不显示
            if (percent < 0.1) return "";

            // 转换为角度（0-360度，但留1度余量）
            double angle = Math.Min(359, percent * 3.6);

            // 直接使用字符串插值生成（最不容易出错）
            return string.Format(CultureInfo.InvariantCulture,
                "M{0},{1} A{2},{2} 0 {3},1 {4},{5} " +
                "L{6},{7} A{8},{8} 0 {3},0 {9},{10} Z",
                centerX, centerY - outerRadius,     // 起点
                outerRadius,
                angle > 180 ? 1 : 0,                // 大弧标志
                centerX + outerRadius * Math.Cos((angle - 90) * Math.PI / 180),  // 外弧终点
                centerY + outerRadius * Math.Sin((angle - 90) * Math.PI / 180),
                centerX + innerRadius * Math.Cos((angle - 90) * Math.PI / 180),  // 内弧终点
                centerY + innerRadius * Math.Sin((angle - 90) * Math.PI / 180),
                innerRadius,
                centerX, centerY - innerRadius      // 内弧起点
            );
        }
        #endregion

        #region UDP处理
        private void InitializeUdpClient()
        {
            try
            {
                _udpClient = new UDPClient();
                _udpClient.SendData += OnUdpDataReceived;
                _udpClient.UdpClientInite();
                Console.WriteLine("[VM] UDP客户端已初始化");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[VM] UDP初始化失败: {ex.Message}");
            }
        }

        private void OnUdpDataReceived(double time, Dictionary<string, double> data)
        {
            _dispatcher.Invoke(() =>
            {
                try
                {
                    Console.WriteLine($"\n[VM] 收到UDP数据，时间: {time}, 项数: {data.Count}");
                    ProcessUdpData(data);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[VM] 处理UDP数据失败: {ex.Message}");
                }
            });
        }

        private void ProcessUdpData(Dictionary<string, double> data)
        {
            int updatedCount = 0;

            foreach (var kvp in data)
            {
                string variableName = VariableConfig.GetVariableFromUdpKey(kvp.Key);
                if (variableName != null)
                {
                    // 使用反射动态设置属性值
                    var property = this.GetType().GetProperty(variableName);
                    if (property != null)
                    {
                        double oldValue = (double)property.GetValue(this);
                        property.SetValue(this, kvp.Value);
                        updatedCount++;
                        Console.WriteLine($"[VM] {VariableConfig.GetDisplayName(variableName)}: {oldValue} -> {kvp.Value}");
                    }
                }
                else
                {
                    Console.WriteLine($"[VM] 未识别的UDP键: {kvp.Key}");
                }
            }

            if (updatedCount > 0)
            {
                Console.WriteLine($"[VM] 成功更新 {updatedCount} 个属性");
            }
        }
        #endregion

        #region 操作方法
        public void ResetAllPointers()
        {
            ExhaustTemp = 0;
            TurboASpeed = 0;
            TurboBSpeed = 0;
            Console.WriteLine("[VM] 重置所有指针");
        }

        public void FullValueTest()
        {
            ExhaustTemp = VariableConfig.GetParam(VariableConfig.ExhaustTemp).MaxValue;
            TurboASpeed = VariableConfig.GetParam(VariableConfig.TurboASpeed).MaxValue;
            TurboBSpeed = VariableConfig.GetParam(VariableConfig.TurboBSpeed).MaxValue;
            Console.WriteLine("[VM] 执行满值测试");
        }

        public void Cleanup()
        {
            try
            {
                if (_udpClient != null)
                {
                    _udpClient.SendData -= OnUdpDataReceived;
                    Console.WriteLine("[VM] UDP事件订阅已移除");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[VM] 清理资源时出错: {ex.Message}");
            }
        }
        #endregion

        #region INotifyPropertyChanged
        public event PropertyChangedEventHandler PropertyChanged;
        protected virtual void OnPropertyChanged([CallerMemberName] string propertyName = null)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
        }
        #endregion
    }
    #endregion

    #region 主窗口

    public partial class AboutWindow : Window
    {
        private DispatcherTimer _followTimer; // 跟随定时器（50ms检测一次）
        private Process _targetProcess; // start.exe进程
        private User32.RECT _lastTargetRect; // 上一次的目标窗口位置
        private bool _isFollowing = true; // 是否开启跟随
        private IntPtr _windowHandle; // 当前WPF窗口句柄（确保非空）
        private readonly object _lockObj = new object(); // 线程锁，防止多线程冲突
        private bool _isProcessExitRegistered = false; // 标记是否已注册进程退出事件

        private MainViewModel _viewModel;
        private void PointerContainer1_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
        {
            // 这里编写点击后的业务逻辑，示例如下：
            // 1. 弹出提示框（可替换为你的实际需求，如显示详细温度、跳转到详情页等）
            MessageBox.Show("排气温度指针被点击啦！", "提示", MessageBoxButton.OK, MessageBoxImage.Information);

            // 2. 标记事件已处理，避免事件向上级元素冒泡（可选，根据业务需求决定是否添加）
            e.Handled = true;
        }
        public AboutWindow()
        {
            InitializeComponent();
            this.Topmost = true;
            this.WindowStyle = WindowStyle.None;
            this.AllowsTransparency = true;

            _viewModel = new MainViewModel();
            DataContext = _viewModel;

            InitWindowHandle();
            InitializeFollowTimer();

            Console.WriteLine("\n[UI] 柴油机监控系统已启动");
            Console.WriteLine("[UI] 正在查找并跟随 start.exe 窗口...");
            Console.WriteLine("[UI] 1. 修改变量显示名称：VariableConfig._displayNames");
            Console.WriteLine("[UI] 2. 修改UDP键名：VariableConfig._udpMappings");
            Console.WriteLine("[UI] 3. 修改参数设置：VariableConfig._variableParams");
            Console.WriteLine("==================================");
        }

        #region 核心基础初始化
        private void InitWindowHandle()
        {
            try
            {
                var interopHelper = new System.Windows.Interop.WindowInteropHelper(this);
                interopHelper.EnsureHandle();
                _windowHandle = interopHelper.Handle;
                if (_windowHandle != IntPtr.Zero)
                {
                    Console.WriteLine($"[句柄] 初始化成功：{_windowHandle.ToInt64()}");
                }
                else
                {
                    Console.WriteLine("[句柄] 初始化失败，将尝试重新获取");
                    this.Loaded += (s, e) =>
                    {
                        _windowHandle = new System.Windows.Interop.WindowInteropHelper(this).Handle;
                    };
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[句柄] 初始化异常：{ex.Message}");
            }
        }

        private void InitializeFollowTimer()
        {
            _followTimer = new DispatcherTimer
            {
                Interval = TimeSpan.FromMilliseconds(50)
            };
            _followTimer.Tick += FollowTimer_Tick;
            _followTimer.Start();
            Console.WriteLine("[跟随] 定时器已启动（50ms检测一次）");
        }
        #endregion

        #region 定时器核心逻辑
        private void FollowTimer_Tick(object sender, EventArgs e)
        {
            lock (_lockObj)
            {
                if (!_isFollowing || _windowHandle == IntPtr.Zero) return;

                try
                {
                    if (!CheckAndGetValidStartProcess())
                    {
                        _lastTargetRect = new User32.RECT();
                        return;
                    }

                    if (!User32.GetWindowRect(_targetProcess.MainWindowHandle, out User32.RECT targetRect) ||
                        !User32.IsWindowVisible(_targetProcess.MainWindowHandle) ||
                        targetRect.Width <= 10 || targetRect.Height <= 10)
                    {
                        return;
                    }

                    if (targetRect.Left != _lastTargetRect.Left ||
                        targetRect.Top != _lastTargetRect.Top ||
                        targetRect.Width != _lastTargetRect.Width ||
                        targetRect.Height != _lastTargetRect.Height)
                    {
                        SyncWithTargetWindow(targetRect);
                        _lastTargetRect = targetRect;
                    }

                    ForceTopMost();

                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[跟随] 检测异常：{ex.Message}");
                }
            }
        }
        #endregion

        #region 核心工具方法
        private bool CheckAndGetValidStartProcess()
        {
            if (_targetProcess != null && !_targetProcess.HasExited && _targetProcess.MainWindowHandle != IntPtr.Zero)
            {
                return true;
            }

            var startProcesses = Process.GetProcessesByName("start")
                .Where(p => !p.HasExited && p.MainWindowHandle != IntPtr.Zero)
                .ToList();

            if (startProcesses.Count == 0)
            {
                _targetProcess = null;
                _isProcessExitRegistered = false;
                Console.WriteLine("[跟随] 未找到有效start.exe进程（无主窗口/已退出），等待中...");
                return false;
            }

            _targetProcess = startProcesses.First();
            _targetProcess.EnableRaisingEvents = true;

            if (!_isProcessExitRegistered)
            {
                _targetProcess.Exited += OnStartProcessExited;
                _isProcessExitRegistered = true;
                Console.WriteLine($"[进程监听] 已注册start.exe退出事件（PID：{_targetProcess.Id}）");
            }

            Console.WriteLine($"[跟随] 找到有效start.exe进程：PID={_targetProcess.Id}，窗口句柄={_targetProcess.MainWindowHandle.ToInt64()}");
            return true;
        }

        /// <summary>
        /// C# 7.3 兼容版本：移除 ? 符号，保留所有逻辑
        /// </summary>
        private void OnStartProcessExited(object sender, EventArgs e)
        {
            Application.Current.Dispatcher.Invoke(() =>
            {
                // 空值判断逻辑不变，_targetProcess?.Id 在 C# 7.3 中仍可使用（这是空值传播运算符，7.3支持）
                Console.WriteLine($"[进程退出] 检测到start.exe（PID：{_targetProcess?.Id}）已关闭，正在关闭监控窗口...");

                // 清理资源（改为 C# 7.3 兼容的空值判断）
                if (_followTimer != null)
                {
                    _followTimer.Stop();
                }
                if (_viewModel != null)
                {
                    _viewModel.Cleanup();
                }

                this.Close();
                // Application.Current.Shutdown(); // 可选退出应用
            });
        }

        private void SyncWithTargetWindow(User32.RECT targetRect)
        {
            try
            {
                this.BeginInit();

                this.Left = targetRect.Left;
                this.Top = targetRect.Top;
                this.Width = targetRect.Width;
                this.Height = targetRect.Height;

                if (IsWindowMaximized(targetRect))
                {
                    if (this.WindowState != WindowState.Maximized)
                        this.WindowState = WindowState.Maximized;
                }
                else
                {
                    if (this.WindowState != WindowState.Normal)
                        this.WindowState = WindowState.Normal;
                }

                this.EndInit();
                Console.WriteLine($"[跟随] 同步窗口状态：位置({targetRect.Left},{targetRect.Top})，大小({targetRect.Width}x{targetRect.Height})");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[跟随] 同步窗口失败：{ex.Message}");
            }
        }

        private void ForceTopMost()
        {
            try
            {
                User32.SetWindowPos(
                    _windowHandle,
                    User32.HWND_TOPMOST,
                    0, 0, 0, 0,
                    User32.SWP_NOMOVE | User32.SWP_NOSIZE | User32.SWP_NOACTIVATE
                );
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[置顶] 强制置顶失败：{ex.Message}");
            }
        }

        private bool IsWindowMaximized(User32.RECT targetRect)
        {
            var screen = System.Windows.Forms.Screen.FromHandle(_targetProcess.MainWindowHandle);
            var workingArea = screen.WorkingArea;
            return Math.Abs(targetRect.Left - workingArea.Left) < 2 &&
                   Math.Abs(targetRect.Top - workingArea.Top) < 2 &&
                   Math.Abs(targetRect.Right - workingArea.Right) < 2 &&
                   Math.Abs(targetRect.Bottom - workingArea.Bottom) < 2;
        }
        #endregion

        #region 原有按钮事件（无改动）
        private void BtnAddExhaustTemp_Click(object sender, RoutedEventArgs e)
        {
            double oldValue = _viewModel.ExhaustTemp;
            _viewModel.ExhaustTemp += 5;
            Console.WriteLine($"[UI] {VariableConfig.GetDisplayName(VariableConfig.ExhaustTemp)} {oldValue} -> {_viewModel.ExhaustTemp}");
        }

        private void BtnMinusExhaustTemp_Click(object sender, RoutedEventArgs e)
        {
            double oldValue = _viewModel.ExhaustTemp;
            _viewModel.ExhaustTemp -= 5;
            Console.WriteLine($"[UI] {VariableConfig.GetDisplayName(VariableConfig.ExhaustTemp)} {oldValue} -> {_viewModel.ExhaustTemp}");
        }

        private void BtnAddTurboASpeed_Click(object sender, RoutedEventArgs e)
        {
            double oldValue = _viewModel.TurboASpeed;
            _viewModel.TurboASpeed += 5;
            Console.WriteLine($"[UI] {VariableConfig.GetDisplayName(VariableConfig.TurboASpeed)} {oldValue} -> {_viewModel.TurboASpeed}");
        }

        private void BtnMinusTurboASpeed_Click(object sender, RoutedEventArgs e)
        {
            double oldValue = _viewModel.TurboASpeed;
            _viewModel.TurboASpeed -= 5;
            Console.WriteLine($"[UI] {VariableConfig.GetDisplayName(VariableConfig.TurboASpeed)} {oldValue} -> {_viewModel.TurboASpeed}");
        }

        private void BtnAddTurboBSpeed_Click(object sender, RoutedEventArgs e)
        {
            double oldValue = _viewModel.TurboBSpeed;
            _viewModel.TurboBSpeed += 5;
            Console.WriteLine($"[UI] {VariableConfig.GetDisplayName(VariableConfig.TurboBSpeed)} {oldValue} -> {_viewModel.TurboBSpeed}");
        }

        private void BtnMinusTurboBSpeed_Click(object sender, RoutedEventArgs e)
        {
            double oldValue = _viewModel.TurboBSpeed;
            _viewModel.TurboBSpeed -= 5;
            Console.WriteLine($"[UI] {VariableConfig.GetDisplayName(VariableConfig.TurboBSpeed)} {oldValue} -> {_viewModel.TurboBSpeed}");
        }

        private void BtnResetPointer_Click(object sender, RoutedEventArgs e)
        {
            _viewModel.ResetAllPointers();
            Console.WriteLine($"[UI] 重置指针: {VariableConfig.GetDisplayName(VariableConfig.ExhaustTemp)}, " +
                            $"{VariableConfig.GetDisplayName(VariableConfig.TurboASpeed)}, " +
                            $"{VariableConfig.GetDisplayName(VariableConfig.TurboBSpeed)}");
        }

        private void BtnFullValueTest_Click(object sender, RoutedEventArgs e)
        {
            _viewModel.FullValueTest();
            Console.WriteLine($"[UI] 满值测试: 使用VariableConfig中的最大值");
        }

        private void BtnAbout_Click(object sender, RoutedEventArgs e)
        {
            AboutPopup.IsOpen = true;
            Console.WriteLine("[UI] 打开关于窗口");
        }

        private void BtnCloseAbout_Click(object sender, RoutedEventArgs e)
        {
            AboutPopup.IsOpen = false;
            Console.WriteLine("[UI] 关闭关于窗口");
        }
        #endregion

        #region 原有窗口事件（无改动）
        protected override void OnClosed(EventArgs e)
        {
            base.OnClosed(e);
            if (_viewModel != null)
            {
                _viewModel.Cleanup();
            }
            if (_followTimer != null)
            {
                _followTimer.Stop();
            }
            if (_targetProcess != null && !_targetProcess.HasExited)
            {
                _targetProcess.Exited -= OnStartProcessExited;
            }
            Console.WriteLine("[UI] 窗口已关闭，资源已清理");
        }

        private void Window_Loaded(object sender, RoutedEventArgs e)
        {
            Console.WriteLine("\n[UI] 窗口加载完成");
            Console.WriteLine("[UI] 当前数值状态:");
            StartAutoTest();

            var variables = new List<(string name, double value)>
        {
            (VariableConfig.ExhaustTemp, _viewModel.ExhaustTemp),
            (VariableConfig.TurboASpeed, _viewModel.TurboASpeed),
            (VariableConfig.TurboBSpeed, _viewModel.TurboBSpeed),
            (VariableConfig.TurboAGasTemp, _viewModel.TurboAGasTemp),
            (VariableConfig.TurboBGasTemp, _viewModel.TurboBGasTemp),
            (VariableConfig.AirTempBefore, _viewModel.AirTempBefore),
            (VariableConfig.AirTempAfter, _viewModel.AirTempAfter),
            (VariableConfig.AirPressure, _viewModel.AirPressure),
            (VariableConfig.YM, _viewModel.YM),
            (VariableConfig.PowerValue, _viewModel.PowerValue),
            (VariableConfig.EngineSpeed, _viewModel.EngineSpeed)
        };

            foreach (var (varName, value) in variables)
            {
                var param = VariableConfig.GetParam(varName);
                Console.WriteLine($"[UI] {VariableConfig.GetDisplayName(varName)}: {value}{param.Unit}");
            }

            Console.WriteLine("==================================");
        }

        private void Window_SizeChanged(object sender, SizeChangedEventArgs e)
        {
            double scale = Math.Min(
                this.ActualWidth / 1000,
                this.ActualHeight / 700
            );
            scale = Math.Max(0.8, Math.Min(1.2, scale));
            Console.WriteLine($"[UI] 窗口尺寸: {this.ActualWidth:F0}x{this.ActualHeight:F0}, 缩放比例: {scale:F2}");
        }

        private void StartAutoTest()
        {
            var timer = new DispatcherTimer
            {
                Interval = TimeSpan.FromSeconds(2)
            };

            int testCount = 0;
            timer.Tick += (s, e) =>
            {
                if (testCount < 3)
                {
                    Console.WriteLine($"\n[测试] 自动更新测试 #{testCount + 1}");
                    _viewModel.ExhaustTemp += 20;
                    _viewModel.TurboASpeed += 15;
                    _viewModel.TurboBSpeed += 10;
                    testCount++;
                }
                else
                {
                    timer.Stop();
                    Console.WriteLine("[测试] 自动测试完成");
                }
            };

            timer.Start();
        }

        private void ProgressBar_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
        }
        #endregion

        #region 跟随功能开关
        public void ToggleFollow(bool enable)
        {
            _isFollowing = enable;
            this.Topmost = enable;
            if (enable)
            {
                _followTimer.Start();
                Console.WriteLine("[跟随] 已开启跟随+置顶功能");
            }
            else
            {
                _followTimer.Stop();
                Console.WriteLine("[跟随] 已关闭跟随+置顶功能");
            }
        }
        #endregion
    }

    #endregion


    #region 使用示例
    public static class UsageExamples
    {
        public static void ShowExamples()
        {
            Console.WriteLine("\n=== 配置使用示例 ===");

            // 示例1：修改显示名称
            Console.WriteLine("\n1. 修改显示名称示例:");
            Console.WriteLine("   原名称: " + VariableConfig.GetDisplayName(VariableConfig.ExhaustTemp));
            // 在实际代码中，你只需要修改 VariableConfig._displayNames 字典

            // 示例2：添加新变量
            Console.WriteLine("\n2. 添加新变量示例:");
            Console.WriteLine("   调用: VariableConfig.AddVariable(\"OilPressure\", \"机油压力\", " +
                            "new VariableConfig.VariableParam(10, \"MPa\", false), " +
                            "new List<string> {\"oilpressure\", \"机油压力\"})");

            // 示例3：查看UDP映射
            Console.WriteLine("\n3. UDP映射示例:");
            string[] testKeys = { "exhausttemp", "排温", "unknown" };
            foreach (var key in testKeys)
            {
                var varName = VariableConfig.GetVariableFromUdpKey(key);
                if (varName != null)
                {
                    Console.WriteLine($"   UDP键 '{key}' -> 变量 '{varName}' " +
                                    $"-> 显示名称 '{VariableConfig.GetDisplayName(varName)}'");
                }
                else
                {
                    Console.WriteLine($"   UDP键 '{key}' -> 未找到匹配变量");
                }
            }

            Console.WriteLine("\n=== 配置文件位置 ===");
            Console.WriteLine("所有配置都集中在 'VariableConfig' 类的顶部区域");
            Console.WriteLine("只需要修改那里的字典，整个程序都会生效");
        }


    }

    #endregion
}