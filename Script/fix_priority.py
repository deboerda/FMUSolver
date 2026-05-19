from PIL import Image
import os

ico_path = 'fmusolver.ico'
output_ico = 'fmusolver_final.ico'

if os.path.exists(ico_path):
    img = Image.open(ico_path)
    img_256 = img.resize((256, 256), Image.Resampling.LANCZOS)
    
    # Try putting 256 first in the list
    img_256.save(output_ico, format='ICO', sizes=[(256,256), (128,128), (64,64), (48,48), (32,32), (16,16)])
    print(f"Final icon saved to {output_ico}")
else:
    print("fmusolver.ico not found")
