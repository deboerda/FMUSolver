import xml.etree.ElementTree as ET
import configparser
import os
import re

class ConfigManager:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.config_ini_path = os.path.join(root_dir, "config.ini")
        self.param_filter_path = os.path.join(root_dir, "ParamFilter.xml")
        self.filter_params = set()       # 原始 code 集合（完整匹配）
        self.filter_numeric = set()      # 数字后缀集合（去前缀匹配）
        self.filter_num_to_code = {}     # 数字后缀 -> 原始code 映射（用于调试）
        self.telemetry_to_sim_map = {}    # 遥测 code/parId -> FMU sim_var
        self.targets = []
        self.config = {}

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
                def add_target(host, port):
                    target = (str(host), int(port))
                    if target not in self.targets:
                        self.targets.append(target)

                if pe_ip and pe_port:
                    add_target(pe_ip, pe_port)
                    print(f"[*] Unified PE target from FmuSolver UI: {pe_ip}:{pe_port}")

                    local_inject_port = os.environ.get('FMUSOLVER_LOCAL_INJECT_PORT', '').strip()
                    if local_inject_port:
                        add_target('127.0.0.1', local_inject_port)
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
            self.load_relationship_mapping()

        except Exception as e:
            print(f"[!] Error parsing ParamFilter.xml: {e}")

    def load_relationship_mapping(self):
        candidates = [
            os.path.join(self.root_dir, "DTS.TM.Sim.Relationship.xml"),
            os.path.join(os.path.dirname(self.root_dir), "DTS.TM.Sim.Relationship.xml"),
        ]
        rel_path = next((p for p in candidates if os.path.exists(p)), None)
        if not rel_path:
            print("[*] Telemetry relationship XML not found; using raw telemetry codes.")
            return
        try:
            root = ET.parse(rel_path).getroot()
            for var in root.findall('.//Var'):
                sim_var = (var.get('sim_var') or '').strip()
                expr = var.get('expression') or ''
                if not sim_var:
                    continue
                codes = re.findall(r'@([A-Za-z0-9_]+)\)', expr)
                # Only direct one-to-one expressions can be safely renamed here.
                if len(codes) != 1:
                    continue
                code = codes[0].strip()
                self.telemetry_to_sim_map[code] = sim_var
            print(f"[*] Loaded {len(self.telemetry_to_sim_map)} telemetry->sim variable mappings from {rel_path}")
        except Exception as e:
            print(f"[!] Error parsing telemetry relationship XML: {e}")

    def map_to_sim_var(self, telemetry_code):
        return self.telemetry_to_sim_map.get(telemetry_code, telemetry_code)

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
