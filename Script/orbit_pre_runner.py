"""
orbit_pre_runner.py  –  32-bit offline orbit pre-calculation engine.

ARCHITECTURE (confirmed by full diagnostic series):
  - FMU reads initial orbit conditions from a seed Orbit_Pre.txt (1 row minimum).
  - FMU propagates forward and provides output via variable interface.
  - 'filepath' parameter is where FMU reads the seed AND writes output.
  - Year must match the FMU's EOP file coverage (2026+, based on EOP240404.txt).
  - Mon, Day, Hour, Min, Sec and all 6 orbital elements are freely settable.
  - We generate the seed file from user's date (year forced=2026) + orbital elements.
"""
import os
import sys

# ── 强制重定向临时目录到程序所在本地目录，避免撑爆 C 盘 ──
# 优先获取 EXE 所在目录，如果是源码运行则获取脚本所在目录
_base_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
_local_temp = os.path.join(_base_dir, "temp_cache")
os.makedirs(_local_temp, exist_ok=True)
os.environ['TEMP'] = _local_temp
os.environ['TMP'] = _local_temp
# ────────────────────────────────────────────────────────

import json
import time
import math
import zipfile
import shutil
import tempfile
import uuid
import fmpy
from fmpy import instantiate_fmu, read_model_description


def log(msg):
    print(msg, flush=True)


def _path_is_safe(path):
    """Check if a path is safe for legacy C++ file I/O (ASCII-only, no spaces, no parens)."""
    import re
    return bool(re.match(r'^[A-Za-z]:\\[A-Za-z0-9_\\]*$', path))


def get_safe_windows_path(path):
    norm_path = os.path.normpath(path)
    if os.name != 'nt' or not os.path.exists(norm_path):
        return norm_path

    try:
        import ctypes
        buffer_size = 4096
        output = ctypes.create_unicode_buffer(buffer_size)
        result = ctypes.windll.kernel32.GetShortPathNameW(norm_path, output, buffer_size)
        if result and output.value != norm_path:
            # Short path successfully obtained and is different from long path
            return output.value
    except Exception:
        pass

    return norm_path


def get_guaranteed_safe_workspace(app_dir):
    """
    Returns a workspace root on C drive to avoid instability on non-system drives.
    """
    base_temp = "C:\\FmuSolver_Runtime"
    try:
        if not os.path.exists(base_temp):
            os.makedirs(base_temp, exist_ok=True)
            
        # 尝试清理旧残留
        import shutil
        for item in os.listdir(base_temp):
            if item.startswith("job_"):
                item_path = os.path.join(base_temp, item)
                try: shutil.rmtree(item_path)
                except: pass
    except:
        pass

    return base_temp


def get_vr(model_desc, name):
    for v in model_desc.modelVariables:
        if v.name == name:
            return v.valueReference
    raise KeyError(f"Variable not found: {name}")


def date_to_jd(year, mon, day, hour, minute, sec):
    """Convert calendar date/time to Julian Date."""
    if mon <= 2:
        year -= 1
        mon  += 12
    A  = math.floor(year / 100.0)
    B  = 2 - A + math.floor(A / 4.0)
    jd = (math.floor(365.25 * (year + 4716))
          + math.floor(30.6001 * (mon + 1))
          + day + B - 1524.5
          + hour / 24.0 + minute / 1440.0 + sec / 86400.0)
    return jd


def generate_seed_orbit_txt(path, jd, a, e, i, omega_big, omega_small, f):
    """Write minimal Orbit_Pre.txt seed: 2 rows of initial conditions to prevent interpolator crashes."""
    with open(path, 'w', encoding='ascii') as fp:
        fp.write("#1\n")
        fp.write("double table(2,7)\n")
        # Row 1: Initial epoch
        fp.write(f"{jd:.5f}\t{a:.5f}\t{e:.5f}\t{i:.5f}\t"
                 f"{omega_big:.5f}\t{omega_small:.5f}\t{f:.5f}\n")
        # Row 2: JD + 1 to satisfy algorithms requiring >= 2 points
        fp.write(f"{jd+1.0:.5f}\t{a:.5f}\t{e:.5f}\t{i:.5f}\t"
                 f"{omega_big:.5f}\t{omega_small:.5f}\t{f:.5f}\n")
    log(f"[OK] Seed file: JD={jd:.5f} (2 rows generated)")


