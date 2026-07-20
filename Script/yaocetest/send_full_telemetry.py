import argparse
import configparser
import math
import os
import random
import re
import socket
import struct
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone


BEIJING_TZ = timezone(timedelta(hours=8))
DEFAULT_CRAFT = "TGMTC101"
DEFAULT_MIN_VARS = 200
DEFAULT_PACKET_BYTES = 2100
DEFAULT_TEMPLATE_LOG = r"C:\Spaceship\FMUSOLVER\FmuSolver_Package\yaocetest\xianchangtiaoshi\raw_record_20260422_161143.log"
DEFAULT_PARAM_FILTER = r"C:\Users\木木\Documents\WXWork\1688855083773985\Cache\File\2026-07\xml\xml\ParamFilter.xml"
DEFAULT_RELATIONSHIP = r"C:\Users\木木\Documents\WXWork\1688855083773985\Cache\File\2026-07\xml\xml\DTS.TM.Sim.Relationship.xml"
BUILTIN_PARAM_CODES = [
    'B0171', 'B1190', 'B1191', 'B0073', 'B1189', 'R1994', 'R1998', 'B0179',
    'B0180', 'K0693', 'K0694', 'K0695', 'K0696', 'K0697', 'K0699', 'K0024',
    'K0025', 'K0026', 'K0027', 'K0028', 'K0029', 'N1842', 'K0191', 'K0180',
    'K0189', 'N0830', 'N1111', 'N1383', 'N1655', 'N2682', 'N2963', 'N3235',
    'N3507', 'N0100', 'N1973', 'N0103', 'N1976', 'N0387', 'N0388', 'N0389',
    'N0390', 'N0391', 'N0392', 'N2260', 'N2261', 'N2262', 'N2263', 'N2264',
    'N2265', 'V0543', 'V1195', 'V1006', 'V0857', 'V0732', 'V0268', 'V0394',
    'V1498', 'V1320', 'V1409', 'V1555', 'V1615', 'V1616', 'N0828', 'N1109',
    'N1381', 'N1653', 'N2680', 'N2961', 'N3233', 'N3505', 'Y0006', 'Y0011',
    'Y0012', 'Y0029', 'Y0030', 'Y0034', 'Y0038', 'Y0039', 'Y0044', 'Y0045',
    'Y0048', 'Y0052', 'Y0053', 'Y0070', 'Y0071', 'S0067', 'DCSM34', 'A024',
    'A025', 'A026', 'A027', 'A028', 'A029', 'A02A', 'A02B', 'A02C',
    'A02D', 'A02E', 'V0469', 'V0601', 'V0656', 'V1065', 'V1117', 'V0727',
    'V1285', 'V1198', 'V0914', 'V1108', 'V0227', 'V0548', 'V0820', 'V0667',
    'V1452', 'V1240', 'V0934', 'V1128', 'V1453', 'V1242', 'V1459', 'V1249',
    'J0168', 'J0169', 'J0170', 'V0658', 'V1066', 'V0473', 'V0603', 'V1462',
    'V1252',
]


def candidate_param_filter_paths(script_dir, config_dir="", param_filter=""):
    paths = []
    if param_filter:
        paths.append(os.path.abspath(param_filter))
    roots = [script_dir, os.getcwd()]
    if config_dir:
        roots.insert(0, os.path.abspath(config_dir))
    for root in list(roots):
        roots.extend([
            os.path.join(root, "yaocetest"),
            os.path.join(root, "Script", "yaocetest"),
            os.path.join(root, "FmuSolver_Package", "yaocetest"),
            os.path.join(os.path.dirname(root), "yaocetest"),
        ])
    roots.extend([
        os.path.dirname(DEFAULT_PARAM_FILTER),
        r"C:\Spaceship\FMUSOLVER\FmuSolver_Package\yaocetest",
        r"C:\Spaceship\FMUSOLVER\Script\yaocetest",
    ])
    for root in roots:
        paths.append(os.path.join(root, "ParamFilter.xml"))

    seen = set()
    for path in paths:
        norm = os.path.normpath(os.path.abspath(path))
        if norm in seen:
            continue
        seen.add(norm)
        yield norm


