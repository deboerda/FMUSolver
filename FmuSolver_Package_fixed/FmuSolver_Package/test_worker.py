
import sys, os
APP_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
with open('c:\\Spaceship\\test_appdir.log', 'w') as f:
    f.write('APP_DIR=' + APP_DIR + '\n')
