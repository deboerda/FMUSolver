import socket
import json
import argparse
import sys

def send_command(step_size=None, sim_time=None, sim_rate=None, sample_freq=None, test_mode=False):
    # 目标 IP 和 Python 接收侧的端口
    target_ip = "127.0.0.1"
    target_port = 8888 
    
    cmd = {}
    if step_size is not None: cmd["step_size"] = step_size
    if sim_time is not None: cmd["sim_time"] = sim_time
    if sim_rate is not None: cmd["sim_rate"] = sim_rate
    if sample_freq is not None: cmd["sample_freq"] = sample_freq
    
    if not cmd:
        print("未提供任何参数。使用 -h 查看帮助。")
        return
        
    print(f"[*] 正在向仿真引擎 ({target_ip}:{target_port}) 发送动态控制指令:")
    print(json.dumps(cmd, indent=4))
    
    if test_mode:
        print("测试模式：未实际发送包。")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(json.dumps(cmd).encode('utf-8'), (target_ip, target_port))
        print("[OK] 指令发送成功！仿真引擎将立即应用。")
    except Exception as e:
        print(f"[!] 发送失败: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FMU 仿真引擎动态控制器 (热更新参数)")
    parser.add_argument("--step-size", type=float, help="设置积分步长 (默认0.01秒)")
    parser.add_argument("--sim-time", type=float, help="限制仿真结束时间 (例如100.0, 到达后代码将停止)")
    parser.add_argument("--sim-rate", type=float, help="设置仿真速率 (1.0=按真实时间走, 2.0=两倍速 0=解除了锁频最快速度运行)")
    parser.add_argument("--sample-freq", type=float, help="设置抽取与外发 UDP 数据的采样频率 (Hz) (0=每个积分步都发送)")
    
    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
        
    send_command(args.step_size, args.sim_time, args.sim_rate, args.sample_freq)
