#pragma once
//***************************************************************************************************************************************
//计算太阳翼遮挡率和太阳入射角
/// @Author	Chen Huikang
/// @Date	2022.8.4
///	@Input
/// @Param	BJTime[6]		北京时间{年, 月, 日, 时, 分, 秒}
///	@Param	OrbElem[6]		轨道六根数{轨道半长轴(km), 轨道偏心率, 轨道倾角(rad), 升交点赤经(rad), 近地点幅角(rad), 真近点角(rad)}
/// @Param	SunPos[6]		J2000惯性坐标系和体坐标系的太阳位置矢量{x_J2000,y_J2000,z_J2000, x_body, y_body, z_body}(单位km)
/// @Param	RotateAngle[2]	两块太阳翼的旋转角{左侧太阳翼a旋转角(rad)，右侧太阳翼b旋转角(rad)} 
/// @Output
/// @Param	ShelterRatioA	太阳翼a遮挡率
/// @Param	ShelterRatioB	太阳翼b遮挡率
/// @Param	SolarAngleA		太阳翼a太阳入射角(rad)
/// @Param	SolarAngleB		太阳翼b太阳入射角(rad)
//***************************************************************************************************************************************
void CalculateSolarPanelShelterRatio(const double BJTime[], const double OrbElem[], const double SunPos[], const double RotateAngle[], 
	double &ShelterRatioA, double &ShelterRatioB, double &SolarAngleA, double &SolarAngleB);