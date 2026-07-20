# FmuSolver Codex Handoff - Field Stability And Telemetry

Reactivation prompt:

```text
We are continuing from this handoff. Read C:\Spaceship\FMUSOLVER\docs\codex-handoffs\2026-07-17-fmusolver-field-stability.md first, inspect the current repo state, verify what still applies, and continue from the next steps without assuming the old chat context is available.
```

## Repo And Branch

- Repo path: `C:\Spaceship\FMUSOLVER`
- Branch: `master`
- Current known working tree at handoff time: `FmuSolver_Package/yaocetest/ParamFilter.xml` is modified and not committed.
- Important note: the user often tests packaged files under `FmuSolver_Package`, not only source files under `Script`. Keep runtime/package copies synchronized when behavior changes.

## Current Goal

Make FmuSolver stable enough for real field operation for at least one full day while running FMU real-time simulation, PE variable injection, telemetry receive/forward/injection, and the DataVisualizer dashboard. The user prioritizes no crashes, no long-term UI lockup, correct telemetry parsing/mapping, and reliable PE protobuf forwarding over UI polish.

## Completed Work And Decisions

- DataVisualizer previously received fixes for theme following, no default Main Plot, plot layout/preset memory, relative plot sizing, Word export, middle-mouse panning, cumulative trend mode, realtime/cumulative rendering optimization, and memory/performance guards.
- FMU launcher previously received UI/log throttling, collapsible log panels, version display, glass/frameless theme work, process cleanup improvements, pause/resume controls, and worker-process based execution.
- Orbit prediction treats time input as Beijing time and orbital element fields as UI-provided values. Angular fields are labeled `deg` and passed to the FMU unchanged. There is no software-side degree/radian conversion.
- Telemetry runtime was consolidated around the `yaocetest` directory. Packaged `YaoCe_LinkLayer32.exe` and `YaoCe_LinkLayer64.exe` had been rebuilt multiple times in previous work.
- `DTS.TM.Sim.Relationship.xml` is the authoritative telemetry code to `sim_var` mapping for dashboard/PE/FMU forwarding.
- Relationship-mapped telemetry can be forwarded even if `ParamFilter.xml` misses the code.
- Unmapped raw telemetry is intentionally not forwarded to dashboard/PE/FMU to avoid random/raw fields polluting streams or causing unsafe injections.
- Numeric parser behavior: decimal strings parse normally; short hex-like values such as `0A` parse as decimal `10`; placeholders such as `AAAA`, `AA55`, `AAAAAAAA`, and `FFFFFFFF` are ignored instead of becoming `0`.
- Suffix collision issue was fixed so values such as `R1190` do not accidentally map to `B1190` and cause cabin-temperature jumps.
- Time telemetry: `A024~A028` are absolute-time components and can generate `d_MT_Online`, `h_MT_Online`, `m_MT_Online`, `s_MT_Online`, `ms_MT_Online`, and `relativetime_MT_Online`.
- Beijing-time telemetry fields `A029~A02E` are recognized by code, but need explicit `sim_var` mappings in `DTS.TM.Sim.Relationship.xml` if they should appear in dashboard/PE streams.
- External PE/YC injection variables are rate-limited and merged into FMU worker handling. Continuous `PE.` and `YC.` variables follow the main sampling/injection frequency strategy.
- Shelter-ratio related injections are clamped to `0~1` for FMU safety. General external injection values should preserve received precision as much as possible.
- Current PE forwarding design: telemetry launched from the main UI sets `FMUSOLVER_MERGE_TELEMETRY_VIA_WORKER=1`, so telemetry first goes to the FMU Worker and is merged with simulation output before PE forwarding.

## Important Files

- `Script/FmuLauncherUniversal.py`: main UI, process launch, telemetry worker environment, PE/manual injection listener, log panels, runtime controls.
- `FmuSolver_Package/FmuLauncherUniversal.py`: packaged copy of main UI logic.
- `Script/fmu_player.py`: FMU worker, realtime loop, PE/YC injection application, PE/dashboard protobuf sending, telemetry merge cache, performance logs.
- `FmuSolver_Package/fmu_player.py`: packaged copy of FMU worker.
- `Script/DataVisualizerPython.py`: dashboard, plot rendering, presets/layout/memory, Word export, runtime variable handling.
- `FmuSolver_Package/Visualizer/DataVisualizer64.exe`: packaged visualizer executable used in field tests.
- `Script/yaocetest/main.py`: telemetry receive, parse, protobuf generation, direct/local forwarding, perf logs.
- `Script/yaocetest/config_manager.py`: telemetry config loading, filter/mapping, target selection, relationship mapping.
- `Script/yaocetest/DTS.TM.Sim.Relationship.xml`: telemetry code to `sim_var` mapping.
- `Script/yaocetest/ParamFilter.xml`: telemetry filter codes.
- `FmuSolver_Package/yaocetest/*`: packaged runtime copies. Keep these aligned with `Script/yaocetest/*` before packaging.
- `Script/orbit_pre_runner.py`: offline orbit prediction worker.
- `FmuSolver software function and logic documentation` markdown at repo root: user-facing documentation that was previously requested to keep improving.

## Commands And Checks Already Run Recently

