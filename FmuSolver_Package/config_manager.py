import configparser
import os
import re
from datetime import datetime

ET = None

def get_xml_parser():
    global ET
    if ET is None:
        import xml.etree.ElementTree as ElementTree
        ET = ElementTree
    return ET

class ConfigManager:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.config_ini_path = os.path.join(root_dir, "config.ini")
        self.param_filter_path = os.path.join(root_dir, "ParamFilter.xml")
        self.filter_params = set()       # 原始 code 集合（完整匹配）
        self.filter_numeric = set()      # 数字后缀集合（去前缀匹配）
        self.filter_num_to_code = {}     # 数字后缀 -> 原始code 映射（用于调试）
        self.telemetry_to_sim_map = {}    # 遥测 code/parId -> FMU sim_var
        self.expression_mappings = []      # expression -> sim_var，用于时间码等复合变量
        self.sat_time_config = None
        self.targets = []
        self.local_injection_targets = set()
        self.config = {}

    def candidate_config_dirs(self):
        # Keep runtime telemetry configuration self-contained in the selected
        # yaocetest directory, avoiding stale XML files from other folders.
        root = os.path.abspath(self.root_dir)
        return [root] if os.path.isdir(root) else []

    def load_config(self):
        parser = configparser.ConfigParser()
        if os.path.exists(self.config_ini_path):
            parser.read(self.config_ini_path, encoding='utf-8-sig')
            if 'Common' in parser:
                common = parser['Common']
                self.config['RecvPort'] = int(common.get('RecvPort', '30019'))

                # 读取字节序配置: little 或 big
                endian_str = common.get('Endian', 'little').lower()
                self.config['EndianMark'] = '>' if endian_str == 'big' else '<'
                print(f"[*] Configured Endian: {endian_str} ('{self.config['EndianMark']}')")

                pe_ip = os.environ.get('FMUSOLVER_PE_IP', '').strip()
                pe_port = os.environ.get('FMUSOLVER_PE_PORT', '').strip()
                merge_via_worker = os.environ.get('FMUSOLVER_MERGE_TELEMETRY_VIA_WORKER', '').strip().lower() in ('1', 'true', 'yes', 'on')
                def add_target(host, port):
                    target = (str(host), int(port))
                    if target not in self.targets:
                        self.targets.append(target)

                if pe_ip and pe_port:
                    if merge_via_worker:
                        print(f"[*] PE target {pe_ip}:{pe_port} will be merged into FMU Worker packets; telemetry direct PE forwarding disabled.")
                    else:
                        add_target(pe_ip, pe_port)
                        print(f"[*] Unified PE target from FmuSolver UI: {pe_ip}:{pe_port}")

                    local_inject_port = os.environ.get('FMUSOLVER_LOCAL_INJECT_PORT', '').strip()
                    if local_inject_port:
                        add_target('127.0.0.1', local_inject_port)
                        self.local_injection_targets.add(('127.0.0.1', int(local_inject_port)))
                        print(f"[*] Local FMU injection target: 127.0.0.1:{local_inject_port}")
                    return

                # 读取双目标配置
                t1_ip = common.get('Target1_IP', '127.0.0.1')
                t1_port = int(common.get('Target1_Port', '8888'))
                add_target(t1_ip, t1_port)

                t2_ip = common.get('Target2_IP', '127.0.0.1')
                t2_port = int(common.get('Target2_Port', '8890'))
                add_target(t2_ip, t2_port)
        else:
            print(f"[!] Warning: config.ini not found at {self.config_ini_path}. Using defaults.")
            self.config['RecvPort'] = 30019
            self.config['EndianMark'] = '<'
            self.targets = [("127.0.0.1", 8888), ("127.0.0.1", 8890)]

    def load_filter_params(self):
        """
        加载白名单 XML。
        兼容两种格式：
          - 正式版: <Param code="N0828" ... />
          - 开发版: <Item name="N0828" ... />

        匹配策略（双轨）：
          1. 精确匹配: param_name in filter_params (完整 ID 相同)
          2. 数字后缀匹配: param_name[1:] in filter_numeric (忽略第一个字母前缀)
             用于处理白名单写 N0828 但报文发来 S0828 的情况
        """
        if not os.path.exists(self.param_filter_path):
            print(f"[!] Warning: Filter file {self.param_filter_path} not found.")
            return
        try:
            ET = get_xml_parser()
            tree = ET.parse(self.param_filter_path)
            root = tree.getroot()

            # 情况1: 匹配 <Param code="xxx" ... /> (正式版)
            for param in root.findall('Param'):
                code = param.get('code') or param.get('parId')
                if code:
                    self.filter_params.add(code)
                    # 提取数字后缀（去掉第1个字母），长度5的标准ID
                    if len(code) >= 2:
                        num = code[1:]
                        self.filter_numeric.add(num)
                        if num not in self.filter_num_to_code: self.filter_num_to_code[num] = []
                        if code not in self.filter_num_to_code[num]: self.filter_num_to_code[num].append(code)

            # 情况2: 匹配 <Item name="xxx" ... /> (开发版)
            for item in root.findall('Item'):
                name = item.get('name')
                if name:
                    self.filter_params.add(name)
                    if len(name) >= 2:
                        num = name[1:]
                        self.filter_numeric.add(num)
                        if num not in self.filter_num_to_code: self.filter_num_to_code[num] = []
                        if name not in self.filter_num_to_code[num]: self.filter_num_to_code[num].append(name)

            print(f"[*] Loaded {len(self.filter_params)} parameters for filtering.")
            print(f"[*] Numeric-suffix index built: {len(self.filter_numeric)} entries.")
            self.load_tm_protocol_config()
            self.load_relationship_mapping()

        except MemoryError:
            print(f"[!] MemoryError parsing ParamFilter.xml. Try reducing other running processes or use the packaged 64-bit telemetry worker.")
        except Exception as e:
            print(f"[!] Error parsing ParamFilter.xml: {e}")

    def load_relationship_mapping(self):
        candidates = []
        for d in self.candidate_config_dirs():
            candidates.append(os.path.join(d, "DTS.TM.Sim.Relationship.xml"))
        rel_path = next((p for p in candidates if os.path.exists(p)), None)
        if not rel_path:
            print("[*] Telemetry relationship XML not found; using raw telemetry codes.")
            return
        try:
            ET = get_xml_parser()
            root = ET.parse(rel_path).getroot()
            for var in root.findall('.//Var'):
                sim_var = (var.get('sim_var') or '').strip()
                expr = var.get('expression') or ''
                if not sim_var:
                    continue
                codes = re.findall(r'@([A-Za-z0-9_]+)\)', expr)
                codes_with_dot = re.findall(r'@([A-Za-z0-9_\.]+)\)', expr)
                if len(codes_with_dot) >= 2:
                    self.expression_mappings.append({"sim_var": sim_var, "expression": expr, "codes": codes_with_dot})
                    continue
                # Only direct one-to-one expressions can be safely renamed here.
                if len(codes) != 1:
                    continue
                code = codes[0].strip()
                self.telemetry_to_sim_map[code] = sim_var
            print(f"[*] Loaded {len(self.telemetry_to_sim_map)} telemetry->sim variable mappings and {len(self.expression_mappings)} expressions from {rel_path}")
        except MemoryError:
            print(f"[!] MemoryError parsing telemetry relationship XML: {rel_path}")
        except Exception as e:
            print(f"[!] Error parsing telemetry relationship XML: {e}")

    def map_to_sim_var(self, telemetry_code):
        return self.telemetry_to_sim_map.get(telemetry_code, telemetry_code)

    def load_tm_protocol_config(self):
        candidates = []
        for d in self.candidate_config_dirs():
            for name in ("DTS.TM.PROTOBUF.xml", "DTS.TM.PROTOBUF2.xml", "DTS.TM.PROTOBUF单舱.xml"):
                candidates.append(os.path.join(d, name))
        proto_path = next((p for p in candidates if os.path.exists(p)), None)
        if not proto_path:
            return
        try:
            ET = get_xml_parser()
            root = ET.parse(proto_path).getroot()
            loaded_params = 0
            for param in root.findall('.//Param'):
                for key in (param.get('code'), param.get('parId')):
                    if key:
                        self.filter_params.add(key)
                        loaded_params += 1
            sat_time = root.find('.//SatTime')
            if sat_time is not None:
                self.sat_time_config = dict(sat_time.attrib)
                try:
                    datetime.strptime(self.sat_time_config.get('timeZero', ''), "%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass
            print(f"[*] Loaded TM protocol config: {proto_path} (params+aliases={loaded_params}, SatTime={self.sat_time_config})")
        except Exception as e:
            print(f"[!] Error parsing TM protocol config: {e}")

    def evaluate_expression_mappings(self, value_map):
        results = {}
        for item in self.expression_mappings:
            expr = item.get("expression", "")
            codes = item.get("codes", [])
            if not codes or any(code not in value_map for code in codes):
                continue
            safe_expr = expr
            try:
                for code in sorted(codes, key=len, reverse=True):
                    safe_expr = safe_expr.replace(f"#(TGMTC101.DAHE@{code})", str(float(value_map[code])))
                    safe_expr = safe_expr.replace(f"#(TGTH0001.DAHE@{code})", str(float(value_map[code])))
                    safe_expr = safe_expr.replace(f"#(TGWT0001.DAHE@{code})", str(float(value_map[code])))
                    safe_expr = safe_expr.replace(f"#(TGMT0001.DAHE@{code})", str(float(value_map[code])))
                if "#(" in safe_expr:
                    continue
                results[item["sim_var"]] = float(eval(safe_expr, {"__builtins__": {}}, {}))
            except Exception:
                continue
        return results

    def is_local_injection_target(self, host, port):
        host_text = str(host).strip().lower()
        normalized_host = '127.0.0.1' if host_text in ('localhost', '0.0.0.0') else host_text
        return (normalized_host, int(port)) in self.local_injection_targets

    def is_param_allowed(self, param_name):
        """
        双轨匹配：先精确匹配，再按安全规则进行数字后缀匹配。
        """
        # 1. 精确匹配 (优先级最高)
        if param_name in self.filter_params:
            return True, param_name

        # 2. 数字后缀匹配安全检查
        # 只有特定的前缀组允许互相转换（如 K0029 <=> Y0029）
        # 严禁将随机参数误匹配到时间码 (S0067) 等关键字段
        SAFE_GROUPS = [{'K', 'Y', 'A'}, {'B', 'R'}]
        # 禁止任何模糊匹配劫持的 ID 列表
        FORBIDDEN_FUZZY = {'S0067', 'DCSM34', 'A024', 'A025', 'A026', 'A027', 'A028'}

        if len(param_name) >= 2:
            prefix = param_name[0].upper()
            num = param_name[1:]
            
            if num in self.filter_numeric:
                matches = self.filter_num_to_code.get(num, [])
                if isinstance(matches, list):
                    for target_id in matches:
                        if target_id in FORBIDDEN_FUZZY: continue
                        
                        target_prefix = target_id[0].upper()
                        # 检查前缀是否属于同一个安全变体组
                        for group in SAFE_GROUPS:
                            if prefix in group and target_prefix in group:
                                return True, target_id

        return False, None