def resolve_param_filter(script_dir, config_dir="", param_filter=""):
    for path in candidate_param_filter_paths(script_dir, config_dir, param_filter):
        if os.path.exists(path):
            return path
    return ""


def load_recv_port(config_dir, fallback=30019):
    parser = configparser.ConfigParser()
    try:
        parser.read(os.path.join(config_dir, "config.ini"), encoding="utf-8-sig")
        return parser.getint("Common", "RecvPort", fallback=fallback)
    except Exception:
        return fallback


def load_param_codes(param_filter_path):
    if not param_filter_path or not os.path.exists(param_filter_path):
        print("[WARN] ParamFilter.xml not found; using built-in code list.")
        return list(BUILTIN_PARAM_CODES)
    try:
        root = ET.parse(param_filter_path).getroot()
        codes = []
        seen = set()
        for param in root.findall(".//Param"):
            code = (param.get("code") or param.get("parId") or "").strip()
            if code and code not in seen:
                seen.add(code)
                codes.append(code)
        return codes or list(BUILTIN_PARAM_CODES)
    except Exception as exc:
        print(f"[WARN] Failed to read ParamFilter.xml ({exc}); using built-in code list.")
        return list(BUILTIN_PARAM_CODES)


def load_relationship_codes(relationship_path):
    if not relationship_path or not os.path.exists(relationship_path):
        return []
    try:
        root = ET.parse(relationship_path).getroot()
    except Exception:
        return []

    codes = []
    seen = set()
    for var in root.findall(".//Var"):
        expression = var.get("expression") or ""
        for code in re.findall(r"@([A-Za-z0-9_\.]+)\)", expression):
            if code and code not in seen:
                seen.add(code)
                codes.append(code)
    return codes


def resolve_relationship(script_dir, config_dir="", relationship=""):
    candidates = []
    if relationship:
        candidates.append(os.path.abspath(relationship))
    roots = [script_dir, os.getcwd()]
    if config_dir:
        roots.insert(0, os.path.abspath(config_dir))
    roots.extend([
        os.path.dirname(DEFAULT_RELATIONSHIP),
        r"C:\Spaceship\FMUSOLVER\FmuSolver_Package\yaocetest",
        r"C:\Spaceship\FMUSOLVER\Script\yaocetest",
    ])
    for root in list(roots):
        roots.extend([
            os.path.join(root, "yaocetest"),
            os.path.join(root, "Script", "yaocetest"),
            os.path.join(root, "FmuSolver_Package", "yaocetest"),
            os.path.join(os.path.dirname(root), "yaocetest"),
        ])
    for root in roots:
        candidates.append(os.path.join(root, "DTS.TM.Sim.Relationship.xml"))

    seen = set()
    for path in candidates:
        norm = os.path.normpath(os.path.abspath(path))
        if norm in seen:
            continue
        seen.add(norm)
        if os.path.exists(norm):
            return norm
    return ""


def merged_unique_codes(param_codes, relationship_codes):
    merged = []
    seen = set()
    for code in list(param_codes) + list(relationship_codes):
        if code and code not in seen:
            seen.add(code)
            merged.append(code)
    return merged


