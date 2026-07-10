import datetime
import json
import os
import re


APP_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_FILE = os.path.join(APP_DIR, "FmuLauncherUniversal.py")
PACKAGE_FILE = os.path.abspath(os.path.join(APP_DIR, "..", "FmuSolver_Package", "FmuLauncherUniversal.py"))
VERSION_FILE = os.path.join(APP_DIR, "build_version.json")


def make_version():
    now = datetime.datetime.now()
    return f"v{now:%y.%m%d.%H%M}"


def update_file(path, version):
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    new_text, count = re.subn(r'APP_VERSION\s*=\s*"[^"]+"', f'APP_VERSION = "{version}"', text, count=1)
    if count <= 0:
        raise RuntimeError(f"APP_VERSION not found in {path}")
    if new_text != text:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(new_text)
    return True


def main():
    version = make_version()
    update_file(SOURCE_FILE, version)
    update_file(PACKAGE_FILE, version)
    with open(VERSION_FILE, "w", encoding="utf-8", newline="") as f:
        json.dump({"version": version, "generated_at": datetime.datetime.now().isoformat(timespec="seconds")}, f, ensure_ascii=False, indent=2)
    print(f"[BUILD_VERSION] APP_VERSION={version}")


if __name__ == "__main__":
    main()