- Installed `keep-codex-fast` skill into the user's Codex skills directory.
- Ran read-only Codex state report with `keep_codex_fast.py`.
- Report summary: active thread rows `21`, old session candidates `16`, sessions `0.145GB`, worktrees `0.833GB`, logs `90.8MB`, thread metadata repair candidates `8`.
- Checked repo status: branch `master`, with `FmuSolver_Package/yaocetest/ParamFilter.xml` modified.
- Inspected orbit unit flow in `Script/FmuLauncherUniversal.py` and `Script/orbit_pre_runner.py`; confirmed no degree/radian conversion.
- Inspected telemetry time handling in `Script/yaocetest/main.py`, `config_manager.py`, `DTS.TM.PROTOBUF.xml`, and `DTS.TM.Sim.Relationship.xml`; confirmed `A024~A028` are mapped and `A029~A02E` need relationship mappings for output.
- Inspected PE forwarding logic in `Script/fmu_player.py` and telemetry forwarding in `Script/yaocetest/main.py`; found worker PE send path chunks by variable count `chunk_size=200`, not by serialized UDP byte size.

## Known Issues And Risks

- PE may fail to receive telemetry/simulation data when data volume is large. Current worker path splits PE packets by up to `200` variables per protobuf packet, but not by actual serialized byte size. Large variable names or many values can still exceed safe UDP payload sizes after base64 encoding and trigger IP fragmentation/loss.
- Direct telemetry worker forwarding can serialize one telemetry protobuf per incoming packet without byte-size chunking if `FMUSOLVER_MERGE_TELEMETRY_VIA_WORKER` is not active or the worker is run outside the main launcher.
- Main Codex chat history is large; future work should rely on this handoff and fresh repo inspection instead of old chat memory.
- `FmuSolver_Package/yaocetest/ParamFilter.xml` is modified. Inspect diff before committing or discarding. Do not revert without confirming whether it contains user-added telemetry variables.
- Field reports include long-running UI stutter and eventual freeze even when CPU/memory look normal. Suspected areas include UI log rendering, UDP/protobuf packet volume, telemetry injection frequency, and FMU model sensitivity to injected values.
- FMU crashes with `fmi2DoStep status 3` or Windows `0xe06d7363` were observed before. Some likely came from unsafe injected values or model-specific constraints, not only software threading.
- No current evidence of multiple threads calling the same FMU instance concurrently. FMU worker queues external commands and applies them in the simulation loop.

## User Preferences And Constraints

- User wants concise, direct status when asking whether requirements are solved.
- User prefers testing scripts directly during debugging; package only when explicitly requested.
- When packaging, update the visible top-left version number on every rebuild.
- Stability beats completeness: if in conflict, prevent crashes and keep data flowing.
- Do not auto-delete or revert user changes. The repo may contain user edits.
- User usually writes operational requests in Chinese; respond in Chinese unless there is a reason not to.
- Field testing may be offline/customer-site, so logs must be useful without internet.
- PE only accepts protobuf on its receiving side.
- PE may only receive on one UDP port. Do not assume multi-port receive is available unless the PE team confirms.

## Recommended Next Steps

1. Inspect `git diff -- FmuSolver_Package/yaocetest/ParamFilter.xml` and decide whether the package-only change should be copied back to `Script/yaocetest/ParamFilter.xml` or committed as package data.
2. Fix PE UDP forwarding to chunk by actual encoded byte size, not variable count. Target safe payload size around `1000~1200` bytes after base64, or make it configurable.
3. Apply the same safe chunking to both worker merged PE sending (`fmu_player.py`) and telemetry direct forwarding (`yaocetest/main.py`) so behavior is safe even when launched independently.
4. Add PE send diagnostics: packet count, vars per packet, raw protobuf bytes, base64 bytes, send errors, and max packet size. Include these in worker/perf logs.
5. Consider optional frame/chunk metadata only if PE can support it. If PE cannot support chunk metadata, maintain one UDP port and multiple independent protobuf packets.
6. If Beijing time should appear in dashboard/PE, add explicit relationship mappings for `A029~A02E` to `DTS.TM.Sim.Relationship.xml` and sync package/source copies.
7. Before any major Codex archive/cleanup, confirm this handoff is committed or otherwise preserved, then use `keep-codex-fast` apply only after Codex is closed.

## Suggested PE UDP Fix Direction

- Replace fixed `chunk_size=200` with a helper that builds protobuf chunks under a configurable byte budget.
- Estimate by trying to add a variable, serializing, base64 encoding, and flushing the current packet if adding the variable would exceed the byte budget.
- Keep packet order stable.
- Log max observed packet size and packets per simulation sample.
- Default to conservative LAN-safe UDP payload. A good first value is `FMUSOLVER_PE_UDP_MAX_BYTES=1200` for encoded payload bytes.
- Avoid adding multi-port PE output as the first fix. One-port multi-packet protobuf is simpler and better aligned with PE constraints.

## Do Not Touch Without Care

- Do not blindly remove large package zips/rar files unless user explicitly asks for workspace cleanup.
- Do not revert `FmuSolver_Package/yaocetest/ParamFilter.xml` without checking whether it contains field-added variables.
- Do not change telemetry filtering back to forwarding unmapped raw variables; that previously caused confusing dashboard variables and possible unsafe injections.
- Do not reintroduce automatic degree-to-radian conversion for orbit six-root inputs; user explicitly requested original logic/no conversion.
- Do not make recurring Codex maintenance mutate state automatically; reminders should be report-only.
