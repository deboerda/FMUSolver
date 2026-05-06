import binascii
import sys
import os

# 从真实日志提取的一段原始字节片段 (Hex String)
# 对应: T0007N13.733/030A ... T0695NAA55/AA55
hex_payload = "54 30 30 30 37 4E 31 33 2E 37 33 33 2F 30 33 30 41 20 54 30 36 39 35 4E 41 41 35 35 2F 41 41 35 35"
raw_str = "".join([chr(int(h, 16)) for h in hex_payload.split()])

def parse_item(item_str, use_old_logic=False):
    """
    模拟解析与转换逻辑
    """
    # 模拟 packet_parser.py 拆分
    id_len = 5
    value_part = item_str[id_len+1:].split("/")[0]
    
    # 模拟转换逻辑
    clean_val = value_part.strip()
    try:
        return float(clean_val)
    except ValueError:
        if use_old_logic:
            try:
                # 旧逻辑会尝试十六进制转换
                return float(int(clean_val, 16))
            except: return 0.0
        else:
            # 新逻辑直接拦截
            return 0.0

print("\n[真实数据解析对照测试]")
print("-" * 70)
print(f"{'原始项':<20} | {'旧逻辑注入值 (故障)':<20} | {'新逻辑注入值 (修复)'}")
print("-" * 70)

for item in raw_str.split(" "):
    if not item: continue
    old_val = parse_item(item, use_old_logic=True)
    new_val = parse_item(item, use_old_logic=False)
    print(f"{item:<20} | {old_val:<20} | {new_val}")

print("-" * 70)
print("[分析]:")
print("1. 对于正常数据 (T0007)，新旧逻辑均能得到 13.733。")
print("2. 对于异常填充字 (T0695)，旧逻辑会将其转为 43605.0，这正是导致 FMU 崩溃的原因！")
print("3. 新逻辑将其安全地设为 0.0，避免了天文数字对仿真的破坏。")
