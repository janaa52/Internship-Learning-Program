import cv2
import face_recognition
from database import get_connection


# ============================================================
# SETTINGS
# ============================================================

RECOGNITION_THRESHOLD = 0.50


# ============================================================
# START PROGRAM
# ============================================================

print("Recognition system starting...")


# ============================================================
# LOAD EMPLOYEES FROM DATABASE
# ============================================================

conn = get_connection()
cursor = conn.cursor()

cursor.execute("""
    SELECT employee_id, employee_code, full_name
    FROM employees
    WHERE is_active = TRUE
""")

employees = cursor.fetchall()

print("\nEmployees in database:")

for employee in employees:
    print(employee)

cursor.close()
conn.close()


# ============================================================
# OPEN CAMERA
# ============================================================

video_capture = cv2.VideoCapture(0)

if not video_capture.isOpened():

    print("Could not open camera.")
    exit()


print("\nCamera opened successfully.")
print("Looking for faces...")
print("Press 'q' to quit.")


# ============================================================
# MAIN RECOGNITION LOOP
# ============================================================

while True:

    # --------------------------------------------------------
    # Read camera frame
    # --------------------------------------------------------

    ret, frame = video_capture.read()

    if not ret:

        print("Could not read from camera.")
        break

    # Mirror image
    frame = cv2.flip(frame, 1)

    # Convert BGR → RGB
    rgb_frame = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )


    # --------------------------------------------------------
    # Detect faces
    # --------------------------------------------------------

    face_locations = face_recognition.face_locations(
        rgb_frame
    )


    # --------------------------------------------------------
    # Create face embeddings
    # --------------------------------------------------------

    face_encodings = face_recognition.face_encodings(
        rgb_frame,
        face_locations
    )


    # ========================================================
    # PROCESS EACH FACE
    # ========================================================

    for face_location, face_encoding in zip(
        face_locations,
        face_encodings
    ):

        # ----------------------------------------------------
        # Face coordinates
        # ----------------------------------------------------

        top, right, bottom, left = face_location


        # ----------------------------------------------------
        # Convert embedding to pgvector format
        # ----------------------------------------------------

        embedding_string = "[" + ",".join(
            str(value) for value in face_encoding
        ) + "]"


        # ----------------------------------------------------
        # Connect to database
        # ----------------------------------------------------

        conn = get_connection()
        cursor = conn.cursor()


        # ----------------------------------------------------
        # Search for closest employee
        # ----------------------------------------------------

        cursor.execute(
            """
            WITH query AS (
                SELECT %s::vector AS embedding
            )

            SELECT
                fe.employee_id,
                e.employee_code,
                e.full_name,
                fe.embedding <-> query.embedding AS distance

            FROM face_embeddings fe

            JOIN employees e
                ON e.employee_id = fe.employee_id

            CROSS JOIN query

            WHERE e.is_active = TRUE

            ORDER BY fe.embedding <-> query.embedding

            LIMIT 1;
            """,
            (embedding_string,)
        )


        result = cursor.fetchone()


        # ----------------------------------------------------
        # Close database connection
        # ----------------------------------------------------

        cursor.close()
        conn.close()


        # ====================================================
        # CHECK MATCH
        # ====================================================

        if result:

            employee_id = result[0]
            employee_code = result[1]
            full_name = result[2]
            distance = result[3]


            print(
                f"Closest employee: {full_name} | "
                f"Distance: {distance:.4f}"
            )


            # =================================================
            # RECOGNIZED
            # =================================================

            if distance <= RECOGNITION_THRESHOLD:

                print(
                    f"Recognized: {full_name}"
                )


                # Green rectangle

                cv2.rectangle(
                    frame,
                    (left, top),
                    (right, bottom),
                    (0, 255, 0),
                    2
                )


                # Employee name

                cv2.putText(
                    frame,
                    f"{full_name} ({distance:.2f})",
                    (left, top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )


            # =================================================
            # UNKNOWN
            # =================================================

            else:

                print("Unknown person")


                # Red rectangle

                cv2.rectangle(
                    frame,
                    (left, top),
                    (right, bottom),
                    (0, 0, 255),
                    2
                )


                # Unknown label

                cv2.putText(
                    frame,
                    f"Unknown ({distance:.2f})",
                    (left, top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2
                )


        # ====================================================
        # NO DATABASE RESULT
        # ====================================================

        else:

            print(
                "No employees found in database."
            )


            cv2.rectangle(
                frame,
                (left, top),
                (right, bottom),
                (0, 0, 255),
                2
            )


            cv2.putText(
                frame,
                "Unknown",
                (left, top - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )


    # ========================================================
    # SHOW CAMERA
    # ========================================================

    cv2.imshow(
        "Employee Recognition",
        frame
    )


    # --------------------------------------------------------
    # Quit with Q
    # --------------------------------------------------------

    if cv2.waitKey(1) & 0xFF == ord("q"):

        break


# ============================================================
# CLEANUP
# ============================================================

video_capture.release()

cv2.destroyAllWindows()