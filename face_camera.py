import cv2
import face_recognition
import os
import numpy as np


# ==========================================
# 1. LOAD REGISTERED EMPLOYEES
# ==========================================

KNOWN_FACES_DIR = "faces"

known_face_encodings = []
known_face_names = []


print("Loading registered employees...")

for filename in os.listdir(KNOWN_FACES_DIR):

    # Only process image files
    if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
        continue

    image_path = os.path.join(KNOWN_FACES_DIR, filename)

    # Load image
    image = face_recognition.load_image_file(image_path)

    # Generate face encoding
    encodings = face_recognition.face_encodings(image)

    if len(encodings) == 0:
        print(f"WARNING: No face found in {filename}")
        continue

    # Use the first face found
    encoding = encodings[0]

    # Employee name = filename without extension
    name = os.path.splitext(filename)[0]

    known_face_encodings.append(encoding)
    known_face_names.append(name)

    print(f"Loaded employee: {name}")


print(f"\nTotal employees loaded: {len(known_face_names)}")


# ==========================================
# 2. OPEN CAMERA
# ==========================================

video_capture = cv2.VideoCapture(0)

if not video_capture.isOpened():
    print("ERROR: Could not open camera.")
    exit()


print("\nCamera started.")
print("Press Q to quit.")


# ==========================================
# 3. PROCESS CAMERA
# ==========================================

while True:

    ret, frame = video_capture.read()

    if not ret:
        print("Could not read camera frame.")
        break

    # Convert BGR → RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Find faces
    face_locations = face_recognition.face_locations(rgb_frame)

    # Generate encodings for detected faces
    face_encodings = face_recognition.face_encodings(
        rgb_frame,
        face_locations
    )

    # ==========================================
    # 4. RECOGNIZE EACH FACE
    # ==========================================

    for face_encoding, face_location in zip(
        face_encodings,
        face_locations
    ):

        # Compare with registered employees
        matches = face_recognition.compare_faces(
            known_face_encodings,
            face_encoding,
            tolerance=0.5
        )

        name = "Unknown"

        # Calculate distances
        face_distances = face_recognition.face_distance(
            known_face_encodings,
            face_encoding
        )

        if len(face_distances) > 0:

            best_match_index = np.argmin(face_distances)

            if matches[best_match_index]:
                name = known_face_names[best_match_index]

        # ==========================================
        # 5. DRAW FACE BOX
        # ==========================================

        top, right, bottom, left = face_location

        cv2.rectangle(
            frame,
            (left, top),
            (right, bottom),
            (0, 255, 0),
            2
        )

        # ==========================================
        # 6. DISPLAY NAME
        # ==========================================

        cv2.rectangle(
            frame,
            (left, bottom - 35),
            (right, bottom),
            (0, 255, 0),
            cv2.FILLED
        )

        cv2.putText(
            frame,
            name,
            (left + 6, bottom - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 0),
            2
        )

    # ==========================================
    # 7. SHOW CAMERA
    # ==========================================

    cv2.imshow(
        "Face Recognition",
        frame
    )

    # Press Q to quit
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


# ==========================================
# 8. CLEAN UP
# ==========================================

video_capture.release()
cv2.destroyAllWindows()