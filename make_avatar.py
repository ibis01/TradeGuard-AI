from PIL import Image, ImageDraw

# Create 440x440 image with sharp corners (no rounded corners!)
img = Image.new('RGB', (440, 440), color='#1E293B')
draw = ImageDraw.Draw(img)

# Draw a simple, sharp-cornered robot face
draw.rectangle([100, 50, 340, 390], fill='#94A3B8') # Head
draw.rectangle([140, 150, 190, 200], fill='#0F172A') # Left Eye
draw.rectangle([250, 150, 300, 200], fill='#0F172A') # Right Eye
draw.rectangle([160, 250, 280, 280], fill='#0F172A') # Mouth
draw.rectangle([215, 20, 225, 50], fill='#94A3B8')  # Antenna Pole
draw.rectangle([205, 10, 235, 25], fill='#EF4444')  # Antenna Bulb

img.save('avatar_440.png')
print("✅ Saved compliant 440x440 avatar to avatar_440.png")
