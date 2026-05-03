@echo off
echo Setting up Face Attendance Web App...
cd attendance_web
echo Installing dependencies...
pip install -r requirements.txt
echo Starting server...
echo Open http://localhost:5000 in browser
flask run
pause

