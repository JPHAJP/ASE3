#!/usr/bin/env python3
"""
Script para monitorear y graficar datos de fuerza del ESP32
"""

import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import re
import time
from collections import deque

# ==================== CONFIGURACIÓN ====================
SERIAL_PORT = '/dev/ttyUSB0'  # Cambia según tu sistema (ttyUSB0, ttyACM0, etc.)
BAUD_RATE = 115200
TARGET_FORCE = 500  # Fuerza objetivo en gF
MAX_SAMPLES = 5000  # Máximo de muestras a graficar
ENABLE_MAX_SAMPLES = True  # True: limitar muestras, False: sin límite

# =======================================================

class ESP32GripMonitor:
    def __init__(self):
        self.ser = None
        self.force_data = deque(maxlen=MAX_SAMPLES if ENABLE_MAX_SAMPLES else None)
        self.sample_count = 0
        self.finished = False
        
    def connect(self):
        """Conecta al puerto serial"""
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)  # Esperar a que se establezca la conexión
            print(f"✓ Conectado a {SERIAL_PORT} a {BAUD_RATE} baud")
            return True
        except Exception as e:
            print(f"✗ Error al conectar: {e}")
            return False
    
    def send_command(self, command):
        """Envía comando al ESP32"""
        if self.ser and self.ser.is_open:
            self.ser.write(f"{command}\n".encode())
            print(f"→ Comando enviado: {command}")
    
    def parse_force(self, line):
        """Parsea la línea para extraer el valor de fuerza"""
        match = re.search(r'Grip force:\s*(\d+(?:\.\d+)?)', line)
        if match:
            return float(match.group(1))
        return None
    
    def read_data(self):
        """Lee datos del serial"""
        if self.ser and self.ser.in_waiting > 0:
            try:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    force = self.parse_force(line)
                    if force is not None:
                        self.force_data.append(force)
                        self.sample_count += 1
                        print(f"Muestra {self.sample_count}: {force} gF")
                        
                        # Verificar si alcanzamos el máximo
                        if ENABLE_MAX_SAMPLES and self.sample_count >= MAX_SAMPLES:
                            if not self.finished:
                                print(f"\n✓ Alcanzadas {MAX_SAMPLES} muestras")
                                self.send_command("MOVE GRIP HOME")
                                self.finished = True
            except Exception as e:
                print(f"Error al leer: {e}")
    
    def close(self):
        """Cierra la conexión serial"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("\n✓ Conexión cerrada")

# Crear monitor
monitor = ESP32GripMonitor()

# Configurar gráfico
fig, ax = plt.subplots(figsize=(12, 6))
line, = ax.plot([], [], 'b-', linewidth=1.5)
ax.set_xlabel('Número de Muestra', fontsize=12)
ax.set_ylabel('Fuerza (gF)', fontsize=12)
ax.set_title(f'Monitoreo de Fuerza del Gripper - Target: {TARGET_FORCE} gF', fontsize=14)
ax.grid(True, alpha=0.3)

def init():
    """Inicializa el gráfico"""
    line.set_data([], [])
    return line,

def animate(frame):
    """Actualiza el gráfico"""
    monitor.read_data()
    
    if len(monitor.force_data) > 0:
        x_data = list(range(1, len(monitor.force_data) + 1))
        y_data = list(monitor.force_data)
        
        line.set_data(x_data, y_data)
        
        # Ajustar límites
        ax.set_xlim(0, max(100, len(monitor.force_data) + 10))
        
        # Ajustar escala Y automáticamente
        if y_data:
            y_min = min(y_data)
            y_max = max(y_data)
            margin = (y_max - y_min) * 0.1 if y_max != y_min else 10
            ax.set_ylim(y_min - margin, y_max + margin)
    
    return line,

def main():
    """Función principal"""
    print("=" * 60)
    print("ESP32 Gripper Force Monitor")
    print("=" * 60)
    print(f"Puerto: {SERIAL_PORT}")
    print(f"Baud Rate: {BAUD_RATE}")
    print(f"Target Force: {TARGET_FORCE} gF")
    print(f"Max Samples: {MAX_SAMPLES if ENABLE_MAX_SAMPLES else 'Ilimitado'}")
    print("=" * 60)
    
    # Conectar
    if not monitor.connect():
        return
    
    # Enviar comando inicial
    time.sleep(0.5)
    monitor.send_command(f"MOVE GRIP TFORCE {TARGET_FORCE}")
    
    # Iniciar animación
    ani = animation.FuncAnimation(
        fig, 
        animate, 
        init_func=init,
        interval=100,  # Actualizar cada 100ms
        blit=True,
        cache_frame_data=False
    )
    
    print("\n✓ Graficando... (Cierra la ventana para terminar)\n")
    
    try:
        plt.show()
    except KeyboardInterrupt:
        print("\n\n✗ Interrumpido por el usuario")
    finally:
        monitor.close()

if __name__ == "__main__":
    main()