from PIL import Image
import os

ico_path = 'fmusolver.ico'
output_ico = 'fmusolver_full.ico'

if os.path.exists(ico_path):
    img = Image.open(ico_path)
    # Scale up to 256x256 to ensure Windows picks it up for all preview sizes
    img_256 = img.resize((256, 256), Image.Resampling.LANCZOS)
    
    # Save with all sizes, forcing PNG compression for 256 if possible (Pillow handles this)
    img_256.save(output_ico, format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
    print(f"Full-size icon saved to {output_ico}")
else:
    print("fmusolver.ico not found")
