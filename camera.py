import sys
import cv2
import os
import time

# === Check for student name argument ===
if len(sys.argv) < 2:
    print("❗ Student name required as argument.")
    sys.exit()

name = sys.argv[1]
data_folder = os.path.join("data", name)
os.makedirs(data_folder, exist_ok=True)

# === Open camera ===
cam = cv2.VideoCapture(0)
if not cam.isOpened():
    print("❌ Failed to open camera.")
    sys.exit()

print(f"📷 Capturing images for student: {name}")

num_images = 5  # Number of images to capture
count = 1

while count <= num_images:
    ret, frame = cam.read()
    if not ret:
        print("⚠️ Failed to read frame.")
        continue

    # === Show live preview with countdown ===
    for i in range(3, 0, -1):
        ret, frame = cam.read()
        if not ret:
            break
        temp = frame.copy()
        cv2.putText(temp, f"Capturing in {i}...", (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        cv2.imshow("Student Capture", temp)
        cv2.waitKey(1000)

    # === Final capture ===
    ret, frame = cam.read()
    if ret:
        img_path = os.path.join(data_folder, f"{count}.png")
        cv2.imwrite(img_path, frame)
        print(f"✅ Saved image {count} as {img_path}")
        count += 1
        cv2.imshow("Student Capture", frame)
        cv2.waitKey(500)
    else:
        print("⚠️ Error capturing image.")

cam.release()
cv2.destroyAllWindows()
print("🎉 Capture complete.")
