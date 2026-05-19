from PIL import Image, ImageDraw

# Create a high-res square with some color to test
img = Image.new('RGBA', (256, 256), color=(0, 120, 215, 255))
d = ImageDraw.Draw(img)
d.ellipse([50, 50, 200, 200], fill=(255, 255, 255, 255))
d.text((100, 110), "FMU", fill=(0, 120, 215, 255))

# Save as test icon
img.save('test_icon.ico', format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
print("Test icon created: test_icon.ico")
