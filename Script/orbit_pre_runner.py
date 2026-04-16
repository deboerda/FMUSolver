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
import json
import time
import math
import zipfile
import shutil
import fmpy
from fmpy import instantiate_fmu, read_model_description


def log(msg):
    print(msg, flush=True)


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
    """Write minimal Orbit_Pre.txt seed: 1 row of initial conditions."""
    with open(path, 'w') as fp:
        fp.write("#1\n")
        fp.write("double table(1,7)\n")
        fp.write(f"{jd:.5f}\t{a:.5f}\t{e:.5f}\t{i:.5f}\t"
                 f"{omega_big:.5f}\t{omega_small:.5f}\t{f:.5f}\n")
    log(f"[OK] Seed file: JD={jd:.5f}")


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
    extract_dir = os.path.join(app_dir, "fmu_orbit_work")
    os.makedirs(extract_dir, exist_ok=True)
    log("[*] Extracting FMU...")
    with zipfile.ZipFile(args.fmu_path, 'r') as z:
        z.extractall(extract_dir)

    # ─── 2. Patch DLLs only (NOT existing Orbit_Pre.txt) ───
    arch    = "win32"
    bin_dir = os.path.join(extract_dir, "binaries", arch)
    os.makedirs(bin_dir, exist_ok=True)

    protected = {'kernel32.dll', 'user32.dll', 'ntdll.dll', 'advapi32.dll'}
    for fname in os.listdir(app_dir):
        if fname.lower().endswith('.dll') and fname.lower() not in protected:
            src_file = os.path.join(app_dir, fname)
            f_arch = check_dll_arch(src_file)
            if f_arch and f_arch != arch:
                continue
            dst = os.path.join(bin_dir, fname)
            if not os.path.exists(dst):
                log(f"[*] Patching {fname}")
                shutil.copy2(src_file, dst)

    # ─── 3. Generate seed Orbit_Pre.txt in bin_dir ───
    seed_path = os.path.join(bin_dir, "Orbit_Pre.txt")
    generate_seed_orbit_txt(seed_path, jd_seed, a_mt, e_mt, i_mt, omega_mt, omega_s_mt, f_mt)

    # ─── 4. DLL paths & CWD ───
    if hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(app_dir)
        os.add_dll_directory(bin_dir)
    os.environ['PATH'] = bin_dir + os.pathsep + app_dir + os.pathsep + os.environ.get('PATH', '')
    os.chdir(bin_dir)
    log(f"[*] CWD = {bin_dir}")

    # ── Pre-load all companion DLLs from bin_dir into process space ──
    import ctypes
    loaded_ok = []
    load_fail = []
    for fname in sorted(os.listdir(bin_dir)):
        if fname.lower().endswith('.dll') and fname.lower() not in protected:
            fpath = os.path.join(bin_dir, fname)
            try:
                ctypes.CDLL(fpath)
                loaded_ok.append(fname)
            except Exception as e:
                load_fail.append(f"{fname}: {e}")
    log(f"[*] Pre-loaded {len(loaded_ok)} DLLs. Failures: {len(load_fail)}")
    # ────────────────────────────────────────────────────────────────

    orbit_txt_abs = seed_path.replace('\\', '/')

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

        # Override filepath → our seed file
        all_vars = list(getattr(model_desc, 'modelVariables', []))
        for v in all_vars:
            t  = getattr(v, 'type', None) or getattr(v, 'typeName', '')
            sv = getattr(v, 'start', '') or ''
            if t == 'String' and ('Orbit_Pre' in sv or v.name == 'filepath'):
                log(f"[*] filepath → {orbit_txt_abs}")
                fmu_inst.setString([v.valueReference], [orbit_txt_abs])

        # Set user params with Year forced to valid range
        var_map = {v.name: v for v in model_desc.modelVariables}
        params_to_set = dict(user_params)
        params_to_set['Year'] = float(eff_year)   # Force valid year

        for k, val in params_to_set.items():
            if k in var_map:
                try:
                    fmu_inst.setReal([var_map[k].valueReference], [float(val)])
                    log(f"[*] Set {k} = {val}")
                except Exception as e:
                    log(f"[!] Cannot set {k}: {e}")

        # ─── Initialize ───
        log("[*] Entering initialization...")
        fmu_inst.enterInitializationMode()
        fmu_inst.exitInitializationMode()
        log("[OK] Initialization complete.")

        # Build VR list
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
        log_every    = max(1, int(max(10.0 * fmu_step, stop_time / 100) / fmu_step))
        step_count   = 0
        log(f"[*] Loop: {int(stop_time / fmu_step)} steps")

        while current_time < stop_time - 1e-9:
            perf = time.perf_counter()
            if (stop_time - current_time) < fmu_step - 1e-6:
                break  # Don't do partial steps

            fmu_inst.doStep(currentCommunicationPoint=current_time,
                            communicationStepSize=fmu_step)
            current_time += fmu_step
            step_count   += 1

            if current_time >= next_sample - 1e-9:
                vals = fmu_inst.getReal(output_vrs)
                data_rows.append([current_time] + [float(v) for v in vals])
                next_sample += output_interval

            if step_count % log_every == 0:
                log(f"[Live] t={current_time:.0f}s | rows={len(data_rows)}")

            if args.sim_rate > 0:
                elapsed = time.perf_counter() - perf
                sleep_t = (fmu_step / args.sim_rate) - elapsed
                if sleep_t > 0:
                    time.sleep(sleep_t)

        fmu_inst.terminate()
        fmu_inst.freeInstance()
        log(f"[OK] Done. {len(data_rows)} rows collected.")

        os.chdir(app_dir)
        export_path = os.path.join(app_dir, "orbit_pre_result.json")
        with open(export_path, 'w') as f:
            json.dump(data_rows, f)

        log(f"[SUCCESS] {len(data_rows)} rows exported.")
        log(f"[EXPORT_READY] {export_path}")

    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stdout)
        log(f"[!] Fatal: {e}")
        sys.exit(1)
