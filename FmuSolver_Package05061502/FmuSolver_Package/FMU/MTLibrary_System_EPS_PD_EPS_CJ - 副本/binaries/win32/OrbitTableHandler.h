#ifndef _ORBIT_TABLE_HANDLER_H_
#define _ORBIT_TABLE_HANDLER_H_

#include <windows.h>

#ifdef ORBITTABLEHANDLER_EXPORTS
#define ORBITTABLEHANDLER_API __declspec(dllexport)
#else
#define ORBITTABLEHANDLER_API __declspec(dllimport)
#endif

EXTERN_C ORBITTABLEHANDLER_API bool LoadOrbitFile(char* pPath);

EXTERN_C ORBITTABLEHANDLER_API bool GetOrbitRowValue(double dTime, double* value1, double* value2, double* value3, double* value4, double* value5, double* value6, 
	double* value7, double* value8, double* value9, double* value10, double* value11, double* value12, double* value13, double* value14, double* value15, double* value16,
	double* value17, double* value18, double* value19, double* value20, double* value21, double* value22, double* value23);

#endif