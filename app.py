from flask import Flask, render_template, Response
from flask_sock import Sock
import threading
from Steer import ip

frame_lock = threading.Lock()
current_frame = None

app = Flask(__name__)
sock = Sock(app)

@app.route('/')
def index():
    return render_template('index.html', ip=ip)

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

# WebSocket route to receive frames
@sock.route('/ws_stream')
def ws_stream(ws):
    global current_frame
    while True:
        # Receive raw bytes from the Pi
        data = ws.receive()
        if data is None:
            break
        # Ensure it's bytes (sometimes comes as str if text)
        if isinstance(data, str):
            data = data.encode("latin1")
        with frame_lock:
            current_frame = data

@sock.route('/controller_data')
def controller_data(ws):
    while True:
        msg = ws.receive()
        if msg is None:
            break
        
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
