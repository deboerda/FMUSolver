import socket
import base64
import time
import random

# ����������Ҫģ�� DDMData �� Protobuf �ṹ
# ���ڻ������ƣ����ǲ�ֱ��ʹ�����ɵ� pb2 �ļ������ǹ������������Ƹ�ʽ������
# �ṹ�ο���
# message DDMData {
#   double machine_time = 1;
#   double sim_time = 2;
#   repeated SimVar sim_vars = 3;
# }
# message SimVar {
#   string name = 1;
#   Type type = 2;
#   double double_value = 3;
# }

def encode_varint(value):
    """���� protobuf �� varint"""
    bits = value & 0x7f
    value >>= 7
    while value:
        yield bits | 0x80
        bits = value & 0x7f
        value >>= 7
    yield bits

def pack_double(field_number, value):
    """���� protobuf �� double (fixed64)"""
    import struct
    tag = (field_number << 3) | 1
    return bytes([(tag)]) + struct.pack('<d', value)

def pack_string(field_number, value):
    """���� protobuf �� string"""
    tag = (field_number << 3) | 2
    b_val = value.encode('utf-8')
    return bytes([(tag)]) + bytes(encode_varint(len(b_val))) + b_val

def pack_message(field_number, content):
    """����Ƕ����Ϣ"""
    tag = (field_number << 3) | 2
    return bytes([(tag)]) + bytes(encode_varint(len(content))) + content

def create_payload(sim_time, data_dict):
    # Field 2: sim_time (double)
    payload = pack_double(2, sim_time)
    
    # Field 3: sim_vars (repeated SimVar)
    for name, value in data_dict.items():
        # SimVar: name(1), type(2, Double=3), double_value(3)
        var_content = pack_string(1, name)
        var_content += bytes([(2 << 3) | 0]) + bytes([3]) # Type=Double
        var_content += pack_double(3, value)
        payload += pack_message(3, var_content)
        
    # ת Base64
    return base64.b64encode(payload).decode('ascii')

def main():
    dest_ip = "127.0.0.1"
    dest_port = 12345
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print(f"Starting test sender to {dest_ip}:{dest_port}...")
    
    t = 0
    try:
        while True:
            # �����������
            test_data = {
                "Temp3": 300 + 50 * random.random(),
                "R_speed3": 1000 + 200 * random.random(),
                "FuelRack3": 50 + 10 * random.random()
            }
            
            b64_msg = create_payload(float(t), test_data)
            sock.sendto(b64_msg.encode('ascii'), (dest_ip, dest_port))
            
            if t % 10 == 0:
                print(f"Sent tick {t}, data: {test_data}")
            
            t += 1
            time.sleep(0.1) # 10Hz
    except KeyboardInterrupt:
        print("Stopped.")

if __name__ == "__main__":
    main()
