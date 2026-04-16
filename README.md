# FMUSolver

FMU (Functional Mock-up Unit) 求解器项目，用于卫星轨道仿真和能源系统建模。

## 项目结构

```
├── Script/           # 源代码脚本
│   ├── fmu_player.py      # FMU播放器核心逻辑
│   ├── fmu_controller.py  # FMU控制器
│   ├── patch_launcher.py  # 启动器补丁
│   └── ...
├── FmuSolver_Package/ # 打包后的可执行文件
│   ├── FmuSolver.exe      # 主求解器
│   ├── FmuWorker32.exe    # 32位工作进程
│   ├── FmuWorker64.exe    # 64位工作进程
│   └── ...
└── README.md          # 项目说明
```

## 功能特性

- FMU 模型加载和执行
- 卫星轨道仿真
- 能源系统建模
- UDP 数据通信

## 快速开始

运行打包后的可执行文件：

```bash
./FmuSolver_Package/FmuSolver.exe
```

## 开发

使用 Python 开发，主要依赖：
- Python 3.x
- protobuf
- base64

## 许可证

MIT License