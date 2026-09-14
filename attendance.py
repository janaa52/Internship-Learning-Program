import cv2
import face_recognition
from database import get_connection
import time
import tkinter as tk
from tkinter import messagebox


# ============================================================
# SETTINGS
# ============================================================

RECOGNITION_THRESHOLD = 0.50

# Prevent the same person from triggering the system
# repeatedly within a short period.
COOLDOWN_SECONDS = 5


# ============================================================
# POPUP FUNCTION
# ============================================================

def show_popup(title, message):

    root = tk.Tk()

    root.withdraw()

    messagebox.showinfo(
        title,
        message
    )

    root.destroy()


# ============================================================
# ATTENDANCE FUNCTION
# ============================================================

def process_attendance(employee_id, full_name):

    conn = get_connection()
    cursor = conn.cursor()

    # --------------------------------------------------------
    # Find the employee's most recent attendance event
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT event_type, timestamp
        FROM attendance
        WHERE employee_id = %s
        ORDER BY timestamp DESC, attendance_id DESC
        LIMIT 1
        """,
        (employee_id,)
    )

    last_record = cursor.fetchone()


    # ========================================================
    # NO PREVIOUS ATTENDANCE
    # ========================================================

    if last_record is None:

        event_type = "IN"

        cursor.execute(
            """
            INSERT INTO attendance
            (employee_id, event_type)
            VALUES (%s, %s)
            """,
            (employee_id, event_type)
        )

        conn.commit()

        cursor.close()
        conn.close()

        print(
            f"{full_name} punched IN."
        )

        show_popup(
            "Punch In Successful",
            f"{full_name}\n\nYou have successfully punched IN."
        )

        return "IN"


    # ========================================================
    # GET LAST EVENT
    # ========================================================

    last_event = last_record[0]


    # ========================================================
    # LAST EVENT = IN
    # ========================================================

    if last_event == "IN":

        # ----------------------------------------------------
        # Another IN is invalid
        # ----------------------------------------------------

        print(
            f"{full_name} is already punched IN."
        )

        cursor.close()
        conn.close()

        show_popup(
            "Already Punched In",
            f"{full_name}\n\nYou have already punched IN."
        )

        return "ALREADY_IN"


    # ========================================================
    # LAST EVENT = OUT
    # ========================================================

    elif last_event == "OUT":

        # ----------------------------------------------------
        # A new IN is valid
        #
        # BUT:
        # We need to know whether the user is trying to
        # punch IN or OUT.
        #
        # For now, this function receives the desired action
        # from the interface.
        # ----------------------------------------------------

        cursor.close()
        conn.close()

        return "OUT_STATE"


# ============================================================
# MAIN ATTENDANCE ACTION
# ============================================================

def punch(employee_id, full_name, requested_event):

    conn = get_connection()
    cursor = conn.cursor()

    # --------------------------------------------------------
    # Get most recent attendance record
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT event_type, timestamp
        FROM attendance
        WHERE employee_id = %s
        ORDER BY timestamp DESC, attendance_id DESC
        LIMIT 1
        """,
        (employee_id,)
    )

    last_record = cursor.fetchone()


    # ========================================================
    # NO PREVIOUS RECORD
    # ========================================================

    if last_record is None:

        if requested_event == "IN":

            cursor.execute(
                """
                INSERT INTO attendance
                (employee_id, event_type)
                VALUES (%s, 'IN')
                """,
                (employee_id,)
            )

            conn.commit()

            cursor.close()
            conn.close()

            show_popup(
                "Punch In Successful",
                f"{full_name}\n\nYou have successfully punched IN."
            )

            print(
                f"{full_name}: IN recorded"
            )

            return True

        else:

            cursor.close()
            conn.close()

            show_popup(
                "Cannot Punch Out",
                f"{full_name}\n\n"
                "You have not punched IN yet."
            )

            print(
                f"{full_name}: OUT rejected"
            )

            return False


    # ========================================================
    # LAST EVENT = IN
    # ========================================================

    if last_record[0] == "IN":

        # ----------------------------------------------------
        # IN while already IN
        # ----------------------------------------------------

        if requested_event == "IN":

            cursor.close()
            conn.close()

            show_popup(
                "Already Punched In",
                f"{full_name}\n\n"
                "You have already punched IN."
            )

            print(
                f"{full_name}: duplicate IN rejected"
            )

            return False


        # ----------------------------------------------------
        # OUT after IN
        # ----------------------------------------------------

        elif requested_event == "OUT":

            cursor.execute(
                """
                INSERT INTO attendance
                (employee_id, event_type)
                VALUES (%s, 'OUT')
                """,
                (employee_id,)
            )

            conn.commit()

            cursor.close()
            conn.close()

            show_popup(
                "Punch Out Successful",
                f"{full_name}\n\n"
                "You have successfully punched OUT."
            )

            print(
                f"{full_name}: OUT recorded"
            )

            return True


    # ========================================================
    # LAST EVENT = OUT
    # ========================================================

    if last_record[0] == "OUT":

        # ----------------------------------------------------
        # IN after OUT
        # ----------------------------------------------------

        if requested_event == "IN":

            cursor.execute(
                """
                INSERT INTO attendance
                (employee_id, event_type)
                VALUES (%s, 'IN')
                """,
                (employee_id,)
            )

            conn.commit()

            cursor.close()
            conn.close()

            show_popup(
                "Punch In Successful",
                f"{full_name}\n\n"
                "You have successfully punched IN."
            )

            print(
                f"{full_name}: IN recorded"
            )

            return True


        # ----------------------------------------------------
        # OUT after OUT
        # ----------------------------------------------------

        elif requested_event == "OUT":

            cursor.execute(
                """
                INSERT INTO attendance
                (employee_id, event_type)
                VALUES (%s, 'OUT')
                """,
                (employee_id,)
            )

            conn.commit()

            cursor.close()
            conn.close()

            show_popup(
                "Punch Out Successful",
                f"{full_name}\n\n"
                "Your latest punch OUT has been recorded."
            )

            print(
                f"{full_name}: OUT recorded"
            )

            return True


    cursor.close()
    conn.close()

    return False


