from PIL import Image
import os

ico_path = 'fmusolver.ico'
output_ico = 'fmusolver_highres.ico'

if os.path.exists(ico_path):
    # Open the icon and pick the largest available size
    img_ico = Image.open(ico_path)
    
    # Icons often have multiple sizes. Find the largest one.
    sizes = img_ico.info.get('sizes')
    print(f"Original icon sizes: {sizes}")
    
    # Copy the largest size to a new image
    # Note: Pillow's .open() for ICO usually selects the largest by default or we can seek
    largest_img = None
    max_w = 0
    
    for i in range(getattr(img_ico, 'n_frames', 1)):
        img_ico.seek(i)
        w, h = img_ico.size
        if w >= max_w:
            max_w = w
            largest_img = img_ico.copy()
            
    if largest_img:
        print(f"Largest frame found: {largest_img.size}")
        # Resize to 256x256 if smaller, or just ensure standard sizes
        # We'll save with all standard sizes
        largest_img.save(output_ico, format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
        print(f"High-res icon saved to {output_ico}")
    else:
        print("Failed to find any frames in icon")
else:
    print("fmusolver.ico not found")
