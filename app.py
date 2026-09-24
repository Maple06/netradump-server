from flask import Flask, render_template, Response
from flask_sock import Sock
import threading
import json
import time

frame_lock = threading.Lock()
state_lock = threading.Lock()

current_frame = None
controller_clients = set()
raspberry_clients = set()

robot_state = {
    "steering": 0,
    "throttle": 0,
    "mode": "MAJU",
    "ultrasonic": {
        "front": -1,
        "back": -1
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

# WebSocket for controller & sensor data FROM Raspberry Pi
@sock.route('/controller_data')
def controller_data(ws):
    print("Raspberry Pi terhubung untuk controller/sensor data!")
    raspberry_clients.add(ws)
    
    try:
        while True:
            msg = ws.receive()
            if msg is None:
                break
            
            try:
                data = json.loads(msg)
            except Exception:
                continue

            with state_lock:
                # Update control attributes jika ada
                if "steering" in data:
                    robot_state["steering"] = data["steering"]
                if "throttle" in data:
                    robot_state["throttle"] = data["throttle"]
                if "mode" in data:
                    robot_state["mode"] = data["mode"]
                if "buttons" in data:
                    robot_state["buttons"] = data["buttons"]
                    buttons = robot_state["buttons"]
                    if len(buttons) >= 6:
                        if buttons[4] == 1:
                            robot_state["mode"] = "MAJU"
                        elif buttons[5] == 1:
                            robot_state["mode"] = "MUNDUR"

                # Update ultrasonic readings jika ada
                if "ultrasonic" in data and isinstance(data["ultrasonic"], dict):
                    u_data = data["ultrasonic"]
                    
                    if "front" in u_data:
                        val = u_data["front"]
                        if val != -1 and val is not None:
                            robot_state["ultrasonic"]["front"] = val

                    if "back" in u_data:
                        val = u_data["back"]
                        if val != -1 and val is not None:
                            robot_state["ultrasonic"]["back"] = val
                    elif "rear" in u_data:
                        val = u_data["rear"]
                        if val != -1 and val is not None:
                            robot_state["ultrasonic"]["back"] = val

                robot_state["last_update"] = time.time()
            
            send_state_to_clients()
            
    except Exception as e:
        # Menagkap disconnection dengan bersih
        pass
    finally:
        raspberry_clients.discard(ws)
        print("Raspberry Pi controller data disconnected")

def send_state_to_clients():
    """Send state update to all web clients"""
    with state_lock:
        state_copy = robot_state.copy()
    
    message = json.dumps(state_copy)
    
    for client in list(controller_clients):
        try:
            client.send(message)
        except Exception:
            controller_clients.discard(client)

# WebSocket for frontend dashboard clients
@sock.route('/ws_controller')
def ws_controller(ws):
    print("Web client connected for controller data")
    controller_clients.add(ws)
    
    try:
        send_state_to_clients()
    except Exception:
        pass
    
    try:
        while True:
            ws.receive(timeout=1)
    except Exception:
        pass
    finally:
        controller_clients.discard(ws)
        print("Web client disconnected from controller data")

# Background thread to broadcast state periodically
def state_broadcaster():
    while True:
        time.sleep(0.05)  # 20 FPS broadcast
        if controller_clients:
            send_state_to_clients()

broadcaster_thread = threading.Thread(target=state_broadcaster, daemon=True)
broadcaster_thread.start()

if __name__ == '__main__':
    app.run(host='100.75.23.88', port=5000, debug=True)