# ============================================================
# CAMERA
# ============================================================

print("Attendance recognition system starting...")


video_capture = cv2.VideoCapture(0)

if not video_capture.isOpened():

    print("Could not open camera.")
    exit()


print("\nCamera opened successfully.")
print("Press 'i' to punch IN.")
print("Press 'o' to punch OUT.")
print("Press 'q' to quit.")


# ============================================================
# STATE
# ============================================================

last_action_time = {}


# ============================================================
# MAIN LOOP
# ============================================================

while True:

    ret, frame = video_capture.read()

    if not ret:

        print("Could not read from camera.")
        break


    frame = cv2.flip(frame, 1)


    # --------------------------------------------------------
    # Convert BGR → RGB
    # --------------------------------------------------------

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
    # Create embeddings
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

        top, right, bottom, left = face_location


        # ----------------------------------------------------
        # Convert embedding to pgvector format
        # ----------------------------------------------------

        embedding_string = "[" + ",".join(
            str(value) for value in face_encoding
        ) + "]"


        # ----------------------------------------------------
        # Search database
        # ----------------------------------------------------

        conn = get_connection()
        cursor = conn.cursor()


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


        cursor.close()
        conn.close()


        # ====================================================
        # EMPLOYEE FOUND
        # ====================================================

        if result:

            employee_id = result[0]
            employee_code = result[1]
            full_name = result[2]
            distance = result[3]


            # ------------------------------------------------
            # Check recognition threshold
            # ------------------------------------------------

            if distance <= RECOGNITION_THRESHOLD:


                # ------------------------------------------------
                # Green rectangle
                # ------------------------------------------------

                cv2.rectangle(
                    frame,
                    (left, top),
                    (right, bottom),
                    (0, 255, 0),
                    2
                )


                cv2.putText(
                    frame,
                    f"{full_name} ({distance:.2f})",
                    (left, top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )


                # ------------------------------------------------
                # Keyboard controls
                # ------------------------------------------------

                key = cv2.waitKey(1) & 0xFF


                # =================================================
                # PUNCH IN
                # =================================================

                if key == ord("i"):

                    current_time = time.time()

                    last_time = last_action_time.get(
                        employee_id,
                        0
                    )


                    if current_time - last_time >= COOLDOWN_SECONDS:

                        punch(
                            employee_id,
                            full_name,
                            "IN"
                        )

                        last_action_time[
                            employee_id
                        ] = current_time


                # =================================================
                # PUNCH OUT
                # =================================================

                elif key == ord("o"):

                    current_time = time.time()

                    last_time = last_action_time.get(
                        employee_id,
                        0
                    )


                    if current_time - last_time >= COOLDOWN_SECONDS:

                        punch(
                            employee_id,
                            full_name,
                            "OUT"
                        )

                        last_action_time[
                            employee_id
                        ] = current_time


            # ====================================================
            # UNKNOWN PERSON
            # ====================================================

            else:

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
    # INSTRUCTIONS ON SCREEN
    # ========================================================

    cv2.putText(
        frame,
        "Press I = IN | O = OUT | Q = Quit",
        (20, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2
    )


    # ========================================================
    # SHOW CAMERA
    # ========================================================

    cv2.imshow(
        "Employee Attendance",
        frame
    )


    # ========================================================
    # QUIT
    # ========================================================

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):

        break


# ============================================================
# CLEANUP
# ============================================================

video_capture.release()

cv2.destroyAllWindows()