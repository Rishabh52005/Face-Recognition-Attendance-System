import cv2
import face_recognition
import mysql.connector
import pickle
import numpy as np
from datetime import datetime

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Chugh123@",
    database="face_attendance"
)

cursor = db.cursor()

# load embeddings
cursor.execute("SELECT student_id,embedding FROM face_embeddings")

data = cursor.fetchall()

known_encodings = []
student_ids = []

for row in data:
    student_ids.append(row[0])
    known_encodings.append(pickle.loads(row[1]))

cap = cv2.VideoCapture(0)

while True:

    ret,frame = cap.read()

    rgb = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)

    faces = face_recognition.face_locations(rgb)
    encodings = face_recognition.face_encodings(rgb,faces)

    for encoding in encodings:

        matches = face_recognition.compare_faces(known_encodings,encoding)
        face_distances = face_recognition.face_distance(known_encodings,encoding)

        best_match = np.argmin(face_distances)

        if matches[best_match]:

            student_id = student_ids[best_match]

            cursor.execute("SELECT name FROM students WHERE student_id=%s", (student_id,))
            name_row = cursor.fetchone()
            name = name_row[0] if name_row else "Unknown"

            now = datetime.now()
            date = now.strftime("%Y-%m-%d")
            time = now.strftime("%H:%M:%S")

            cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id=%s AND date=%s", (student_id, date))
            count = cursor.fetchone()[0]

            if count == 0:
                cursor.execute(
                    "INSERT INTO attendance(student_id,date,time,status) VALUES(%s,%s,%s,%s)",
                    (student_id, date, time, "Present")
                )
                db.commit()
                print(f"Attendance marked for {name}")
            else:
                print(f"Attendance already marked today for {name}")

    cv2.imshow("Face Recognition",frame)

    if cv2.waitKey(1)==27:
        break

cap.release()
cv2.destroyAllWindows()