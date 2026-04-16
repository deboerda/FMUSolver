import sys
import os
import struct
from fmu_player import FMUPlayer

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("fmu_path")
    parser.add_argument("--ip", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8889)
    parser.add_argument("--step", type=float, default=0.01)
    parser.add_argument("--rate", type=float, default=1.0)
    parser.add_argument("--freq", type=float, default=50.0)
    parser.add_argument("--time", type=float, default=99999.0)
    parser.add_argument("--params", type=str, default="{}", help="JSON string for init variables")
    parser.add_argument("--sync_vars", type=str, default=None, help="Path to JSON file containing fields to sync")
    args = parser.parse_args()
    
    if not os.path.exists(args.fmu_path):
        print(f"Error: FMU not found: {args.fmu_path}")
        sys.exit(1)
        
    print(f"[*] Worker Architecture: {struct.calcsize('P') * 8} bit")
    try:
        import json
        init_params = json.loads(args.params)
        player = FMUPlayer(args.fmu_path, remote_ip=args.ip, remote_port=args.port, sync_vars_file=args.sync_vars)
        player.run(step_size=args.step, sim_time=args.time, sim_rate=args.rate, sample_freq=args.freq, init_params=init_params)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
