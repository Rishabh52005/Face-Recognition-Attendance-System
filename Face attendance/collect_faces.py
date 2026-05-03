import cv2
import face_recognition
import mysql.connector
import numpy as np
import pickle

# database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Chugh123@",
    database="face_attendance"
)

cursor = db.cursor()

name = input("Enter student name: ")
roll = input("Enter roll number: ")

# insert student
cursor.execute("INSERT INTO students(name,roll_no) VALUES(%s,%s)",(name,roll))
db.commit()

student_id = cursor.lastrowid

cap = cv2.VideoCapture(0)

print("Collecting face samples...")

while True:
    ret, frame = cap.read()

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    faces = face_recognition.face_locations(rgb)

    for face in faces:

        encoding = face_recognition.face_encodings(rgb,[face])[0]

        data = pickle.dumps(encoding)

        cursor.execute(
        "INSERT INTO face_embeddings(student_id,embedding) VALUES(%s,%s)",
        (student_id,data)
        )

        db.commit()

        print("Face Stored!")

        cap.release()
        cv2.destroyAllWindows()
        exit()

    cv2.imshow("Capture Face",frame)

    if cv2.waitKey(1)==27:
        break