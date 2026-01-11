# flask app.py - UPDATED VERSION
from flask import Flask, render_template, Response
from flask_sock import Sock
import threading
import json
import time

frame_lock = threading.Lock()
current_frame = None
controller_clients = set()
raspberry_clients = set()

robot_state = {
    "steering": 0,
    "throttle": 0,
    "mode": "MAJU",
    "ultrasonic": {
        "front": 0,
        "back": 0
    },
    "buttons": [],
    "last_update": 0
}

app = Flask(__name__)
sock = Sock(app)

@app.route('/')
def index():
    return render_template('index.html')

def generate_frames():
    global current_frame
    while True:
        with frame_lock:
            if current_frame is None:
                continue
            frame_to_send = current_frame
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_to_send + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# WebSocket for video stream
@sock.route('/ws_stream')
def ws_stream(ws):
    global current_frame
    while True:
        data = ws.receive()
        if data is None:
            break
        if isinstance(data, str):
            data = data.encode("latin1")
        with frame_lock:
            current_frame = data

# WebSocket for controller data FROM Raspberry Pi
@sock.route('/controller_data')
def controller_data(ws):
    print("Raspberry Pi terhubung untuk controller data!")
    raspberry_clients.add(ws)
    
    try:
        while True:
            msg = ws.receive()
            if msg is None:
                break
            
            data = json.loads(msg)
            
            with threading.Lock():
                robot_state["steering"] = data.get("steering", 0)
                robot_state["throttle"] = data.get("throttle", 0)
                robot_state["buttons"] = data.get("buttons", [])
                
                ultrasonic_data = data.get("ultrasonic", {})
                if ultrasonic_data.get("front", -1) != -1:
                    robot_state["ultrasonic"]["front"] = ultrasonic_data.get("front", 0)
                if ultrasonic_data.get("back", -1) != -1:
                    robot_state["ultrasonic"]["back"] = ultrasonic_data.get("back", 0)
                
                buttons = robot_state["buttons"]
                if len(buttons) >= 6:
                    if buttons[4] == 1:
                        robot_state["mode"] = "MAJU"
                    elif buttons[5] == 1:
                        robot_state["mode"] = "MUNDUR"
                
                robot_state["last_update"] = time.time()
            
            send_state_to_clients()
    
    except Exception as e:
        print(f"Error in controller_data: {e}")
    finally:
        raspberry_clients.discard(ws)
        print("Raspberry Pi controller data disconnected")

def send_state_to_clients():
    """Send current state to all connected web clients"""
    with threading.Lock():
        state_copy = robot_state.copy()
    
    message = json.dumps(state_copy)
    
    for client in list(controller_clients):
        try:
            client.send(message)
        except:
            controller_clients.discard(client)

# WebSocket for web clients that want controller data
@sock.route('/ws_controller')
def ws_controller(ws):
    print("Web client connected for controller data")
    controller_clients.add(ws)
    
    try:
        send_state_to_clients()
    except:
        pass
    
    try:
        while True:
            ws.receive(timeout=1)
    except:
        pass
    finally:
        controller_clients.discard(ws)
        print("Web client disconnected from controller data")

# Background thread to periodically send state even without updates
def state_broadcaster():
    """Periodically send state to keep clients updated"""
    while True:
        time.sleep(0.5)  # Update every 500ms
        if controller_clients:
            send_state_to_clients()

# Start broadcaster thread
broadcaster_thread = threading.Thread(target=state_broadcaster, daemon=True)
broadcaster_thread.start()

if __name__ == '__main__':
    app.run(host='100.75.23.88', port=5000, debug=True)