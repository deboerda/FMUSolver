from PIL import Image
import os

ico_path = 'fmusolver.ico'
new_ico_path = 'fmusolver_fixed.ico'

if os.path.exists(ico_path):
    img = Image.open(ico_path)
    # Ensure it's RGBA
    img = img.convert("RGBA")
    
    # Save with multiple sizes to ensure Windows preview works
    img.save(new_ico_path, format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
    print(f"Icon fixed and saved to {new_ico_path}")
else:
    print(f"Error: {ico_path} not found")
