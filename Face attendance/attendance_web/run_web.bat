@echo off
echo Setting up Face Attendance Web App...
cd attendance_web
echo Installing dependencies...
pip install -r requirements.txt
echo.
echo Server ready! Open http://127.0.0.1:5000
echo Press Ctrl+C to stop
python app.py

