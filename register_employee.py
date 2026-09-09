import cv2
import face_recognition
from database import get_connection
import time


def register_employee():
    # -----------------------------------
    # 1. Get employee information
    # -----------------------------------
    employee_code = input("Enter employee code: ")
    full_name = input("Enter employee name: ")
    department = input("Enter department: ")
    position = input("Enter position: ")

    # -----------------------------------
    # 2. Open database connection
    # -----------------------------------
    conn = get_connection()
    cursor = conn.cursor()

    # -----------------------------------
    # 3. Check if employee code already exists
    # -----------------------------------
    cursor.execute(
        "SELECT employee_id FROM employees WHERE employee_code = %s",
        (employee_code,)
    )

    existing_employee = cursor.fetchone()

    if existing_employee:
        print("An employee with this employee code already exists.")
        cursor.close()
        conn.close()
        return

    # -----------------------------------
    # 4. Open webcam
    # -----------------------------------
    video_capture = cv2.VideoCapture(0)

    if not video_capture.isOpened():
        print("Could not open camera.")
        cursor.close()
        conn.close()
        return

    print("\nCamera opened.")
    print("Look at the camera.")
    print("We will capture 5 face samples.")
    print("Press 'q' to cancel.\n")

    embeddings = []

    last_capture_time = 0

    while len(embeddings) < 5:

        ret, frame = video_capture.read()

        if not ret:
            print("Could not read from camera.")
            break

        # Mirror the camera image
        frame = cv2.flip(frame, 1)

        # Convert BGR → RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect faces
        face_locations = face_recognition.face_locations(rgb_frame)

        # Draw rectangles around detected faces
        for top, right, bottom, left in face_locations:
            cv2.rectangle(
                frame,
                (left, top),
                (right, bottom),
                (0, 255, 0),
                2
            )

        # Only capture if exactly one face is visible
        if len(face_locations) == 1:

            current_time = time.time()

            # Wait 0.7 seconds between samples
            if current_time - last_capture_time > 0.7:

                # Generate face encoding
                face_encodings = face_recognition.face_encodings(
                    rgb_frame,
                    face_locations
                )

                if face_encodings:

                    embedding = face_encodings[0]

                    embeddings.append(embedding)

                    last_capture_time = current_time

                    print(
                        f"Captured face sample "
                        f"{len(embeddings)}/5"
                    )

        elif len(face_locations) > 1:

            cv2.putText(
                frame,
                "Only one person should be visible",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

        else:

            cv2.putText(
                frame,
                "No face detected",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

        # Show progress
        cv2.putText(
            frame,
            f"Samples: {len(embeddings)}/5",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        cv2.imshow("Employee Registration", frame)

        # Press q to cancel
        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("Registration cancelled.")
            video_capture.release()
            cv2.destroyAllWindows()
            cursor.close()
            conn.close()
            return

    # -----------------------------------
    # 5. Close camera
    # -----------------------------------
    video_capture.release()
    cv2.destroyAllWindows()

    # Make sure we actually captured 5 samples
    if len(embeddings) < 5:
        print("Registration failed: not enough face samples.")
        cursor.close()
        conn.close()
        return

    # -----------------------------------
    # 6. Create employee record
    # -----------------------------------
    cursor.execute(
        """
        INSERT INTO employees
        (employee_code, full_name, department, position)
        VALUES (%s, %s, %s, %s)
        RETURNING employee_id
        """,
        (
            employee_code,
            full_name,
            department,
            position
        )
    )

    employee_id = cursor.fetchone()[0]

    # -----------------------------------
    # 7. Save all face embeddings
    # -----------------------------------
    for embedding in embeddings:

        embedding_string = "[" + ",".join(
            str(value) for value in embedding
        ) + "]"

        cursor.execute(
            """
            INSERT INTO face_embeddings
            (employee_id, embedding)
            VALUES (%s, %s::vector)
            """,
            (
                employee_id,
                embedding_string
            )
        )

    # -----------------------------------
    # 8. Save everything permanently
    # -----------------------------------
    conn.commit()

    # -----------------------------------
    # 9. Close database connection
    # -----------------------------------
    cursor.close()
    conn.close()

    print("\n--------------------------------")
    print("Employee registered successfully!")
    print(f"Employee ID: {employee_id}")
    print(f"Name: {full_name}")
    print(f"Face samples: {len(embeddings)}")
    print("--------------------------------")


if __name__ == "__main__":
    register_employee()