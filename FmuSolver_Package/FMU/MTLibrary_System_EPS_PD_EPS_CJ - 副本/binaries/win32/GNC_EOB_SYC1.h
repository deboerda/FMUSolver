#pragma once

#include <Windows.h>

#ifdef GNC_EOB_SYC1_EXPORTS
#define GNC_EOB_SYC1_API __declspec(dllexport)
#else
#define GNC_EOB_SYC1_API __declspec(dllimport)
#endif

//nStep:		步长，单位ms
//nPhase:		0-消初偏，1-寻的段，2-接近段，4-平移靠拢段
//nInitFlag:	由外部参数初始化时置1，自测试时置0
EXTERN_C GNC_EOB_SYC1_API void TY_KJZ_GNC_Dll_Init(int nStep, int nPhase, int nInitFlag);

EXTERN_C GNC_EOB_SYC1_API void TY_KJZ_GNC_Dll_Stop();

//输入参数
//sim_time：				仿真累计时间，0时刻开始
//BJT0_year：				仿真累计时间0时刻对应的北京时，年
//BJT0_month：				仿真累计时间0时刻对应的北京时，月
//BJT0_day：				仿真累计时间0时刻对应的北京时，日
//BJT0_hour：				仿真累计时间0时刻对应的北京时，时
//BJT0_minute：				仿真累计时间0时刻对应的北京时，分
//BJT0_second：				仿真累计时间0时刻对应的北京时，秒
//TH_Qbi：					长度为4的数组，表示从J2000惯性系到[核心舱]本体控制坐标系的四元数，其中第四个量Qbi[3]为标量部分
//WT_Qbi：					长度为4的数组，表示从J2000惯性系到[实验舱I]本体控制坐标系的四元数，其中第四个量Qbi[3]为标量部分
//XT_Qbi：					长度为4的数组，表示从J2000惯性系到[实验舱II]本体控制坐标系的四元数，其中第四个量Qbi[3]为标量部分
//HY_Qbi：					长度为4的数组，表示从J2000惯性系到[货船]本体控制坐标系的四元数，其中第四个量Qbi[3]为标量部分
//TH_Wbi：					长度为3的数组，表示[核心舱]本体控制坐标系相对于J2000惯性系的角速度在其本体控制坐标系下的值，单位rad/s
//WT_Wbi：					长度为3的数组，表示[实验舱I]本体控制坐标系相对于J2000惯性系的角速度在其本体控制坐标系下的值，单位rad/s
//XT_Wbi：					长度为3的数组，表示[实验舱II]本体控制坐标系相对于J2000惯性系的角速度在其本体控制坐标系下的值，单位rad/s
//HY_Wbi：					长度为3的数组，表示[货船]本体控制坐标系相对于J2000惯性系的角速度在其本体控制坐标系下的值，单位rad/s
//TH_panel_alpha:			长度为2的数组，表示核心舱左右帆板转角，先II象限帆板，再IV象限帆板（帆板相关的数组中，都采用此顺序），单位rad
//WT_panel_alpha:			长度为2的数组，实验舱I左右帆板alpha转角，先II象限帆板，再IV象限帆板（帆板相关的数组中，都采用此顺序），单位rad
//WT_panel_beta:			长度为2的数组，实验舱I左右帆板beta转角，先II象限帆板，再IV象限帆板（帆板相关的数组中，都采用此顺序），单位rad 
//XT_panel_alpha:			实验舱II左右帆板alpha转角，先II象限帆板，再IV象限帆板（帆板相关的数组中，都采用此顺序），单位rad
//XT_panel_beta:			实验舱II左右帆板beta转角，先II象限帆板，再IV象限帆板（帆板相关的数组中，都采用此顺序），单位rad
//TH_panel_state：			长度为2的数组，核心舱左右帆板归零状态，0：表示未归零， 1表示水平归零，2表示垂直归零
//WT_panel_alpha_state：	实验舱I的alpha帆板定位状态
//WT_panel_alpha_state1：	实验舱I的alpha帆板启停状态
//WT_panel_beta_state：		长度为2的数组，实验舱I左右帆板归零状态，0：表示未归零， 1表示水平归零，2表示垂直归零
//XT_panel_alpha_state：	实验舱II的alpha帆板定位状态
//XT_panel_alpha_state1：	实验舱II的alpha帆板启停状态
//XT_panel_beta_state：		长度为2的数组，实验舱II左右帆板归零状态，0：表示未归零， 1表示水平归零，2表示垂直归零
//TH_panel_unfold:			长度为2的数组，核心舱帆板展开标志，0：未展开，1：展开
//WT_panel_unfold:			长度为2的数组，实验舱I帆板展开标志，0：未展开，1：展开
//XT_panel_unfold:			长度为2的数组，实验舱II帆板展开标志，0：未展开，1：展开
//orb_a:					舱段轨道半长轴，单位km
//orb_e:					舱段轨道偏心率
//orb_i:					舱段轨道倾角，单位rad
//orb_Omg:					舱段升交点赤经，单位(rad)
//orb_w:					舱段近地点幅角，单位(rad)
//orb_f:					舱段真近点角，单位(rad)
//TH_accer_F：				长度为3的数组，核心舱受到的除引力外的外力产生的加速度在轨道坐标系下的坐标，单位（m/s^2）
//WT_accer_F：				长度为3的数组，实验舱I受到的除引力外的外力产生的加速度在轨道坐标系下的坐标，单位（m/s^2）
//XT_accer_F：				长度为3的数组，实验舱II受到的除引力外的外力产生的加速度在轨道坐标系下的坐标，单位（m/s^2）
//HY_accer_F：				长度为3的数组，货船受到的除引力外的外力产生的加速度在轨道坐标系下的坐标，单位（m/s）
//TH_So：					长度为3的数组，太阳方向的单位矢量，在轨道坐标系下的坐标
//TH_jet_F：				长度为3的数组，核心舱推力器产生的总的力在其本体控制系下的坐标，单位N
//TH_jet_T：				长度为3的数组，核心舱推力器产生的总的力矩在其本体控制系下的坐标，单位N*m
//WT_jet_F：				长度为3的数组，实验舱I推力器产生的总的力在其本体控制系下的坐标，单位N
//WT_jet_T：				长度为3的数组，实验舱I推力器产生的总的力矩在其本体控制系下的坐标，单位N*m
//XT_jet_F：				长度为3的数组，实验舱II推力器产生的总的力在其本体控制系下的坐标，单位N
//XT_jet_T：				长度为3的数组，实验舱II推力器产生的总的力矩在其本体控制系下的坐标，单位N*m
//HY_jet_F：				长度为3的数组，货运推力器产生的总的力在其本体控制系下的坐标，单位N
//HY_jet_T：				长度为3的数组，货运推力器产生的总的力矩在其本体控制系下的坐标，单位N*m
//TH_CMD:					接收核心舱数管分系统发送的指令的整形参数，1-转位开始，2-停控，3-切至下一构型
//							31-核心舱帆板固定角度伺服
//							43-核心舱帆板水平归零
//							53-核心舱帆板停转
//							55-核心舱帆板捕获太阳
//							57-核心舱帆板垂直归零
//WT_CMD：					接收实验舱I数管分系统发送的指令的整形参数，n根据需要设定
//							21-实验舱I帆板alpha轴固定角度伺服
//							23 实验舱I帆板alpha轴水平归零
//							25 实验舱I帆板alpha轴停转
//							27 实验舱I帆板alpha轴捕获太阳
//							29 实验舱I帆板alpha轴垂直归零
//							33 实验舱I帆板beta轴固定角度伺服
//							35 实验舱I帆板beta轴水平归零
//							37 实验舱I帆板beta轴停转
//							39 实验舱I帆板beta轴捕获太阳
//							41 实验舱I帆板beta轴垂直归零
//							100 实验舱I 2A发动机开，不是100时，2A发动机关
//XT_CMD：					接收实验舱II数管分系统发送的指令的整形参数，n根据需要设定
//							22_实验舱II帆板alpha轴固定角度伺服
//							24 实验舱II帆板alpha轴水平归零
//							26 实验舱II帆板alpha轴停转
//							28 实验舱II帆板alpha轴捕获太阳
//							30 实验舱II帆板alpha轴垂直归零
//							34 实验舱II帆板beta轴固定角度伺服
//							36 实验舱II帆板beta轴水平归零
//							38 实验舱II帆板beta轴停转
//							40 实验舱II帆板beta轴捕获太阳
//							42 实验舱II帆板beta轴垂直归零
//							100 实验舱II 2A发动机开，不是100时，2A发动机关
//TH01Pos：					长度为3的数组，核心舱目标器J2000位置(米)
//TH01Vel：					长度为3的数组，核心舱目标器J2000速度(米/秒)
//WTOrbitTime：				长度为6的数组，当前时间(BJT)
//SYCPos：					长度为3的数组，追踪器J2000位置(米)
//SYCVel：					长度为3的数组，追踪器J2000速度(米/秒)
//SYCbZhuRu：				追踪器注入数据标志
//SYCZhuRu：				追踪器注入数据
//ChStatusMark:				长度为10的数组，
//ChFault：	
//输出参数//////////////////////////////////////////////////////////////////////////////////////////////////////
//TH_jet_time：				长度为26的数组，核心舱发动机开机时间指令，单位s，更新周期200ms
//WT_jet_time：				长度为36的数组，实验舱I发动机开机时间指令，单位s，更新周期200ms
//XT_jet_time：				长度为36的数组，实验舱II发动机开机时间指令，单位s，更新周期200ms
//TZ_jet_time：				长度为36的数组，货运发动机开机时间指令，单位s，更新周期200ms
//TH_panel_omg：			长度为2的数组，核心舱帆板转速指令，顺序为II象限帆板，IV象限帆板，单位rad/s, 更新周期200ms
//WT_panel_omg：			长度为4的数组，实验舱I帆板转速指令，顺序为II象限帆板alpha转角转速，II象限帆板beta转角转速，IV象限帆板alpha转角转速，IV象限帆板beta转角转速，单位rad/s, 更新周期200ms
//XT_panel_omg：			长度为4的数组，实验舱II帆板转速指令，顺序为II象限帆板alpha转角转速，II象限帆板beta转角转速，IV象限帆板alpha转角转速，IV象限帆板beta转角转速，单位rad/s, 更新周期200ms
//WT_panel_mode:			长度为2的数组，实验舱I帆板alpha机构控制方式，更新周期200ms
//							1-正向角度伺服， -1-反向角度伺服
//							2-正向捕获，     -2-反向捕获
//							3-正向水平归零， -3-反向水平归零
//							4-正向垂直归零， -4-反向垂直归零
//							5-停转,			 -5-停转
//							其他，跟踪
//WT_panel_mode2[2]:		长度为2的数组，实验舱I帆板beta机构控制方式，数值含义同上，更新周期200ms
//XT_panel_mode[2]:			长度为2的数组，实验舱II帆板alpha机构控制方式，数值含义同上，更新周期200ms
//XT_panel_mode2[2]:		长度为2的数组，实验舱II帆板beta机构控制方式，数值含义同上，更新周期200ms
//phi:						滚动姿态角，单位度，按照通信协议，发送给机械臂分系统的数据，更新周期200ms
//theta:					俯仰姿态角，单位度，按照通信协议，发送给机械臂分系统的数据，更新周期200ms
//psi:						偏航姿态角，单位度，按照通信协议，发送给机械臂分系统的数据，更新周期200ms
//dphi:						滚动姿态角速度，单位度/秒，按照通信协议，发送给机械臂分系统的数据，更新周期200ms
//dtheta:					俯仰姿态角速度，单位度/秒，按照通信协议，发送给机械臂分系统的数据，更新周期200ms
//dpsi:						偏航姿态角速度，单位度/秒，按照通信协议，发送给机械臂分系统的数据，更新周期200ms
//P1：						控制器一级段标，更新周期200ms
//P2：						控制器二级段标，更新周期200ms
//P3：						控制器三级段标，更新周期200ms
//TH_qbi：					长度为4的数组，核心舱控制器估计的本体相对惯性系四元数
//TH_wbi：					长度为3的数组，核心舱控制器估计的本体相对惯性系角速度
//WT_qbi：					长度为4的数组，从J2000惯性系到实验舱I本体控制坐标系的四元数，其中第四个量Qbi[3]为标量部分
//WT_wbi：					长度为3的数组，实验舱I本体控制坐标系相对于J2000惯性系的角速度在其本体控制坐标系下的值，单位rad/s
//TH_CMG_H：				长度为3的数组，核心舱CMG的合成角动量在其本体控制坐标系下的分量，单位Nms,更新周期10ms
//TH_CMG_T：				长度为3的数组，核心舱CMG产生的力矩，在其本体控制坐标系下的分量，单位Nm,更新周期10ms
//WT_CMG_H：				长度为3的数组，实验舱ICMG的合成角动量在其本体控制坐标系下的分量，单位Nms,更新周期10ms
//WT_CMG_T：				长度为3的数组，实验舱ICMG产生的力矩，在其本体控制坐标系下的分量，单位Nm,更新周期10ms
//TH01JianShi：				长度为12000的数组，核心舱遥测和监视
//chaser_OrbAtt：			飞船轨道系姿态
//target_rvd_relposvel：	相对位置在目标器RVD系下的表示
//target_dock_relposvel：	
//WTJetTime：				货船发动机喷气脉宽
//SuccessOrFail：
//PFlag：					长度为12000的数组
//Flg_RGPSfilter：
//Flg_WRfilter：
//Flg_LRfilter：
//Flg_CCDfilter：
//ExpendFuel：
//WTJianShi：				长度为12000的数组，实验舱I遥测和监视
EXTERN_C GNC_EOB_SYC1_API void TY_KJZ_GNC_Dll_Solve(
	//输入
	double sim_time, int BJT0_year, int BJT0_month, int BJT0_day, int BJT0_hour, int BJT0_minute, double BJT0_second,
	double* TH_Qbi, double* WT_Qbi, double* XT_Qbi, double* HY_Qbi,
	double* TH_Wbi, double* WT_Wbi, double* XT_Wbi, double* HY_Wbi,
	double* TH_panel_alpha, double* WT_panel_alpha, double* WT_panel_beta, double* XT_panel_alpha, double* XT_panel_beta,
	int* TH_panel_state, int WT_panel_alpha_state, int WT_panel_alpha_state1, int* WT_panel_beta_state, int XT_panel_alpha_state, int XT_panel_alpha_state1, int* XT_panel_beta_state,
	int* TH_panel_unfold, int* WT_panel_unfold, int* XT_panel_unfold,
	double orb_a, double orb_e, double orb_i, double orb_Omg, double orb_w, double orb_f,
	double* TH_accer_F, double* WT_accer_F, double* XT_accer_F, double* HY_accer_F, double* TH_So,
	double* TH_jet_F, double* TH_jet_T, double* WT_jet_F, double* WT_jet_T, double* XT_jet_F, double* XT_jet_T, double* HY_jet_F, double* HY_jet_T,
	int TH_CMD, int WT_CMD, int XT_CMD,
	double* TH01Pos, double* TH01Vel,
	double* WTOrbitTime, double* SYCPos, double* SYCVel, bool SYCbZhuRu, char* SYCZhuRu, double SYCMass,
	int* ChStatusMark, int ChFault,
	//输出
	double* TH_jet_time, double* WT_jet_time, double* XT_jet_time, double* TZ_jet_time,
	double* TH_panel_omg, double* WT_panel_omg, double* XT_panel_omg,
	double* TH_panel_mode, double* WT_panel_mode, double* WT_panel_mode2, double* XT_panel_mode, double* XT_panel_mode2,
	double* phi, double* theta, double* psi, double* dphi, double* dtheta, double* dpsi, int* P1, int* P2, int* P3,
	double* TH_qbi, double* TH_wbi, double* WT_qbi, double* WT_wbi,
	double* TH_CMG_H, double* TH_CMG_T, double* WT_CMG_H, double* WT_CMG_T/*, char* TH01JianShi*/,
	double* chaser_OrbAtt, double* target_rvd_relposvel, double* target_dock_relposvel, double* WTJetTime,
	int* SuccessOrFail, int* PFlag, int* Flg_RGPSfilter, int* Flg_WRfilter, int* Flg_LRfilter, int* Flg_CCDfilter/*, double* ExpendFuel*/, char* WTJianShi
	);

EXTERN_C GNC_EOB_SYC1_API void TY_KJZ_GNC_Dll_Inject(char* injecttable);