## JOYSTICK to LAPTOP to RASPBERRY

import pygame
import asyncio
import websockets
import json
import time

ip = "100.75.23.88"

# Inisialisasi pygame
pygame.init()
pygame.joystick.init()

print("Mencari joystick/steering wheel...")
print(f"Jumlah joystick terdeteksi: {pygame.joystick.get_count()}")

if pygame.joystick.get_count() == 0:
    print("Tidak ada joystick/steering wheel terdeteksi!")
    exit()

# Inisialisasi joystick pertama
joystick = pygame.joystick.Joystick(0)
joystick.init()

print(f"\nNama perangkat: {joystick.get_name()}")
print(f"Jumlah axis: {joystick.get_numaxes()}")
print(f"Jumlah tombol: {joystick.get_numbuttons()}")
print(f"Jumlah hat: {joystick.get_numhats()}")

print("\nTekan CTRL+C untuk menghentikan")
print("Gerakkan steering wheel atau tekan tombol untuk testing...")

async def handler(websocket):
    print("\nRaspberry Pi terhubung!")
    try:
        while True:
            pygame.event.pump()  # Process event queue

            # Baca semua axis
            axes = [joystick.get_axis(i) for i in range(joystick.get_numaxes())]
            
            # Baca semua tombol
            tombol_states = [joystick.get_button(i) for i in range(joystick.get_numbuttons())]
            
            # Format data paket sesuai dengan struktur axis dari kodingan pertama
            data_paket = {
                "setir": axes[0] if len(axes) > 0 else 0.0,
                "gas": axes[2] if len(axes) > 2 else 0.0,
                "tombol": tombol_states
            }
            
            # Tampilkan output real-time dari steering wheel
            print(f"\rSteering: {axes[0]:.3f} | Gas: {axes[2]:.3f} | Tombol aktif: {sum(tombol_states)}", end="")

            await websocket.send(json.dumps(data_paket))

            await asyncio.sleep(0.1)  # Sesuaikan delay dengan kodingan pertama
            
    except websockets.exceptions.ConnectionClosed:
        print("\n\nKoneksi dengan Raspberry Pi terputus.")
    finally:
        print("Menunggu koneksi baru...")

# Jalankan server WebSocket
async def main():
    # Gunakan ip agar bisa diakses dari perangkat lain di jaringan
    async with websockets.serve(handler, ip, 8765):
        print("\nServer WebSocket berjalan di port 8765. Menunggu koneksi...")
        await asyncio.Future()  # Berjalan selamanya

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nProgram dihentikan")
    finally:
        pygame.quit()