import zipfile
import platform
import os
import shutil
import xml.etree.ElementTree as ET

class FMUHandler:
    """
    独立处理 FMU 文件解压、架构识别与 modelDescription.xml 解析的模块
    """
    def __init__(self, fmu_path, extract_dir="./fmu_extracted"):
        self.fmu_path = fmu_path
        self.extract_dir = extract_dir
        self.model_description = None
        self.arch = "Unknown"

    def process(self):
        """主处理流程：解压 -> 架构识别 -> 解析描述文件"""
        if not os.path.exists(self.fmu_path):
            raise FileNotFoundError(f"FMU file not found at: {self.fmu_path}")

        # 1. 解压 FMU
        print(f"[*] Extracting FMU: {os.path.basename(self.fmu_path)} ...")
        self._extract_fmu()

        # 2. 识别架构
        self.arch = self._detect_architecture()
        print(f"[*] Detected FMU Architecture: {self.arch}")

        # 3. 校验宿主环境匹配
        self._verify_host_compatibility()

        # 4. 解析 modelDescription.xml
        self.model_description = self._parse_model_description()
        print(f"[*] Successfully parsed FMU: {self.model_description['model_name']}")
        return self.model_description

    def _extract_fmu(self):
        """将 FMU (Zip) 解压到目标目录"""
        if os.path.exists(self.extract_dir):
            shutil.rmtree(self.extract_dir)
        
        with zipfile.ZipFile(self.fmu_path, 'r') as z:
            z.extractall(self.extract_dir)

    def _detect_architecture(self):
        """
        动态识别二进制库支持的架构
        逻辑：检查 binaries 目录下的平台文件夹情况
        """
        bin_path = os.path.join(self.extract_dir, "binaries")
        if not os.path.exists(bin_path):
            return "No binaries found (Source only or invalid FMU)"

        supported = []
        # Windows 文件夹通常为 win32 / win64
        if os.path.exists(os.path.join(bin_path, "win64")):
            supported.append("win64")
        if os.path.exists(os.path.join(bin_path, "win32")):
            supported.append("win32")
        
        # Linux / MacOS 兼容逻辑
        if os.path.exists(os.path.join(bin_path, "linux64")): supported.append("linux64")
        if os.path.exists(os.path.join(bin_path, "darwin64")): supported.append("darwin64")

        return supported if supported else "Unknown"

    def _verify_host_compatibility(self):
        """验证当前 Python 解析器是否能运行该 FMU"""
        host_machine = platform.machine().lower()
        is_64bit = "64" in host_machine or "amd64" in host_machine
        host_arch = "win64" if is_64bit else "win32"

        print(f"[*] Host Machine: {host_machine} ({host_arch})")

        if isinstance(self.arch, list):
            if host_arch not in self.arch:
                print(f"[!] Warning: FMU does not explicitly support host arch {host_arch}.")
                print(f"    Available archs: {self.arch}")
            else:
                print(f"[OK] Host architecture {host_arch} is supported by this FMU.")
        else:
            print(f"[?] Architectural check skipped or failed.")

    def _parse_model_description(self):
        """解析 XML，提取模型名称、变量名、类型及引用（ValueReference）"""
        xml_path = os.path.join(self.extract_dir, "modelDescription.xml")
        if not os.path.exists(xml_path):
            raise FileNotFoundError("modelDescription.xml not found inside FMU.")

        tree = ET.parse(xml_path)
        root = tree.getroot()

        # 模型基本信息
        model_info = {
            "model_name": root.attrib.get("modelName", "Unknown"),
            "guid": root.attrib.get("guid", ""),
            "fmi_version": root.attrib.get("fmiVersion", "2.0"),
            "variables": []
        }

        # 遍历 ModelVariables
        vars_node = root.find("ModelVariables")
        if vars_node is not None:
            for var in vars_node.findall("ScalarVariable"):
                name = var.attrib.get("name")
                value_ref = var.attrib.get("valueReference")
                causality = var.attrib.get("causality", "local") # input, output, etc.

                # 提取子节点确定数据类型
                data_type = "Unknown"
                if var.find("Real") is not None: data_type = "Real"
                elif var.find("Integer") is not None: data_type = "Integer"
                elif var.find("Boolean") is not None: data_type = "Boolean"
                elif var.find("String") is not None: data_type = "String"

                model_info["variables"].append({
                    "name": name,
                    "value_reference": value_ref,
                    "type": data_type,
                    "causality": causality
                })

        return model_info

if __name__ == "__main__":
    # 测试代码 (需在此目录下放置测试用 fmu 或指定路径)
    test_fmu = os.path.join(os.getcwd(), "MyModel.fmu")
    if os.path.exists(test_fmu):
        handler = FMUHandler(test_fmu)
        res = handler.process()
        print(f"Loaded {len(res['variables'])} variables.")
    else:
        print("No test FMU found. Please set 'test_fmu' path.")
