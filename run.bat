@echo off
cd "D:\Programming\Projects\netradump"

start "Flask App" python app.py
start "Steering Wheel" python Steer.py

start http://127.0.0.1:5000