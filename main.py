import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import pyautogui
import math
import time

# 1. Configure the new Tasks API to use the external model file
base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.VIDEO, # Required for webcam feeds
    num_hands=1)

# Initialize the detector
detector = vision.HandLandmarker.create_from_options(options)

cap = cv2.VideoCapture(0)
screen_width, screen_height = pyautogui.size()
last_click_time = 0

# The new API requires exact timestamps for every frame
start_time = time.time()

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break
        
    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # 2. Convert standard image to MediaPipe Image format
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    timestamp_ms = int((time.time() - start_time) * 1000)
    
    # 3. Process the frame using the new video detection method
    result = detector.detect_for_video(mp_image, timestamp_ms)
    
    # 4. Extract landmarks using the new data structure
    if result.hand_landmarks:
        for hand_landmarks in result.hand_landmarks:
            index_tip = hand_landmarks[8]
            thumb_tip = hand_landmarks[4]
            
            mouse_x = int(index_tip.x * screen_width)
            mouse_y = int(index_tip.y * screen_height)
            
            pyautogui.moveTo(mouse_x, mouse_y)
            
            thumb_x = int(thumb_tip.x * screen_width)
            thumb_y = int(thumb_tip.y * screen_height)
            
            distance = math.hypot(mouse_x - thumb_x, mouse_y - thumb_y)
            
            current_time = time.time()
            if distance < 40:
                if current_time - last_click_time > 0.5:
                    pyautogui.click()
                    last_click_time = current_time
                    
    cv2.imshow("Touchless Interface (v1.0.1)", frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()