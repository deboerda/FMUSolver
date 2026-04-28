import xml.etree.ElementTree as ET
import configparser
import os

class ConfigManager:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.config_ini_path = os.path.join(root_dir, "config.ini")
        self.param_filter_path = os.path.join(root_dir, "ParamFilter.xml")
        self.filter_params = set()       # 原始 code 集合（完整匹配）
        self.filter_numeric = set()      # 数字后缀集合（去前缀匹配）
        self.filter_num_to_code = {}     # 数字后缀 -> 原始code 映射（用于调试）
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

                # 读取双目标配置
                t1_ip = common.get('Target1_IP', '127.0.0.1')
                t1_port = int(common.get('Target1_Port', '8888'))
                self.targets.append((t1_ip, t1_port))

                t2_ip = common.get('Target2_IP', '127.0.0.1')
                t2_port = int(common.get('Target2_Port', '8890'))
                self.targets.append((t2_ip, t2_port))
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
                        self.filter_num_to_code[num] = code

            # 情况2: 匹配 <Item name="xxx" ... /> (开发版)
            for item in root.findall('Item'):
                name = item.get('name')
                if name:
                    self.filter_params.add(name)
                    if len(name) >= 2:
                        num = name[1:]
                        self.filter_numeric.add(num)
                        self.filter_num_to_code[num] = name

            print(f"[*] Loaded {len(self.filter_params)} parameters for filtering.")
            print(f"[*] Numeric-suffix index built: {len(self.filter_numeric)} entries.")

        except Exception as e:
            print(f"[!] Error parsing ParamFilter.xml: {e}")

    def is_param_allowed(self, param_name):
        """
        双轨匹配：先精确匹配，再按数字后缀匹配。
        返回值: (is_allowed: bool, matched_code: str or None)
        """
        # 精确匹配
        if param_name in self.filter_params:
            return True, param_name

        # 数字后缀匹配（忽略第一个字母前缀）
        if len(param_name) >= 2:
            num = param_name[1:]
            if num in self.filter_numeric:
                return True, self.filter_num_to_code.get(num, param_name)

        return False, None