def expand_codes_for_pressure(codes, min_vars, synthetic_mode="numbered"):
    if not codes:
        return []
    expanded = [{"code": code, "source": code, "synthetic": False, "index": 0} for code in codes]
    if synthetic_mode == "repeat":
        cursor = 0
        while len(expanded) < min_vars:
            source = codes[cursor % len(codes)]
            expanded.append({"code": source, "source": source, "synthetic": False, "index": cursor + 1})
            cursor += 1
        return expanded

    cursor = 0
    while len(expanded) < min_vars:
        source = codes[cursor % len(codes)]
        suffix = (cursor // len(codes)) + 1
        expanded.append({
            "code": f"{source}_{suffix:03d}",
            "source": source,
            "synthetic": True,
            "index": suffix,
        })
        cursor += 1
    return expanded


def day_and_tenths_ms(now):
    base = datetime(2000, 1, 1, tzinfo=BEIJING_TZ)
    delta = now - base
    n_day = delta.days + 1
    seconds_in_day = now.hour * 3600 + now.minute * 60 + now.second + now.microsecond / 1_000_000.0
    return n_day, int(seconds_in_day * 10_000)


def format_value(code, frame_index, occurrence_index, seed_offset=0.0, historical_samples=None):
    now = datetime.now(BEIJING_TZ)
    absolute_day = (now - datetime(2000, 1, 1, tzinfo=BEIJING_TZ)).days
    absolute_ms = now.microsecond // 1000

    if code in ("S0067", "DCSM34", "DCSH34", "DCSW34"):
        return f"{absolute_day}:{now.hour:02d}:{now.minute:02d}:{now.second:02d}:{absolute_ms:03d}"
    if code in ("A024", "DCSH34.d", "DCSW34.d"):
        return str(absolute_day)
    if code in ("A025", "DCSH34.h", "DCSW34.h"):
        return str(now.hour)
    if code in ("A026", "DCSH34.m", "DCSW34.m"):
        return str(now.minute)
    if code in ("A027", "DCSH34.s", "DCSW34.s"):
        return str(now.second)
    if code in ("A028", "DCSH34.ms", "DCSW34.ms"):
        return str(absolute_ms)
    if code == "A029":
        return str(now.year)
    if code == "A02A":
        return str(now.month)
    if code == "A02B":
        return str(now.day)
    if code == "A02C":
        return str(now.hour)
    if code == "A02D":
        return str(now.minute)
    if code == "A02E":
        return str(now.second)

    if historical_samples:
        bucket = historical_samples.get(code) or []
        if bucket:
            sample = bucket[(frame_index + occurrence_index) % len(bucket)]
            try:
                numeric = float(sample)
                numeric += math.sin(frame_index * 0.1 + occurrence_index * 0.01) * 0.01
                return f"{numeric:.6f}"
            except Exception:
                return sample

    phase = frame_index * 0.1 + occurrence_index * 0.017 + seed_offset
    prefix = str(code)[:1].upper()
    if prefix == "K":
        value = math.sin(phase) * 180.0
    elif prefix == "N":
        value = 28.0 + math.sin(phase) * 8.0
    elif prefix == "V":
        value = 12.0 + math.sin(phase) * 4.0
    elif prefix in ("B", "R"):
        value = 70.0 + math.sin(phase) * 15.0
    elif prefix == "Y":
        value = 1.0 if int(frame_index + occurrence_index) % 20 < 10 else 0.0
    elif prefix in ("J", "P"):
        value = 5.0 + math.sin(phase) * 2.0
    else:
        value = 50.0 + math.sin(phase) * 10.0
    value += random.uniform(-0.05, 0.05)
    return f"{value:.6f}"


def build_body(entries, frame_index, historical_samples=None):
    items = []
    for idx, entry in enumerate(entries):
        code = entry["code"] if isinstance(entry, dict) else str(entry)
        source = entry.get("source", code) if isinstance(entry, dict) else code
        value = format_value(source, frame_index, idx, seed_offset=idx * 0.03, historical_samples=historical_samples)
        items.append(f"{code}A{value}/{value}")
    return " ".join(items).encode("ascii", errors="ignore")


def build_packet(body_bytes, craft=DEFAULT_CRAFT, endian="<"):
    now = datetime.now(BEIJING_TZ)
    n_day, n_ms_tenths = day_and_tenths_ms(now)
    pkg_len = 29 + len(body_bytes)
    if pkg_len > 32767:
        raise ValueError(f"packet too large for telemetry header: {pkg_len}; lower --max-packet-bytes")

    header = struct.pack(f"{endian}h", pkg_len)
    header += struct.pack("8s", craft.encode("ascii", errors="ignore")[:8].ljust(8, b"\x00"))
    header += struct.pack(f"{endian}hI", n_day, n_ms_tenths)
    header += b"\x00"
    header += b"\x01"
    header += struct.pack("4s", b"YC01")
    header += b"\x00"
    header += struct.pack("3s", b"SRC")
    header += struct.pack("3s", b"DST")
    return header + body_bytes


def load_packet_size_template(path, limit=2000):
    sizes = []
    if not path or not os.path.exists(path):
        return sizes
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as file:
            for line in file:
                match = re.search(r"RX\s+(\d+)\s+bytes", line)
                if not match:
                    continue
                size = int(match.group(1))
                if size >= 80:
                    sizes.append(size)
                if len(sizes) >= limit:
                    break
    except Exception as exc:
        print(f"[WARN] Failed to load packet template log ({exc}); using {DEFAULT_PACKET_BYTES} bytes.")
    return sizes


def load_historical_value_samples(path, known_codes, max_packets=1500, max_samples_per_code=200):
    samples = {code: [] for code in known_codes}
    if not path or not os.path.exists(path):
        return samples
    sorted_codes = sorted(known_codes, key=len, reverse=True)
    expecting_hex = False
    packets = 0
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as file:
            for line in file:
                if " RX " in line and " bytes " in line:
                    expecting_hex = True
                    continue
                if not expecting_hex:
                    continue
                expecting_hex = False
                clean_hex = line.strip().replace(" ", "").replace("\t", "")
                if len(clean_hex) < 58:
                    continue
                try:
                    data = bytes.fromhex(clean_hex)
                except Exception:
                    continue
                if len(data) <= 29:
                    continue
                body = data[29:].decode("ascii", errors="ignore")
                for item in body.split(" "):
                    if len(item) < 6:
                        continue
                    code = next((candidate for candidate in sorted_codes if item.startswith(candidate)), "")
                    if not code:
                        continue
                    value = item[len(code) + 1:].split("/", 1)[0].strip()
                    if not value:
                        continue
                    bucket = samples.setdefault(code, [])
                    if len(bucket) < max_samples_per_code:
                        bucket.append(value)
                packets += 1
                if packets >= max_packets:
                    break
    except Exception as exc:
        print(f"[WARN] Failed to load historical values ({exc}); generated values will be used.")
    return samples


def resolve_packet_size_template(args):
    if args.max_packet_bytes and args.max_packet_bytes > 0:
        return [max(200, min(int(args.max_packet_bytes), 32000))], f"fixed {args.max_packet_bytes}"
    sizes = load_packet_size_template(args.packet_template_log)
    if sizes:
        return sizes, f"raw log template ({len(sizes)} packet sizes)"
    return [DEFAULT_PACKET_BYTES], f"fallback {DEFAULT_PACKET_BYTES}"


def chunk_codes_by_packet_size(entries, frame_index, packet_size_template, historical_samples=None):
    current = []
    chunk_index = 0
    sizes = packet_size_template or [DEFAULT_PACKET_BYTES]
    for entry in entries:
        candidate = current + [entry]
        packet = build_packet(build_body(candidate, frame_index, historical_samples=historical_samples))
        max_packet_bytes = sizes[chunk_index % len(sizes)]
        if current and len(packet) > max_packet_bytes:
            yield current
            chunk_index += 1
            current = [entry]
        else:
            current = candidate
    if current:
        yield current


def send_full_telemetry(args):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    param_filter = resolve_param_filter(script_dir, args.config_dir, args.param_filter)
    relationship = resolve_relationship(script_dir, args.config_dir, args.relationship)
    config_dir = os.path.dirname(param_filter) if param_filter else os.path.abspath(args.config_dir or script_dir)
    unique_codes = merged_unique_codes(load_param_codes(param_filter), load_relationship_codes(relationship))
    if args.limit and args.limit > 0:
        unique_codes = unique_codes[:args.limit]
    entries = expand_codes_for_pressure(unique_codes, max(0, args.min_vars), args.synthetic_mode)
    if not entries:
        raise RuntimeError("No telemetry codes available.")
    synthetic_count = sum(1 for item in entries if item.get("synthetic"))

    target_port = args.port or load_recv_port(config_dir)
    target = (args.host, target_port)
    interval = 1.0 / max(0.001, args.hz)
    packet_size_template, packet_strategy = resolve_packet_size_template(args)
    historical_samples = load_historical_value_samples(args.packet_template_log, unique_codes) if args.use_historical_values else {}
    historical_codes = sum(1 for code in unique_codes if historical_samples.get(code))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if args.broadcast:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    print("[*] Full telemetry pressure sender")
    print(f"[*] ParamFilter: {param_filter or 'built-in list'}")
    print(f"[*] Relationship: {relationship or 'not found'}")
    print(f"[*] Unique codes: {len(unique_codes)}")
    print(f"[*] Variables per frame: {len(entries)} (real={len(unique_codes)} synthetic={synthetic_count} min_vars={args.min_vars})")
    print(f"[*] Target: {target[0]}:{target[1]} hz={args.hz} count={args.count or 'loop'}")
    print(f"[*] Packet strategy: {packet_strategy}")
    print(f"[*] Packet template first sizes: {packet_size_template[:10]}")
    print(f"[*] Historical value samples: {historical_codes}/{len(unique_codes)} codes")

    frame_index = 0
    total_packets = 0
    total_frames = 0
    try:
        while args.count <= 0 or frame_index < args.count:
            chunks = list(chunk_codes_by_packet_size(entries, frame_index, packet_size_template, historical_samples=historical_samples))
            frame_packets = 0
            frame_bytes = 0
            for chunk in chunks:
                packet = build_packet(build_body(chunk, frame_index, historical_samples=historical_samples), craft=args.craft)
                sock.sendto(packet, target)
                frame_packets += 1
                frame_bytes += len(packet)
                total_packets += 1
                if args.packet_gap > 0:
                    time.sleep(args.packet_gap)

            total_frames += 1
            if frame_index < 3 or total_frames % args.log_every == 0:
                print(
                    f"[SEND] frame={frame_index} vars={len(entries)} real={len(unique_codes)} synthetic={synthetic_count} "
                    f"packets={frame_packets} bytes={frame_bytes} total_packets={total_packets}"
                )

            frame_index += 1
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[*] Stopped by user.")
    finally:
        sock.close()
        print(f"[*] Done. frames={total_frames} packets={total_packets}")


def parse_args():
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Send simulated full telemetry datagrams to FmuSolver YaoCe receiver.")
    parser.add_argument("--config-dir", default=here, help="Directory containing config.ini and ParamFilter.xml.")
    parser.add_argument("--param-filter", default="", help="Override ParamFilter.xml path.")
    parser.add_argument("--relationship", default="", help="Override DTS.TM.Sim.Relationship.xml path.")
    parser.add_argument("--host", default="127.0.0.1", help="Target host.")
    parser.add_argument("--port", type=int, default=0, help="Target UDP port. Defaults to RecvPort in config.ini.")
    parser.add_argument("--hz", type=float, default=10.0, help="Frames per second.")
    parser.add_argument("--count", type=int, default=0, help="Number of frames to send. 0 means loop forever.")
    parser.add_argument("--limit", type=int, default=0, help="Only use the first N unique codes.")
    parser.add_argument("--min-vars", type=int, default=DEFAULT_MIN_VARS, help="Minimum telemetry entries per frame.")
    parser.add_argument("--synthetic-mode", choices=("numbered", "repeat"), default="numbered", help="How to fill entries when real variables are fewer than min-vars.")
    parser.add_argument("--max-packet-bytes", type=int, default=0, help="Fixed split size. 0 means use onsite raw-record packet-size template.")
    parser.add_argument("--packet-template-log", default=DEFAULT_TEMPLATE_LOG, help="Raw telemetry log used as packet-size template.")
    parser.add_argument("--use-historical-values", action=argparse.BooleanOptionalAction, default=True, help="Use value samples from the raw telemetry log when available.")
    parser.add_argument("--packet-gap", type=float, default=0.0, help="Sleep seconds between packets in one frame.")
    parser.add_argument("--log-every", type=int, default=10, help="Print one progress line every N frames.")
    parser.add_argument("--craft", default=DEFAULT_CRAFT, help="8-byte spacecraft id in packet header.")
    parser.add_argument("--broadcast", action="store_true", help="Enable UDP broadcast socket option.")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        send_full_telemetry(parse_args())
    except Exception as exc:
        print(f"[ERROR] send_full_telemetry failed: {exc}")
        print(r"[HELP] python C:\Spaceship\FMUSOLVER\FmuSolver_Package\yaocetest\send_full_telemetry.py --host 127.0.0.1 --port 30019 --hz 10")
