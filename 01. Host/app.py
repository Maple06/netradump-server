from flask import Flask, render_template, Response, request, jsonify
from flask_sock import Sock
import threading
import os
import time
import cv2
import numpy as np
import json
from datetime import datetime
import queue

app = Flask(__name__)
sock = Sock(app)

# --- DATA STORES ---
frame_lock = threading.Lock()
current_frame = None
current_frame_time = 0

# Data FROM Laptop Controller
controller_lock = threading.Lock()
last_controller = None
last_controller_time = 0
controller_clients = set()  # WebSocket clients for controller

# Data FROM Robot (Feedback)
robot_lock = threading.Lock()
last_robot_status = None
last_robot_time = 0
robot_clients = set()  # WebSocket clients for robot

# Store commands for RPi
controller_queue = queue.Queue(maxsize=100)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

def generate_frames():
    global current_frame, current_frame_time
    last_yielded = None
    
    blank_image = np.zeros((240, 360, 3), dtype=np.uint8)
    blank_image[:] = (100, 100, 100)
    cv2.putText(blank_image, "No Camera Feed", (50, 120), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    _, buffer = cv2.imencode('.jpg', blank_image)
    placeholder_bytes = buffer.tobytes()
    
    while True:
        frame_to_send = placeholder_bytes
        frame_time = 0
        
        with frame_lock:
            if current_frame is not None and time.time() - current_frame_time < 2:
                frame_to_send = current_frame
                frame_time = current_frame_time
        
        if frame_to_send != last_yielded:
            last_yielded = frame_to_send
            yield (b"--frame\r\n" 
                   b"Content-Type: image/jpeg\r\n\r\n" + 
                   frame_to_send + b"\r\n")
        
        time.sleep(0.033)

@app.route("/video_feed")
def video_feed():
    return Response(generate_frames(), 
                   mimetype="multipart/x-mixed-replace; boundary=frame")

# ================= WEBSOCKET ENDPOINTS =================

# 1. Controller (Laptop) connects via WebSocket
@sock.route("/ws_controller")
def ws_controller(ws):
    print(f"[Controller WS] New connection from {ws.remote_address}")
    
    # Add client to set
    with controller_lock:
        controller_clients.add(ws)
    
    try:
        while True:
            msg = ws.receive()
            if msg is None:
                break
            
            try:
                data = json.loads(msg)
                print(f"[Controller WS] Received command: {data}")
                
                with controller_lock:
                    last_controller = data
                    last_controller_time = time.time()
                    # Add to queue for RPi
                    try:
                        controller_queue.put_nowait(data)
                    except queue.Full:
                        try:
                            controller_queue.get_nowait()
                        except queue.Empty:
                            pass
                        controller_queue.put_nowait(data)
                
                # Forward to all robot clients (RPi)
                with controller_lock:
                    dead_clients = []
                    for client in robot_clients:
                        try:
                            client.send(json.dumps(data))
                        except:
                            dead_clients.append(client)
                    
                    # Remove dead clients
                    for client in dead_clients:
                        robot_clients.remove(client)
                        
            except json.JSONDecodeError:
                print(f"[Controller WS] Invalid JSON: {msg}")
            except Exception as e:
                print(f"[Controller WS] Error: {e}")
                
    except Exception as e:
        print(f"[Controller WS] Connection error: {e}")
    finally:
        with controller_lock:
            if ws in controller_clients:
                controller_clients.remove(ws)
        print(f"[Controller WS] Connection closed")

# 2. Robot (RPi) connects via WebSocket
@sock.route("/ws_robot")
def ws_robot(ws):
    print(f"[Robot WS] New connection from {ws.remote_address}")
    
    # Add client to set
    with controller_lock:
        robot_clients.add(ws)
    
    try:
        # Send initial handshake with simpler format
        ws.send(json.dumps({"type": "handshake", "status": "connected"}))
        print("[Robot WS] Sent handshake")
        
        while True:
            try:
                msg = ws.receive(timeout=1)  # 1 second timeout
                if msg is None:
                    # Send ping to keep connection alive
                    try:
                        ws.send(json.dumps({"type": "ping", "time": time.time()}))
                    except:
                        break
                    continue
                
                # Robot sending status updates
                try:
                    data = json.loads(msg)
                    print(f"[Robot WS] Received status: {data}")
                    
                    with robot_lock:
                        last_robot_status = data
                        last_robot_time = time.time()
                        
                except json.JSONDecodeError:
                    print(f"[Robot WS] Invalid JSON: {msg}")
                except Exception as e:
                    print(f"[Robot WS] Error: {e}")
                    
            except Exception as e:
                if "timeout" in str(e).lower():
                    continue
                else:
                    print(f"[Robot WS] Receive error: {e}")
                    break
                
    except Exception as e:
        print(f"[Robot WS] Connection error: {e}")
    finally:
        with controller_lock:
            if ws in robot_clients:
                robot_clients.remove(ws)
        print(f"[Robot WS] Connection closed")

# 3. Website connects via WebSocket for real-time updates
@sock.route("/ws_view")
def ws_view(ws):
    print(f"[View WS] New connection from {ws.remote_address}")
    
    try:
        while True:
            # Send current status
            with controller_lock:
                controller_data = last_controller
                controller_time = last_controller_time
            
            with robot_lock:
                robot_data = last_robot_status
                robot_time = last_robot_time
            
            with frame_lock:
                camera_time = current_frame_time
            
            payload = {
                "controller": controller_data,
                "robot": robot_data,
                "camera_ts": camera_time,
                "controller_ts": controller_time,
                "robot_ts": robot_time,
                "server_time": time.time()
            }
            
            try:
                ws.send(json.dumps(payload))
            except:
                break
            
            time.sleep(0.1)  # 10Hz update
            
    except Exception as e:
        print(f"[View WS] Connection error: {e}")
    finally:
        print(f"[View WS] Connection closed")

# ================= HTTP ENDPOINTS (for backward compatibility) =================
@app.route("/api/upload_frame", methods=["POST"])
def upload_frame():
    global current_frame, current_frame_time
    
    try:
        if request.files and 'frame' in request.files:
            file = request.files['frame']
            frame_data = file.read()
        elif request.json and 'frame' in request.json:
            import base64
            frame_data = base64.b64decode(request.json['frame'])
        else:
            return jsonify({"status": "error", "message": "No frame data"}), 400
        
        with frame_lock:
            current_frame = frame_data
            current_frame_time = time.time()
        
        return jsonify({"status": "success", "timestamp": time.time()})
        
    except Exception as e:
        print(f"[Upload Frame] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/robot_status", methods=["POST"])
def robot_status():
    global last_robot_status, last_robot_time
    
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data"}), 400
        
        with robot_lock:
            last_robot_status = data
            last_robot_time = time.time()
        
        return jsonify({"status": "success", "timestamp": time.time()})
        
    except Exception as e:
        print(f"[Robot Status] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/get_status")
def get_status():
    with controller_lock:
        controller_data = last_controller
        controller_time = last_controller_time
    
    with robot_lock:
        robot_data = last_robot_status
        robot_time = last_robot_time
    
    with frame_lock:
        camera_time = current_frame_time
    
    return jsonify({
        "controller": controller_data,
        "robot": robot_data,
        "camera_ts": camera_time,
        "controller_ts": controller_time,
        "robot_ts": robot_time,
        "server_time": time.time()
    })

@app.route("/api/pop_command")
def pop_command():
    try:
        command = controller_queue.get_nowait()
        command_time = time.time()
        
        with controller_lock:
            last_controller = command
            last_controller_time = command_time
        
        return jsonify({
            "command": command,
            "timestamp": command_time,
            "has_command": True
        })
    except queue.Empty:
        return jsonify({
            "command": None,
            "timestamp": 0,
            "has_command": False
        })

@app.route("/api/debug")
def debug():
    with controller_lock:
        controller_data = last_controller
    
    with robot_lock:
        robot_data = last_robot_status
    
    return jsonify({
        "controller": controller_data,
        "robot": robot_data,
        "current_frame": "yes" if current_frame else "no",
        "queue_size": controller_queue.qsize(),
        "controller_clients": len(controller_clients),
        "robot_clients": len(robot_clients)
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, threaded=True)