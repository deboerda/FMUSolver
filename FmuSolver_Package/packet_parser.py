import struct
from datetime import datetime, timedelta

class InfoBody:
    def __init__(self, sys_ident, exceed_code, value, source_code, src_str, mapped_name=None):
        self.sys_ident = sys_ident
        self.exceed_code = exceed_code
        self.value = value
        self.source_code = source_code
        self.src_str = src_str
        self.mapped_name = mapped_name if mapped_name else sys_ident

class InfoTransPkg:
    def __init__(self):
        self.pkg_len = 0
        self.craft_num = ""
        self.recv_time = ""
        self.reserve = 0
        self.data_ident = 0
        self.info_ident = ""
        self.auxiliary_ident = 0
        self.info_src = ""
        self.info_dest = ""
        self.info_body_vct = []

class PacketParser:
    @staticmethod
    def gen_time(day_offset, ms_offset):
        # 严格复刻 C++: baseTime = QDateTime(QDate(2000,1,1), QTime(0,0,0,0))
        base_date = datetime(2000, 1, 1)
        # target_date = baseTime.addDays(nDay - 1).addMSecs(fMS)
        target_date = base_date + timedelta(days=day_offset)
        final_time = target_date + timedelta(milliseconds=ms_offset)
        return final_time.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def parse_datagram(data, endian_mark='<', filter_set=None):
        # Header 长度需满足 29 字节
        if len(data) < 29:
            raise ValueError(f"Packet too short: {len(data)} bytes (expected >= 29).")
            
        pkg = InfoTransPkg()
        
        try:
            # OFFSET 0-2: nLen (short)
            pkg.pkg_len = struct.unpack(f"{endian_mark}h", data[0:2])[0]
            
            # OFFSET 2-10: craftNum (8 bytes char)
            pkg.craft_num = data[2:10].decode('ascii', errors='ignore').strip('\x00')
            
            # OFFSET 10-12: nDay (short)
            nDay = struct.unpack(f"{endian_mark}h", data[10:12])[0]
            
            # OFFSET 12-16: nMS (unsigned int)
            nMS = struct.unpack(f"{endian_mark}I", data[12:16])[0]
            fMS = nMS * 0.1 # 毫秒步长转换
            
            # 这里的 nDay-1 逻辑完全遵循 C++ 源码
            pkg.recv_time = PacketParser.gen_time(nDay - 1, int(fMS))
            
            # OFFSET 16: reserve (char)
            pkg.reserve = data[16]
            
            # OFFSET 17: data_ident (char)
            pkg.data_ident = data[17]
            
            # OFFSET 18-22: info_ident (4 bytes char)
            pkg.info_ident = data[18:22].decode('ascii', errors='ignore').strip('\x00')
            
            # OFFSET 22: auxiliary_ident (char)
            pkg.auxiliary_ident = data[22]
            
            # OFFSET 23-26: info_src (3 bytes char)
            pkg.info_src = data[23:26].decode('ascii', errors='ignore').strip('\x00')
            
            # OFFSET 26-29: info_dest (3 bytes char)
            pkg.info_dest = data[26:29].decode('ascii', errors='ignore').strip('\x00')
        except Exception as e:
            raise ValueError(f"Header parsing failed: {e}")
            
        try:
            # BODY 解析: 
            body_bytes = data[29:29 + (pkg.pkg_len - 27)]
            str_info_body = body_bytes.decode('ascii', errors='ignore')
            
            # 拆分逻辑: body.split(' ')
            info_body_lst = str_info_body.split(" ")
            for item_str in info_body_lst:
                if not item_str or len(item_str) < 6:
                    continue
                
                # 使用正则表达式提取 ID (字母/字符串 + 数字)
                import re
                id_match = re.match(r'^([a-zA-Z]+[0-9]+)', item_str)
                found = False
                sys_ident = ""
                exceed_code = ""
                value_part = ""

                if id_match:
                    full_id = id_match.group(1)
                    # 优先进行高级匹配检查
                    target_id = full_id
                    
                    # 尝试匹配全长及缩短版本 (5, 4, 6位)
                    candidate_ids = [full_id]
                    if len(full_id) > 5: candidate_ids.append(full_id[:5])
                    if len(full_id) > 4: candidate_ids.append(full_id[:4])
                    if len(full_id) > 6: candidate_ids.append(full_id[:6])

                    for cid in candidate_ids:
                        # 如果传入了 filter_mgr 对象，使用它的高级匹配逻辑
                        if hasattr(filter_set, 'is_param_allowed'):
                            allowed, mapped_name = filter_set.is_param_allowed(cid)
                        else:
                            allowed, mapped_name = (cid in filter_set, cid) if filter_set is not None else (True, cid)
                        
                        if allowed:
                            sys_ident = cid
                            # 剥离 ID 后的内容
                            rem = item_str[len(cid):]
                            exceed_code = rem[0:1] if len(rem) > 0 else ""
                            value_part = rem[1:] if len(rem) > 1 else ""
                            found = True
                            target_mapped_name = mapped_name
                            break
                
                if not found:
                    continue

                value_lst = value_part.split("/")
                if len(value_lst) == 1:
                    prj_value = value_lst[0]
                    source_code = value_lst[0]
                else:
                    prj_value = value_lst[0]
                    source_code = value_lst[1]
                    
                pkg.info_body_vct.append(InfoBody(sys_ident, exceed_code, prj_value, source_code, item_str, mapped_name=target_mapped_name))
                
        except Exception as e:
            raise ValueError(f"Body parsing failed: {e}")
            
        return pkg
