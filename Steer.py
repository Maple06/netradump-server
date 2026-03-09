## JOYSTICK to LAPTOP to RASPBERRY

import pygame
import asyncio
import websockets
import json
import time

ip = "100.114.16.27"

latest_payload = None

# Inisialisasi pygame
pygame.init()
try:
    pygame.joystick.init()

    def find_joystick(name_contains: str):
        target = name_contains.lower()
        for idx in range(pygame.joystick.get_count()):
            candidate = pygame.joystick.Joystick(idx)
            candidate.init()
            name = (candidate.get_name() or "").lower()
            if target in name:
                return candidate, idx
        return None, None

    wheel_joy, wheel_index = find_joystick("Racing Wheel")
    if wheel_joy is None:
        raise pygame.error(
            f"Joystick wheel dengan nama mengandung 'Racing Wheel' tidak terdeteksi. Total device: {pygame.joystick.get_count()}"
        )

    arm_joy, arm_index = find_joystick("Extreme 3D")
    if arm_joy is None:
        raise pygame.error(
            f"Joystick arm dengan nama mengandung 'Extreme 3D' tidak terdeteksi. Total device: {pygame.joystick.get_count()}"
        )

    print(f"Server siap. Wheel: {wheel_joy.get_name()} (index={wheel_index})")
    print(f"Server siap. Arm:   {arm_joy.get_name()} (index={arm_index})")
except pygame.error:
    print("Joystick tidak terdeteksi. Pastikan sudah terhubung.")
    exit()


def build_data_paket():
    # Pump events so joystick state updates.
    pygame.event.pump()

    # === Extreme 3D Pro (arm controls) ===
    arm_buttons = [arm_joy.get_button(i) for i in range(arm_joy.get_numbuttons())]
    arm_axes = [arm_joy.get_axis(i) for i in range(arm_joy.get_numaxes())]
    arm_hats = [arm_joy.get_hat(i) for i in range(arm_joy.get_numhats())]

    hat0 = arm_hats[0] if len(arm_hats) > 0 else (0, 0)
    base_hat = hat0[0]
    if base_hat == -1:
        base = "left"
    elif base_hat == 1:
        base = "right"
    else:
        base = "idle"

    elbow_hat = hat0[1]
    if elbow_hat == 1:
        elbow = "down"
    elif elbow_hat == -1:
        elbow = "up"
    else:
        elbow = "idle"

    shoulder_axis = arm_axes[1] if len(arm_axes) > 1 else 0.0
    if shoulder_axis <= -0.5:
        shoulder = "down"
    elif shoulder_axis >= 0.5:
        shoulder = "up"
    else:
        shoulder = "idle"

    wrist_up = arm_buttons[4] == 1 if len(arm_buttons) > 4 else False
    wrist_down = arm_buttons[2] == 1 if len(arm_buttons) > 2 else False
    if wrist_up and not wrist_down:
        wrist = "up"
    elif wrist_down and not wrist_up:
        wrist = "down"
    else:
        wrist = "idle"

    gripper_open = arm_buttons[0] == 1 if len(arm_buttons) > 0 else False
    gripper_closed = arm_buttons[1] == 1 if len(arm_buttons) > 1 else False
    if gripper_open and not gripper_closed:
        gripper = "open"
    elif gripper_closed and not gripper_open:
        gripper = "closed"
    else:
        gripper = "idle"

    return {
        "setir": wheel_joy.get_axis(0),
        "gas": wheel_joy.get_axis(2),
        "base": base,
        "shoulder": shoulder,
        "elbow": elbow,
        "wrist": wrist,
        "gripper": gripper,
    }


async def joystick_monitor():
    global latest_payload
    while True:
        data_paket = build_data_paket()
        payload = json.dumps(data_paket, ensure_ascii=False, separators=(",", ":"))
        latest_payload = payload

        await asyncio.sleep(0.02)

async def handler(websocket):
    print("\nRaspberry Pi terhubung!")
    try:
        while True:
            payload = latest_payload
            if payload is not None:
                await websocket.send(payload)

            await asyncio.sleep(0.1)  # Sesuaikan delay dengan kodingan pertama
            
    except websockets.exceptions.ConnectionClosed:
        print()
        print("Koneksi dengan Raspberry Pi terputus.")
    finally:
        print()
        print("Menunggu koneksi baru...")

# Jalankan server WebSocket
async def main():
    monitor_task = asyncio.create_task(joystick_monitor())
    # Gunakan ip agar bisa diakses dari perangkat lain di jaringan
    try:
        async with websockets.serve(handler, ip, 8765):
            print("Server WebSocket berjalan di port 8765. Menunggu koneksi...")
            await asyncio.Future()  # Berjalan selamanya
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nProgram dihentikan")
    finally:
        pygame.quit()