def check_dll_arch(filepath):
    try:
        import struct
        with open(filepath, 'rb') as f:
            dos = f.read(64)
            if dos[:2] != b'MZ': return None
            ofs = struct.unpack('<I', dos[60:64])[0]
            f.seek(ofs + 4)
            m = struct.unpack('<H', f.read(2))[0]
            if m == 0x014c: return "win32"
            if m == 0x8664: return "win64"
    except: pass
    return None


# Valid year for this FMU's EOP data (EOP240404.txt covers ~2026+)
FMU_VALID_YEAR = 2026


if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))

    os.chdir(app_dir)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("fmu_path")
    parser.add_argument("--params",      default="{}")
    parser.add_argument("--stop_time",   type=float, default=86400.0)
    parser.add_argument("--step_size",   type=float, default=10.0)
    parser.add_argument("--sample_freq", type=float, default=0.1)
    parser.add_argument("--sim_rate",    type=float, default=0.0)
    parser.add_argument("--seed_path",   default=None, help="Optional external Orbit_Pre.txt to use as seed")
    parser.add_argument("--pause_file",  default=None, help="Pause while this file exists")
    args = parser.parse_args()

    user_params     = json.loads(args.params)
    output_interval = (1.0 / args.sample_freq) if args.sample_freq > 0 else args.step_size

    # FMU requires step size = multiple of 10s (matches internal integration interval)
    fmu_step = args.step_size
    if fmu_step < 10.0 or abs(round(fmu_step / 10.0) * 10.0 - fmu_step) > 1e-6:
        fmu_step = max(10.0, round(fmu_step / 10.0) * 10.0)
        log(f"[!] Step snapped to {fmu_step}s (FMU requires multiples of 10s)")

    stop_time = max(fmu_step, round(args.stop_time / fmu_step) * fmu_step)

    log(f"[*] app_dir = {app_dir}")
    log(f"[*] fmu     = {os.path.basename(args.fmu_path)}")
    log(f"[*] Step={fmu_step}s | Freq={args.sample_freq}Hz | "
        f"Interval={output_interval:.3f}s | Duration={stop_time}s | Rate={args.sim_rate}x")

    # ─── Extract user params ───
    user_year  = int(user_params.get('Year', FMU_VALID_YEAR))
    mon        = int(user_params.get('Mon',  3))
    day        = int(user_params.get('Day',  31))
    hour       = int(user_params.get('Hour', 12))
    minute     = int(user_params.get('Min',  0))
    sec        = float(user_params.get('Sec', 0.0))
    a_mt       = float(user_params.get('a_MT',     6766.71777))
    e_mt       = float(user_params.get('e_MT',     0.00110))
    i_mt       = float(user_params.get('i_MT',     0.72653))
    omega_mt   = float(user_params.get('OMEGA_MT', 2.39969))
    omega_s_mt = float(user_params.get('omega_MT', 1.34409))
    f_mt       = float(user_params.get('f_MT',     1.00447))

    # Year must match FMU's EOP data range
    eff_year = FMU_VALID_YEAR
    if user_year != FMU_VALID_YEAR:
        log(f"[!] Requested Year={user_year}. FMU EOP data covers {FMU_VALID_YEAR}+.")
        log(f"[!] Forcing Year={FMU_VALID_YEAR}. Mon/Day/Hour/Min/Sec retained.")

    jd_seed = date_to_jd(eff_year, mon, day, hour, minute, sec)
    log(f"[*] Epoch: {eff_year}-{mon:02d}-{day:02d} {hour:02d}:{minute:02d}:{sec:.1f}"
        f" → JD={jd_seed:.5f}")

    # ─── 1. Extract FMU ───
    # get_guaranteed_safe_workspace() handles:
    #   - Chinese/special chars in user profile (e.g. C:\Users\木木)
    #   - Spaces/parentheses in paths (e.g. Program Files (x86))
    #   - Systems with 8.3 short names disabled (enterprise/corporate PCs)
    workspace_root = get_guaranteed_safe_workspace(app_dir)

    # Create a unique per-run job directory within the safe workspace
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    extract_dir = os.path.join(workspace_root, job_id)
    os.makedirs(extract_dir, exist_ok=True)
    log(f"[*] Runtime workspace = {extract_dir}")
    log("[*] Extracting FMU...")
    with zipfile.ZipFile(args.fmu_path, 'r') as z:
        z.extractall(extract_dir)

    # ─── 2. Patch Environment (Synchronize all data/DLL files) ───
    arch    = "win32"
    bin_dir = os.path.join(extract_dir, "binaries", arch)
    os.makedirs(bin_dir, exist_ok=True)

    protected = {'kernel32.dll', 'user32.dll', 'ntdll.dll', 'advapi32.dll'}
    log(f"[*] Synchronizing dependencies from {app_dir}...")
    for fname in os.listdir(app_dir):
        # Synchronize DLLs and critical data files (txt, dat, xml)
        ext = fname.lower().split('.')[-1] if '.' in fname else ''
        if ext in ['dll', 'txt', 'dat', 'xml', 'ini', 'json'] and fname.lower() not in protected:
            src_file = os.path.join(app_dir, fname)
            # Arch check only for DLLs
            if ext == 'dll':
                f_arch = check_dll_arch(src_file)
                if f_arch and f_arch != arch:
                    continue
            
            dst = os.path.join(bin_dir, fname)
            if not os.path.exists(dst):
                shutil.copy2(src_file, dst)
    log("[OK] Environment patched.")

    # ─── 3. Prepare Orbit_Pre.txt seed ───
    seed_path = os.path.join(bin_dir, "Orbit_Pre.txt")
    if args.seed_path and os.path.exists(args.seed_path):
        log(f"[*] Using external seed file: {args.seed_path}")
        shutil.copy2(args.seed_path, seed_path)
    else:
        log("[*] Generating seed file from parameters...")
        generate_seed_orbit_txt(seed_path, jd_seed, a_mt, e_mt, i_mt, omega_mt, omega_s_mt, f_mt)

    # ─── 4. DLL paths & CWD ───
    safe_bin_dir = get_safe_windows_path(bin_dir)
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(app_dir)
        os.add_dll_directory(safe_bin_dir)
    os.environ['PATH'] = safe_bin_dir + os.pathsep + app_dir + os.pathsep + os.environ.get('PATH', '')
    os.chdir(safe_bin_dir)
    log(f"[*] CWD = {safe_bin_dir}")

    # ── Pre-load all companion DLLs from bin_dir into process space ──
    import ctypes
    from ctypes import wintypes
    
    # Python 3.8+ requires winmode=0 to search for dependencies in the same directory
    # or we use kernel32.LoadLibraryW to bypass PyInstaller's ctypes hook.
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.LoadLibraryW.argtypes = [wintypes.LPCWSTR]
    kernel32.LoadLibraryW.restype = wintypes.HMODULE

    loaded_ok = []
    load_fail = []
    for fname in sorted(os.listdir(bin_dir)):
        if fname.lower().endswith('.dll') and fname.lower() not in protected:
            fpath = os.path.join(bin_dir, fname)
            try:
                # Try standard ctypes first with winmode=0 (bypasses some restrictions)
                # winmode=0 is for Python 3.8+
                ctypes.CDLL(fpath, winmode=0)
                loaded_ok.append(fname)
            except Exception:
                try:
                    # Fallback to direct Windows API call to bypass PyInstaller hooks
                    h = kernel32.LoadLibraryW(fpath)
                    if h:
                        loaded_ok.append(f"{fname}(API)")
                    else:
                        raise Exception(f"WinError {ctypes.get_last_error()}")
                except Exception as e:
                    load_fail.append(f"{fname}: {e}")
    log(f"[*] Pre-loaded {len(loaded_ok)} DLLs. Failures: {len(load_fail)}")
    for err in load_fail:
        log(f"[!] Pre-load FAIL: {err}")
    # ────────────────────────────────────────────────────────────────

    # Use simple filename for the FMU internal reader (we are already in bin_dir)
    orbit_txt_abs = "Orbit_Pre.txt"

    output_var_names = [
        'uTCG.JD_Out',
        'hPOP.Out_SixRoot[1]', 'hPOP.Out_SixRoot[2]', 'hPOP.Out_SixRoot[3]',
        'hPOP.Out_SixRoot[4]', 'hPOP.Out_SixRoot[5]', 'hPOP.Out_SixRoot[6]',
    ]

    try:
        model_desc = read_model_description(args.fmu_path, validate=False)
        log(f"[OK] Model: {model_desc.modelName}")

        fmu_inst = instantiate_fmu(
            unzipdir=extract_dir,
            model_description=model_desc,
            fmi_type='CoSimulation'
        )
        log("[OK] FMU instantiated.")

        fmu_inst.setupExperiment(startTime=0.0)

        all_vars = list(getattr(model_desc, 'modelVariables', []))
        for v in all_vars:
            t = getattr(v, 'type', 'Real')
            sv = getattr(v, 'start', '') or ''
            if t == 'String' and ('Orbit_Pre' in sv or v.name == 'filepath'):
                log(f"[*] filepath → {orbit_txt_abs}")
                fmu_inst.setString([v.valueReference], [orbit_txt_abs])

        # Set user params with Year forced to valid range
        var_map = {v.name: v for v in model_desc.modelVariables}
        params_to_set = dict(user_params)
        params_to_set['Year'] = float(eff_year)   # Force valid year
        # 新版FMU内部按 endtime/sampletime 写表头行数(endtime/5+1)，
        # 必须与实际仿真时长一致，否则表头行数与实际数据行数不符
        params_to_set.setdefault('endtime', float(stop_time))

        # 关键：必须按变量类型分发 set 调用。
        # 新版MWORKS(26.1.2+)FMU对 Integer 变量(Year/Mon/Day/Hour/Min)调 fmi2SetReal
        # 会报错并把实例置为错误状态，之后连正确类型的调用都会报
        # "invalid execution timing"（enterInitializationMode 可清除该状态）。
        def _set_var(k, val):
            v = var_map[k]
            t = getattr(v, 'type', 'Real')
            if t == 'Integer':
                fmu_inst.setInteger([v.valueReference], [int(round(float(val)))])
            elif t == 'Boolean':
                fmu_inst.setBoolean([v.valueReference], [bool(val)])
            else:
                fmu_inst.setReal([v.valueReference], [float(val)])

        deferred_params = {}
        for k, val in params_to_set.items():
            if k in var_map:
                try:
                    _set_var(k, val)
                    log(f"[*] Set {k} = {val}")
                except Exception:
                    deferred_params[k] = val

        # ─── Initialize ───
        log("[*] enterInitializationMode...")
        fmu_inst.enterInitializationMode()
        if deferred_params:
            # 兜底：个别FMU只在 InitializationMode 内接受设参
            log(f"[*] Retrying {len(deferred_params)} params inside InitializationMode...")
            for k, val in deferred_params.items():
                try:
                    _set_var(k, val)
                    log(f"[*] Set {k} = {val} (init mode)")
                except Exception as e:
                    log(f"[!] Cannot set {k} in either phase: {e}")
        log("[*] exitInitializationMode (This may take a while)...")
        fmu_inst.exitInitializationMode()
        log("[OK] Initialization complete.")

        # Build VR list for output variables
        output_vrs = []
        for name in output_var_names[:]:
            try:
                output_vrs.append(get_vr(model_desc, name))
            except KeyError:
                log(f"[!] Output var not found: {name}")
                output_var_names.remove(name)

        # ─── Simulation loop ───
        current_time = 0.0
        next_sample  = 0.0
        data_rows    = []
        step_count   = 0
        
        # 1% 步进或每 1s 仿真时间输出一次日志
        log_every_steps = max(1, int((stop_time / fmu_step) / 100))
        one_sec_steps = max(1, int(1.0 / fmu_step))
        
        log(f"[*] Loop: {int(stop_time / fmu_step)} steps. Sampling every {output_interval}s")

        sim_wall_anchor = time.perf_counter()
        sim_time_anchor = 0.0
        last_log_wall = 0.0
        last_log_pct = -1
        pause_logged = False

        while current_time < stop_time - 1e-9:
            while args.pause_file and os.path.exists(args.pause_file):
                if not pause_logged:
                    log(f"[*] Orbit pre-calc paused at Time: {current_time:.2f}s")
                    pause_logged = True
                time.sleep(0.1)
                sim_wall_anchor = time.perf_counter()
                sim_time_anchor = current_time
            if pause_logged:
                log(f"[*] Orbit pre-calc resumed at Time: {current_time:.2f}s")
                pause_logged = False

            if (stop_time - current_time) < fmu_step - 1e-6:
                break

            fmu_inst.doStep(currentCommunicationPoint=current_time,
                            communicationStepSize=fmu_step)
            current_time += fmu_step
            step_count   += 1

            # 补齐采样点 (处理采样频率 > 计算频率的情况)
            while next_sample <= current_time + 1e-9:
                if next_sample > stop_time + 1e-9: break
                vals = fmu_inst.getReal(output_vrs)
                data_rows.append([next_sample] + [float(v) for v in vals])
                next_sample += output_interval

            now_wall = time.perf_counter()
            pct = min(100, int((current_time / stop_time) * 100)) if stop_time > 0 else 0
            if (now_wall - last_log_wall) >= 1.0 or pct != last_log_pct:
                log(f"[Live] [{pct}%] Time: {current_time:6.2f}s | Collected {len(data_rows)} rows | Rate: {args.sim_rate:4.1f}x")
                last_log_wall = now_wall
                last_log_pct = pct

            if args.sim_rate > 0:
                target_wall_time = sim_wall_anchor + (current_time - sim_time_anchor) / args.sim_rate
                diff = target_wall_time - time.perf_counter()
                if diff > 0.005:
                    time.sleep(diff)

        log(f"[Live] [100%] Time: {stop_time:6.2f}s | Final: {len(data_rows)} rows collected.")
        
        fmu_inst.terminate()
        fmu_inst.freeInstance()
        log(f"[OK] Done. {len(data_rows)} rows processed.")

        os.chdir(app_dir)
        export_path = os.path.join(app_dir, "orbit_pre_result.json")
        with open(export_path, 'w') as f:
            json.dump(data_rows, f)

        # 核心修复：把生成的 Orbit_Pre.txt 从临时目录捞出来，放回主目录，供实时仿真使用
        orbit_txt_source = os.path.join(bin_dir, "Orbit_Pre.txt")
        if os.path.exists(orbit_txt_source):
            # 防止把 Worker 自己写的种子文件(2行×7列)误当成FMU结果导出
            with open(orbit_txt_source) as fchk:
                out_lines = fchk.readlines()
            n_cols = len(out_lines[2].split()) if len(out_lines) > 2 else 0
            if len(out_lines) > 2 and n_cols >= 22:
                shutil.copy2(orbit_txt_source, os.path.join(app_dir, "Orbit_Pre.txt"))
                log(f"[OK] Generated Orbit_Pre.txt exported ({len(out_lines) - 2} data rows, {n_cols} cols).")
            else:
                log(f"[!] Warning: Orbit_Pre.txt in {bin_dir} is only the seed file "
                    f"({len(out_lines)} lines, {n_cols} cols) — FMU did not write results. NOT exported.")
        else:
            log(f"[!] Warning: Orbit_Pre.txt was not generated by the FMU in {bin_dir}.")

        log(f"[SUCCESS] {len(data_rows)} rows exported.")
        log(f"[EXPORT_READY] {export_path}")

    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stdout)
        log(f"[!] Fatal: {e}")
        sys.exit(1)
