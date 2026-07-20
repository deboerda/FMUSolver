"""Bidirectional PE injection/current-output smoke test.

The sender continuously sends six PE inputs to the Python listener (default
127.0.0.1:9988). A receiver listens for the Worker output (default
127.0.0.1:8889), extracts the four solar-current outputs from DDM/Protobuf
packets, and appends the latest values to a CSV log.
"""

import argparse
import base64
import csv
import datetime
import os
import socket
import sys
import threading
import time

import ddm_pb2


PE_VARIABLES = {
    "SolarAngle_CJinput[1]": 0.0,
    "SolarAngle_CJinput[2]": 0.0,
    "solar_CJinput[1]": 1353.0,
    "solar_CJinput[2]": 1353.0,
    "ShelterRatio_CJinput[1]": 0.0,
    "ShelterRatio_CJinput[2]": 0.0,
}
CURRENT_VARIABLES = (
    "Sys_ISolar_A",
    "Sys_ISolar_B",
    "ISolar[1]",
    "ISolar[2]",
)


def build_packet(sim_time):
    packet = ddm_pb2.DDMData()
    packet.machine_time = time.time()
    packet.sim_time = sim_time
    for name, value in PE_VARIABLES.items():
        variable = packet.sim_vars.add()
        variable.name = name
        variable.type = ddm_pb2.DDMData.SimVar.Type.Value("Double")
        variable.double_value = value
    return base64.b64encode(packet.SerializeToString())


def parse_ddm_packet(data):
    packet = ddm_pb2.DDMData()
    packet.ParseFromString(base64.b64decode(data, validate=True))
    values = {}
    type_names = ddm_pb2.DDMData.SimVar.Type
    for variable in packet.sim_vars:
        if variable.type == type_names.Value("Double"):
            values[variable.name] = variable.double_value
        elif variable.type == type_names.Value("Int"):
            values[variable.name] = variable.int_value
        elif variable.type == type_names.Value("Bool"):
            values[variable.name] = bool(variable.bool_value)
        elif variable.type == type_names.Value("String"):
            values[variable.name] = variable.string_value
    return packet.sim_time, values


def parse_dashboard_packet(data):
    """Keep the original helper API for the optional PE echo check."""
    return parse_ddm_packet(data)[1]


def wait_for_dashboard(sock, timeout):
    expected = {f"PE.{name}" for name in PE_VARIABLES}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sock.settimeout(max(0.05, deadline - time.monotonic()))
        try:
            values = parse_dashboard_packet(sock.recv(65535))
        except (socket.timeout, ValueError, TypeError):
            continue
        if expected.issubset(values):
            return values
    return None


