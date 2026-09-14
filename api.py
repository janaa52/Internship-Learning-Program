import base64
import io
from datetime import timezone

import cv2
import face_recognition
import numpy as np
from flask import Flask, jsonify, request
from flask_cors import CORS

from database import get_connection

app = Flask(__name__)
CORS(app)
RECOGNITION_THRESHOLD = 0.60


def utc_iso(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def image_from_payload(payload):
    encoded = payload.get("image", "")
    if "," in encoded:
        encoded = encoded.split(",", 1)[1]
    image_bytes = base64.b64decode(encoded)
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The camera image could not be decoded.")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def single_encoding(image):
    locations = face_recognition.face_locations(image)
    if len(locations) != 1:
        raise ValueError("Show exactly one face to the camera.")
    encodings = face_recognition.face_encodings(image, locations)
    if not encodings:
        raise ValueError("No usable face was found in the image.")
    return encodings[0]


def vector(encoding):
    return "[" + ",".join(str(value) for value in encoding) + "]"


def find_employee(cursor, encoding):
    cursor.execute(
        """
        WITH query AS (SELECT %s::vector AS embedding)
        SELECT fe.employee_id, e.employee_code, e.full_name,
               fe.embedding <-> query.embedding AS distance
        FROM face_embeddings fe
        JOIN employees e ON e.employee_id = fe.employee_id
        CROSS JOIN query
        WHERE e.is_active = TRUE
        ORDER BY fe.embedding <-> query.embedding
        LIMIT 1
        """,
        (vector(encoding),),
    )
    result = cursor.fetchone()
    if not result or float(result[3]) > RECOGNITION_THRESHOLD:
        return None
    return {"employee_id": result[0], "staffId": result[1], "name": result[2], "distance": float(result[3])}


@app.get("/api/health")
def health():
    try:
        conn = get_connection()
        conn.close()
        return jsonify({"ok": True, "database": "connected"})
    except Exception as error:
        return jsonify({"ok": False, "database": "unavailable", "error": str(error)}), 503


@app.get("/api/attendance/status")
def attendance_status():
    employee_code = request.args.get("employee_code", "").strip()
    if not employee_code:
        return jsonify({"error": "Employee code is required."}), 400
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT employee_id FROM employees WHERE employee_code = %s AND is_active = TRUE", (employee_code,))
        employee = cursor.fetchone()
        if not employee:
            cursor.close()
            conn.close()
            return jsonify({"error": "Employee not found."}), 404
        cursor.execute(
            """
            SELECT event_type, timestamp
            FROM attendance
            WHERE employee_id = %s
            ORDER BY timestamp DESC, attendance_id DESC
            LIMIT 1
            """,
            (employee[0],),
        )
        latest = cursor.fetchone()
        cursor.close()
        conn.close()
        if not latest:
            return jsonify({"lastEvent": None, "inAt": None, "outAt": None, "totalMinutes": 0})
        event, timestamp = latest
        return jsonify({
            "lastEvent": event.lower(),
            "inAt": utc_iso(timestamp) if event == "IN" else None,
            "outAt": utc_iso(timestamp) if event == "OUT" else None,
            "totalMinutes": 0,
        })
    except Exception as error:
        return jsonify({"error": str(error)}), 503


@app.post("/api/register")
def register():
    payload = request.get_json(silent=True) or {}
    required = ("employee_code", "full_name", "department", "position", "image")
    if any(not payload.get(key) for key in required):
        return jsonify({"error": "Employee details and a face image are required."}), 400
    try:
        encoding = single_encoding(image_from_payload(payload))
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT employee_id FROM employees WHERE employee_code = %s", (payload["employee_code"],))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "That employee code already exists."}), 409
        cursor.execute(
            """
            INSERT INTO employees (employee_code, full_name, department, position)
            VALUES (%s, %s, %s, %s) RETURNING employee_id
            """,
            (payload["employee_code"], payload["full_name"], payload["department"], payload["position"]),
        )
        employee_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO face_embeddings (employee_id, embedding) VALUES (%s, %s::vector)",
            (employee_id, vector(encoding)),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"employee_id": employee_id, "name": payload["full_name"], "staffId": payload["employee_code"]}), 201
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        return jsonify({"error": str(error)}), 503


@app.post("/api/attendance")
def attendance():
    payload = request.get_json(silent=True) or {}
    requested_event = payload.get("event", "").upper()
    expected_code = payload.get("employee_code", "").strip()
    if requested_event not in ("IN", "OUT") or not payload.get("image") or not expected_code:
        return jsonify({"error": "A face image, employee code, and event IN or OUT are required."}), 400
    try:
        encoding = single_encoding(image_from_payload(payload))
        conn = get_connection()
        cursor = conn.cursor()
        employee = find_employee(cursor, encoding)
        if not employee:
            cursor.close()
            conn.close()
            return jsonify({"error": "Face not recognized."}), 401
        if employee["staffId"] != expected_code:
            cursor.close()
            conn.close()
            return jsonify({
                "error": f"Face belongs to {employee['name']}, not employee {expected_code}.",
                "recognized_employee": employee,
            }), 409
        cursor.execute(
            "SELECT event_type, timestamp FROM attendance WHERE employee_id = %s ORDER BY timestamp DESC, attendance_id DESC LIMIT 1",
            (employee["employee_id"],),
        )
        last = cursor.fetchone()
        if requested_event == "OUT" and not last:
            cursor.close()
            conn.close()
            return jsonify({"error": "You have not punched in yet."}), 409
        if last and last[0] == requested_event and requested_event == "IN":
            cursor.close()
            conn.close()
            return jsonify({"error": "You are already punched in."}), 409
        cursor.execute("INSERT INTO attendance (employee_id, event_type) VALUES (%s, %s) RETURNING timestamp", (employee["employee_id"], requested_event))
        timestamp = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"employee": employee, "event": requested_event, "timestamp": utc_iso(timestamp)})
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except Exception as error:
        return jsonify({"error": str(error)}), 503


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
