# FMUSolver — FMU Co-Simulation Runner for Industrial Digital Twins

> Python platform that **loads FMI 2.0 FMUs**, runs real-time co-simulation, bridges telemetry into model inputs, and streams variables to 3D viewers / dashboards. Built for industrial energy & orbit-class models (generic capability — not a single customer build).

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python)](#)
[![FMI](https://img.shields.io/badge/FMI-2.0%20FMU-orange)](#)
[![Protobuf](https://img.shields.io/badge/UDP-Protobuf-blue)](#)

## Why it exists

Industrial FMUs often ship as **32-bit or 64-bit DLLs** with tens of thousands of variables. A single Python process cannot load both bitnesses. FMUSolver solves that with a **sidecar architecture**: a 64-bit GUI orchestrator + auto-selected 32/64-bit worker processes.

As core developer I shipped ~**30K lines** of Python (GUI, workers, telemetry bridge, orbit pre-calc, packaging) across multiple releases in ~2 months.

## Capabilities

- Load & step standard **FMI 2.0** FMUs (`fmpy`-style race)
- Real-time controls: start / pause / resume / stop, hot parameter inject
- **Orbit / energy-class offline pre-calc** worker (seed file → propagate → export)
- **UDP + Protobuf** fan-out of selected variables to 3D viz or local dashboards
- Telemetry bridge: binary packet parse → fuzzy ID map → FMU inputs (config-driven)
- Live multi-plot dashboard with down-sampling for long runs; Word export path
- PyInstaller one-file packaging (`FmuSolver.exe`, `FmuWorker32/64`, orbit & telemetry tools)

## Architecture

```
FmuSolver.exe (64-bit GUI / orchestrator)
   │  detects FMU bitness
   ├─► FmuWorker32.exe  ─┐
   └─► FmuWorker64.exe  ─┴─ FMI doStep + DLL load
                              │
                              ▼  UDP / Protobuf
                     3D viewer · DataVisualizer · peers

Optional: OrbitPreCalc*  ·  YaoCe telemetry link layer
```

## Tech stack

| Piece | Tech |
|-------|------|
| Language | Python 3.x (dual 32/64 toolchains) |
| Sim standard | FMI 2.0 / FMU |
| IPC / net | STDOUT logs, UDP, Protobuf (`ddm.proto`) |
| GUI | Tkinter-themed launcher + .NET visualizer package |
| Ship | PyInstaller one-file |

## Repo layout

```
FmuSolver_Package/   # Packaged runners, workers, visualizer, configs
Script/              # (when present) Python sources
FMUcontent.md        # Deploy / architecture notes
```

## Role

**Core developer** — architecture (sidecar), simulation control, telemetry mapping, packaging & field diagnostics.

---

*Industrial / aerospace-adjacent energy & orbit co-simulation capability. FMU 协同仿真运行器 — 工业能源 / 轨道类模型通用联调。*
