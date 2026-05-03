CREATE DATABASE face_attendance;
USE face_attendance;
CREATE TABLE students(
    student_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),
    roll_no VARCHAR(50)
);
CREATE TABLE face_embeddings(
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT,
    embedding BLOB,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);
CREATE TABLE attendance(
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id INT,
    date DATE,
    time TIME,
    status VARCHAR(10),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
); 

CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

select * from attendance;
select * from users;

-- RBAC Update
ALTER TABLE users ADD COLUMN IF NOT EXISTS role ENUM('admin','user') DEFAULT 'user' AFTER password_hash;
-- To make first user admin: UPDATE users SET role = 'admin' WHERE id = 1 LIMIT 1;
