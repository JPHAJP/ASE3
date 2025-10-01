#!/usr/bin/env python3
import socket
import sys
import time
import threading
import queue
import signal

# ====== Config ======
ESP32_MAC = "88:13:BF:70:40:72"   # tu MAC
RFCOMM_CH = 1                     # BluetoothSerial usa canal 1
BAUD_INFO = "115200 (solo informativo en BT SPP)"  # por si lo imprimes


class BluetoothController:
    """
    Control de LED vía Bluetooth RFCOMM hacia ESP32 (BluetoothSerial).
    """
    def __init__(self, esp32_addr=ESP32_MAC, port=RFCOMM_CH, debug=True, recv_timeout=1.0):
        self.esp32_addr = esp32_addr
        self.port = port
        self.debug = debug
        self.sock = None
        self.connected = False
        self.recv_timeout = recv_timeout

    def connect(self):
        """Establece conexión RFCOMM (Bluetooth clásico)."""
        # Socket RFCOMM nativo (Linux)
        self.sock = socket.socket(
            socket.AF_BLUETOOTH,
            socket.SOCK_STREAM,
            socket.BTPROTO_RFCOMM
        )
        self.sock.settimeout(8.0)

        if self.debug:
            print(f"Conectando a {self.esp32_addr}:{self.port} …")

        try:
            self.sock.connect((self.esp32_addr, self.port))
            self.sock.settimeout(self.recv_timeout)
            self.connected = True
            if self.debug:
                print("✅ Conexión Bluetooth establecida.")
            return True
        except OSError as e:
            if self.debug:
                print("❌ Error al conectar:", e)
            self.connected = False
            self.sock = None
            return False

    def send_text(self, text: str):
        """Envía texto (agrega '\n' si no está)."""
        if not self.connected or not self.sock:
            raise RuntimeError("No conectado.")
        data = text if text.endswith("\n") else text + "\n"
        try:
            self.sock.send(data.encode("utf-8"))
            if self.debug:
                print(f"→ TX: {text.strip()}")
        except OSError as e:
            self.connected = False
            raise

    def recv_line(self) -> str | None:
        """Lee una línea si llega algo; None en timeout."""
        if not self.connected or not self.sock:
            return None
        try:
            buf = b""
            while True:
                ch = self.sock.recv(1)
                if not ch:
                    # conexión cerrada del otro lado
                    self.connected = False
                    return None
                if ch in (b"\n", b"\r"):
                    if buf:
                        break
                    else:
                        # salta líneas vacías
                        continue
                buf += ch
                # límite simple para no colgarse si nunca llega '\n'
                if len(buf) > 1024:
                    break
            return buf.decode("utf-8", errors="ignore").strip()
        except TimeoutError:
            return None
        except OSError:
            self.connected = False
            return None

    def disconnect(self):
        """Cierra la conexión."""
        if self.sock:
            if self.debug:
                print("🔌 Cerrando conexión Bluetooth…")
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        self.connected = False


def print_help():
    print("\nComandos:")
    print("  1   → LED ON")
    print("  0   → LED OFF")
    print("  t   → Toggle (envía '1' y luego '0' 1s después)")
    print("  s X → Envía texto crudo X (ej. 'hello')")
    print("  h   → Ayuda")
    print("  q   → Salir\n")


def reader_thread(ctrl: BluetoothController, outq: queue.Queue):
    """Hilo lector: mete líneas recibidas en outq."""
    while True:
        if not ctrl.connected:
            time.sleep(0.2)
            continue
        line = ctrl.recv_line()
        if line:
            outq.put(line)
        else:
            # timeout o desconexión; pequeño respiro
            time.sleep(0.05)


def main():
    print("=== Control ESP32 por Bluetooth (RFCOMM/Serial) ===")
    print(f"Objetivo: {ESP32_MAC} canal {RFCOMM_CH}")
    print_help()

    ctrl = BluetoothController(esp32_addr=ESP32_MAC, port=RFCOMM_CH, debug=True)

    # Conecta (intento rápido + reintento)
    if not ctrl.connect():
        print("Reintentando en 3s…")
        time.sleep(3)
        if not ctrl.connect():
            print("❌ No se pudo establecer la conexión. Verifica emparejamiento/potencia/alcance.")
            return

    # Hilo para leer sin bloquear la entrada de usuario
    outq: queue.Queue[str] = queue.Queue()
    t = threading.Thread(target=reader_thread, args=(ctrl, outq), daemon=True)
    t.start()

    # Manejo limpio de Ctrl+C
    def on_sigint(sig, frame):
        print("\n(CTRL+C) Saliendo…")
        ctrl.disconnect()
        sys.exit(0)
    signal.signal(signal.SIGINT, on_sigint)

    # Bucle interactivo
    while True:
        # drena lo que haya llegado del ESP32
        while not outq.empty():
            msg = outq.get_nowait()
            print(f"ESP32: {msg}")

        try:
            cmd = input("> ").strip()
        except EOFError:
            cmd = "q"

        if cmd == "q":
            break
        elif cmd == "h":
            print_help()
        elif cmd == "1":
            try:
                ctrl.send_text("1")
            except Exception as e:
                print("TX error:", e)
        elif cmd == "0":
            try:
                ctrl.send_text("0")
            except Exception as e:
                print("TX error:", e)
        elif cmd.startswith("s "):
            payload = cmd[2:].strip()
            if payload:
                try:
                    ctrl.send_text(payload)
                except Exception as e:
                    print("TX error:", e)
        elif cmd == "t":
            try:
                ctrl.send_text("1")
                time.sleep(1)
                ctrl.send_text("0")
            except Exception as e:
                print("TX error:", e)
        else:
            print("Comando no reconocido. Presiona 'h' para ayuda.")

        # Reconexión simple si se cayó
        if not ctrl.connected:
            print("⚠️  Conexión perdida. Reintentando en 2s…")
            time.sleep(2)
            if not ctrl.connect():
                print("❌ No se pudo reconectar. Reintenta más tarde con 'q' y vuelve a ejecutar.")
                # sigue en loop por si vuelve a aparecer el dispositivo

    ctrl.disconnect()
    print("Listo. 👌")


if __name__ == "__main__":
    main()
