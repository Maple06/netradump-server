import subprocess
import sys
import threading
import signal
import time
import os

# --- KONFIGURASI WARNA (Agar mudah dibaca) ---
CYAN = '\033[96m'
YELLOW = '\033[93m'
RESET = '\033[0m'

processes = []

def stream_reader(pipe, label, color):
    """
    Fungsi ini berjalan di thread terpisah.
    Tugasnya: Membaca output program baris demi baris,
    menambahkan label, dan mencetaknya.
    """
    try:
        # iter() akan membaca terus sampai stream habis/putus
        for line in iter(pipe.readline, ''):
            text = (line or '').rstrip()
            if text:
                # FORMAT LOG: [LABEL] Pesan
                print(f"{color}[{label}] {RESET}{text}")
    except ValueError:
        pass

def start_process(command, label, color):
    """Menjalankan proses dan attach reader thread"""
    # NOTE: Tambahkan "-u" agar python outputnya Unbuffered (langsung muncul)
    cmd_list = [sys.executable, "-u"] + command

    env = os.environ.copy()
    # Pastikan output anak pakai UTF-8 agar log tidak rusak di Windows.
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    
    # Jalankan proses dengan redirect STDOUT dan STDERR ke PIPE
    proc = subprocess.Popen(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # Gabung error ke output biasa
        bufsize=1, # Line buffered (text mode)
        close_fds=False, # Penting untuk Windows
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    
    # Buat thread khusus untuk memantau output proses ini
    t = threading.Thread(target=stream_reader, args=(proc.stdout, label, color))
    t.daemon = True # Agar thread mati otomatis jika program utama mati
    t.start()

    item = {"proc": proc, "label": label, "color": color, "command": cmd_list}
    processes.append(item)
    return item

def shutdown_all(reason: str):
    print(f"\n{RESET}[MANAGER] {reason}")
    for item in processes:
        try:
            item["proc"].terminate()
        except:
            pass
    sys.exit(0)


def cleanup(signum, frame):
    shutdown_all("Ctrl+C ditekan. Mematikan semua program...")

# Register Ctrl+C handler
signal.signal(signal.SIGINT, cleanup)

if __name__ == "__main__":
    print("================================")
    print("    Log Manager Started")
    print("================================")

    # 1. Jalankan FLASK (Warna CYAN)
    start_process(["app.py"], "FLASK", CYAN)
    
    # Beri jeda sedikit agar Flask siap
    time.sleep(2)
    
    # 2. Jalankan STEER (Warna YELLOW)
    start_process(["Steer.py"], "STEER", YELLOW)

    # Loop utama agar script tidak langsung selesai
    try:
        while True:
            time.sleep(1)
            # Cek jika salah satu program crash/mati
            stopped = [item for item in processes if item["proc"].poll() is not None]
            if stopped:
                first = stopped[0]
                code = first["proc"].returncode
                shutdown_all(
                    f"Proses '{first['label']}' berhenti (exit code {code}). Shutdown semua program..."
                )
                
    except KeyboardInterrupt:
        shutdown_all("KeyboardInterrupt. Mematikan semua program...")