def current_receiver_loop(sock, stop_event, log_path, log_interval, stats):
    """Receive Worker packets and periodically append the latest currents."""
    log_path = os.path.abspath(log_path)
    parent = os.path.dirname(log_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    file_exists = os.path.exists(log_path) and os.path.getsize(log_path) > 0
    latest = None
    last_log_time = 0.0
    try:
        with open(log_path, "a", encoding="utf-8", newline="") as log_file:
            writer = csv.writer(log_file)
            if not file_exists:
                writer.writerow(
                    [
                        "wall_time",
                        "sim_time",
                        *CURRENT_VARIABLES,
                        "source_ip",
                        "source_port",
                        "status",
                    ]
                )
                log_file.flush()

            sock.settimeout(0.5)
            while not stop_event.is_set():
                try:
                    data, addr = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                except OSError:
                    break

                stats["received_packets"] += 1
                try:
                    sim_time, values = parse_ddm_packet(data)
                except (ValueError, TypeError, UnicodeError):
                    stats["decode_errors"] += 1
                    continue

                found = {name: values[name] for name in CURRENT_VARIABLES if name in values}
                if not found:
                    continue
                latest = (sim_time, found, addr)
                now = time.monotonic()
                if log_interval > 0 and now - last_log_time < log_interval:
                    continue

                sim_time_value, current_values, source = latest
                status = "ok" if all(name in current_values for name in CURRENT_VARIABLES) else "partial"
                writer.writerow(
                    [
                        datetime.datetime.now().astimezone().isoformat(timespec="milliseconds"),
                        sim_time_value,
                        *(current_values.get(name, "") for name in CURRENT_VARIABLES),
                        source[0],
                        source[1],
                        status,
                    ]
                )
                log_file.flush()
                stats["current_rows"] += 1
                last_log_time = now
                latest = None

            if latest is not None:
                sim_time_value, current_values, source = latest
                status = "ok" if all(name in current_values for name in CURRENT_VARIABLES) else "partial"
                writer.writerow(
                    [
                        datetime.datetime.now().astimezone().isoformat(timespec="milliseconds"),
                        sim_time_value,
                        *(current_values.get(name, "") for name in CURRENT_VARIABLES),
                        source[0],
                        source[1],
                        status,
                    ]
                )
                log_file.flush()
                stats["current_rows"] += 1
    except OSError as exc:
        stats["log_error"] = str(exc)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Continuously send six PE variables and log four Worker current outputs."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Python PE injection IP")
    parser.add_argument("--port", type=int, default=9988, help="Python PE injection port")
    parser.add_argument("--sim-time", type=float, default=12.5)
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Packets to send; 0 means run continuously until Ctrl+C",
    )
    parser.add_argument("--duration", type=float, default=0.0, help="Seconds to run; 0 means no limit")
    parser.add_argument("--interval", type=float, default=0.2, help="Seconds between PE packets")
    parser.add_argument(
        "--receive-host",
        default="0.0.0.0",
        help="Local bind IP for Worker output, default: 0.0.0.0",
    )
    parser.add_argument(
        "--receive-port",
        type=int,
        default=8889,
        help="Worker output port, default: 8889",
    )
    parser.add_argument(
        "--log-file",
        default="pe_current_results.csv",
        help="CSV output path, default: pe_current_results.csv",
    )
    parser.add_argument(
        "--log-interval",
        type=float,
        default=0.2,
        help="Minimum seconds between CSV rows; 0 logs every matching packet",
    )
    parser.add_argument(
        "--receive-grace",
        type=float,
        default=2.0,
        help="Seconds to keep receiving after the sender stops",
    )
    parser.add_argument(
        "--verify-dashboard-port",
        type=int,
        help="Optional UDP port for checking PE.* dashboard echo",
    )
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args(argv)

    if args.count < 0:
        parser.error("--count must be >= 0")
    if args.duration < 0 or args.interval < 0 or args.log_interval < 0 or args.receive_grace < 0:
        parser.error("duration, interval, log-interval and receive-grace must be >= 0")

    dashboard_sock = None
    if args.verify_dashboard_port:
        dashboard_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dashboard_sock.bind(("127.0.0.1", args.verify_dashboard_port))

    receiver_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        receiver_sock.bind((args.receive_host, args.receive_port))
    except OSError as exc:
        receiver_sock.close()
        parser.error(f"cannot bind Worker output {args.receive_host}:{args.receive_port}: {exc}")

    stop_event = threading.Event()
    stats = {"received_packets": 0, "decode_errors": 0, "current_rows": 0, "log_error": ""}
    receiver = threading.Thread(
        target=current_receiver_loop,
        args=(receiver_sock, stop_event, args.log_file, args.log_interval, stats),
        daemon=True,
        name="pe-current-receiver",
    )
    receiver.start()

    payload = build_packet(args.sim_time)
    target = (args.host, args.port)
    sent = 0
    started = time.monotonic()
    print(f"[INFO] Sending PE inputs to {target[0]}:{target[1]}")
    print(
        f"[INFO] Receiving {', '.join(CURRENT_VARIABLES)} "
        f"from {args.receive_host}:{args.receive_port}"
    )
    print(f"[INFO] Current CSV log: {os.path.abspath(args.log_file)}")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            while (args.count == 0 or sent < args.count) and (
                args.duration == 0 or time.monotonic() - started < args.duration
            ):
                sender.sendto(payload, target)
                sent += 1
                if args.interval > 0:
                    time.sleep(args.interval)
    except KeyboardInterrupt:
        print("[INFO] Stopped by Ctrl+C")
    finally:
        if args.receive_grace > 0:
            time.sleep(args.receive_grace)
        stop_event.set()
        receiver_sock.close()
        receiver.join(timeout=2.0)
        if dashboard_sock is not None:
            try:
                values = wait_for_dashboard(dashboard_sock, args.timeout)
            finally:
                dashboard_sock.close()
            expected = {f"PE.{name}" for name in PE_VARIABLES}
            if values is None or not expected.issubset(values):
                print("[FAIL] Dashboard echo does not contain all PE.* variables.")
                return 1
            print("[PASS] Dashboard echo contains all six PE.* variables.")

    print(f"[PASS] Sent {sent} PE packet(s) to {target[0]}:{target[1]}")
    print(
        f"[INFO] Worker packets={stats['received_packets']} current_rows={stats['current_rows']} "
        f"decode_errors={stats['decode_errors']}"
    )
    if stats["log_error"]:
        print(f"[FAIL] Current CSV log error: {stats['log_error']}")
        return 1
    if stats["current_rows"] == 0:
        print(
            "[WARN] No solar-current packets received; check Worker --port "
            "and sync_fields.json."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
