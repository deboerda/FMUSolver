import os
import runpy


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, "yaocetest", "send_full_telemetry.py")
    runpy.run_path(target, run_name="__main__")
