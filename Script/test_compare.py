import struct
import json
import os

# 模拟原始报文数据
# 1. K0693 (5位ID, 正常值)
# 2. N0100 (5位ID, 带斜杠的工程值/源码)
# 3. V0103 (5位ID, AAAAAAAA填充字)
# 4. DCSM34 (6位ID, 正常值)
raw_body = "K0693A6766.71 N0100A55.5/AAAA V0103AAAAAAAAA DCSM34A123.45"

def qt_style_parse(item_str):
    """
    模拟 Qt PacketHandle.cpp 逻辑:
    - 索引 0-5: ID
    - 索引 5: Exceed
    - 索引 6: Value (带斜杠处理)
    """
    sys_ident = item_str[0:5]
    value_part = item_str[6:]
    prj_value = value_part.split("/")[0]
    return sys_ident, prj_value

def python_current_parse(item_str):
    """
    模拟当前 Python (packet_parser.py + main.py) 逻辑:
    - 动态 ID 长度探测
    - 自动十六进制回退转换
    """
    # 简单模拟动态长度 (DCSM34=6, 其余=5)
    id_len = 6 if item_str.startswith("DCSM34") else 5
    value_part = item_str[id_len+1:].split("/")[0]
    
    # 模拟 main.py 中的 add_to_sim_vars 转换逻辑
    clean_val = value_part.strip()
    try:
        return float(clean_val)
    except ValueError:
        try:
            return float(int(clean_val, 16))
        except:
            return 0.0
    except:
        return 0.0

print("\n[数据解析对照测试]")
print(f"{'原始项':<20} | {'Qt 逻辑提取':<15} | {'Python 最终转换值':<15}")
print("-" * 60)

for item in raw_body.split(" "):
    q_id, q_val = qt_style_parse(item)
    p_val = python_current_parse(item)
    print(f"{item:<20} | {q_val:<15} | {p_val:<15}")

print("\n[分析结论]:")
print("1. 为什么出现 2863311530? 因为 AAAAAAAA 被 Python 自动识别为了十六进制并成功转换。")
print("2. 为什么会有异常跳变? 当遥测源发送 AAAA 填充字时，Qt 仅将其作为字符串处理(通常不显示或报错)，但 Python 强行将其转成了数字注入了 FMU。")
print("3. 解析偏移风险: Qt 固定 5 位 ID，如果遇到 6 位 ID (如 DCSM34)，Qt 会解析错位，而 Python 能正确识别 ID。")
