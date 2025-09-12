## JOYSTICK to LAPTOP to RASPBERRY

import pygame
import asyncio
import websockets
import json

ip = "192.168.1.202"

# Inisialisasi Pygame dan Joystick
pygame.init()
try:
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    print(f"Server siap. Menggunakan: {joystick.get_name()}")
except pygame.error:
    print("G29 tidak terdeteksi. Pastikan sudah terhubung.")
    exit()

async def handler(websocket):
    print("Raspberry Pi terhubung!")
    try:
        while True:
            pygame.event.get()

            tombol_states = [joystick.get_button(i) for i in range(joystick.get_numbuttons())]
            
            data_paket = {
                "setir": joystick.get_axis(0),
                "gas": joystick.get_axis(2),
                "tombol": tombol_states
            }

            await websocket.send(json.dumps(data_paket))

            await asyncio.sleep(0.02)
            
    except websockets.exceptions.ConnectionClosed:
        print("Koneksi dengan Raspberry Pi terputus.")
    finally:
        print("Menunggu koneksi baru...")

# Jalankan server WebSocket
async def main():
    # Gunakan ip agar bisa diakses dari perangkat lain di jaringan
    async with websockets.serve(handler, ip, 8765):
        print("Server WebSocket berjalan di port 8765. Menunggu koneksi...")
        await asyncio.Future()  # Berjalan selamanya

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server dihentikan.")
    finally:
        pygame.quit()