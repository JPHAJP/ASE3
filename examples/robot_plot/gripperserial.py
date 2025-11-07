# ==================== CONFIGURACIÓN ====================
SERIAL_PORT = None  # Se detectará automáticamente
BAUD_RATE = 115200
TARGET_FORCE = 100  # Fuerza objetivo en gF
MAX_SAMPLES = 300  # Máximo de muestras a graficar
ENABLE_MAX_SAMPLES = True  # True: limitar muestras, False: sin límite
WINDOW_SIZE = 500   # Tamaño de ventana deslizante para visualización (0 = mostrar todo)

# ============== CONFIGURACIÓN PID GAINS ================
PID_KP = 1.0        # Ganancia proporcional
PID_KI = 0.1        # Ganancia integral  
PID_KD = 0.05       # Ganancia derivativabin/env# ==================== CONFIGURACIÓN ====================
SERIAL_PORT = None  # Se detectará automáticamente
BAUD_RATE = 115200
TARGET_FORCE = 500  # Fuerza objetivo en gF
MAX_SAMPLES = 5000  # Máximo de muestras a graficar
ENABLE_MAX_SAMPLES = True  # True: limitar muestras, False: sin límite
WINDOW_SIZE = 500   # Tamaño de ventana deslizante para visualización (0 = mostrar todo)n3
"""
Script para monitorear y graficar datos de fuerza del ESP32
"""

import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import re
import time
import glob
import os
from collections import deque

# ==================== CONFIGURACIÓN ====================
SERIAL_PORT = None  # Se detectará automáticamente
BAUD_RATE = 115200
TARGET_FORCE = 100  # Fuerza objetivo en gF
MAX_SAMPLES = 300  # Máximo de muestras a graficar
ENABLE_MAX_SAMPLES = True  # True: limitar muestras, False: sin límite

# =======================================================

def validate_pid_gains():
    """Valida que las ganancias PID sean valores positivos"""
    global PID_KP, PID_KI, PID_KD
    
    if PID_KP < 0 or PID_KI < 0 or PID_KD < 0:
        print("⚠️ Advertencia: Las ganancias PID deben ser valores positivos")
        PID_KP = max(0, PID_KP)
        PID_KI = max(0, PID_KI)  
        PID_KD = max(0, PID_KD)
        print(f"📝 Ganancias corregidas - KP: {PID_KP}, KI: {PID_KI}, KD: {PID_KD}")

def find_serial_port():
    """Busca automáticamente el último puerto serie conectado"""
    # Buscar puertos USB y ACM
    usb_ports = glob.glob('/dev/ttyUSB*')
    acm_ports = glob.glob('/dev/ttyACM*')
    
    # Combinar y ordenar por tiempo de modificación (más reciente primero)
    all_ports = usb_ports + acm_ports
    
    if not all_ports:
        print("✗ No se encontraron puertos serie USB/ACM")
        return None
    
    # Ordenar por tiempo de modificación (el más reciente primero)
    all_ports.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    print(f"📡 Puertos serie encontrados: {all_ports}")
    selected_port = all_ports[0]
    print(f"🎯 Puerto seleccionado: {selected_port}")
    
    return selected_port

class ESP32GripMonitor:
    def __init__(self):
        self.ser = None
        self.force_data = deque(maxlen=MAX_SAMPLES if ENABLE_MAX_SAMPLES else None)
        self.sample_count = 0
        self.finished = False
        
    def connect(self):
        """Conecta al puerto serial"""
        global SERIAL_PORT
        
        # Si no se ha especificado puerto, buscar automáticamente
        if SERIAL_PORT is None:
            SERIAL_PORT = find_serial_port()
            if SERIAL_PORT is None:
                print("✗ No se pudo encontrar un puerto serie")
                return False
        
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)  # Esperar a que se establezca la conexión
            print(f"✓ Conectado a {SERIAL_PORT} a {BAUD_RATE} baud")
            return True
        except Exception as e:
            print(f"✗ Error al conectar a {SERIAL_PORT}: {e}")
            # Intentar buscar otro puerto si falla
            print("🔄 Buscando otro puerto disponible...")
            SERIAL_PORT = find_serial_port()
            if SERIAL_PORT:
                try:
                    self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
                    time.sleep(2)
                    print(f"✓ Conectado a {SERIAL_PORT} a {BAUD_RATE} baud")
                    return True
                except Exception as e2:
                    print(f"✗ Error al conectar a {SERIAL_PORT}: {e2}")
            return False
    
    def send_command(self, command):
        """Envía comando al ESP32"""
        if self.ser and self.ser.is_open:
            self.ser.write(f"{command}\n".encode())
            print(f"📤 Comando enviado: {command}")
            # Pequeña pausa para procesamiento
            time.sleep(0.1)
        else:
            print(f"❌ Error: Puerto serie no disponible para enviar comando: {command}")
    
    def parse_force(self, line):
        """Parsea la línea para extraer el valor de fuerza"""
        # Intentar múltiples patrones para mayor flexibilidad
        patterns = [
            r'Grip force:\s*(\d+(?:\.\d+)?)',  # Patrón original
            r'Force:\s*(\d+(?:\.\d+)?)',       # Patrón alternativo 1
            r'force:\s*(\d+(?:\.\d+)?)',       # Patrón alternativo 2 (minúscula)
            r'(\d+(?:\.\d+)?)\s*gF',           # Patrón con unidad gF
            r'(\d+(?:\.\d+)?)\s*g',            # Patrón con unidad g
            r'F:\s*(\d+(?:\.\d+)?)',           # Patrón corto
            r'^(\d+(?:\.\d+)?)$',              # Número simple (solo dígitos y punto decimal)
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line.strip(), re.IGNORECASE)
            if match:
                force_value = float(match.group(1))
                # Convertir a gF si parece estar en otras unidades
                # Si el valor es muy pequeño (< 10), probablemente esté en otra unidad
                if force_value < 10:
                    force_value = force_value * 100  # Convertir de alguna unidad a gF
                return force_value
        return None
    
    def read_data(self):
        """Lee datos del serial"""
        if self.ser and self.ser.in_waiting > 0:
            try:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(f"📥 Línea recibida: {line}")  # Debug: mostrar línea recibida
                    force = self.parse_force(line)
                    if force is not None:
                        self.force_data.append(force)
                        self.sample_count += 1
                        print(f"✅ Muestra {self.sample_count}: {force} gF")
                        
                        # Verificar si alcanzamos el máximo
                        if ENABLE_MAX_SAMPLES and self.sample_count >= MAX_SAMPLES:
                            if not self.finished:
                                print(f"\n✓ Alcanzadas {MAX_SAMPLES} muestras")
                                self.send_command("MOVE GRIP HOME")
                                self.finished = True
                    else:
                        print(f"⚠️ No se pudo parsear fuerza de: {line}")  # Debug: línea no parseada
            except Exception as e:
                print(f"❌ Error al leer: {e}")
        else:
            # Debug: verificar estado del puerto
            if self.ser and self.ser.is_open:
                # Sin datos disponibles, esto es normal
                pass
            else:
                print("⚠️ Puerto serie no disponible")
    
    def close(self):
        """Cierra la conexión serial"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("📡 Conexión serial cerrada")

# Crear monitor
monitor = ESP32GripMonitor()

# Configurar gráfico
fig, ax = plt.subplots(figsize=(14, 8))
line, = ax.plot([], [], 'b-', linewidth=2, marker='o', markersize=2, alpha=0.8)
ax.set_xlabel('Número de Muestra', fontsize=12, fontweight='bold')
ax.set_ylabel('Fuerza (gF)', fontsize=12, fontweight='bold')
ax.set_title(f'ESP32 Gripper Force Monitor - Target: {TARGET_FORCE} gF', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)

# Configurar auto-escalado dinámico
ax.set_autoscalex_on(True)
ax.set_autoscaley_on(True)

# Configuración inicial de límites
ax.set_xlim(0, 50)
ax.set_ylim(0, TARGET_FORCE * 2)

def init():
    """Inicializa el gráfico"""
    line.set_data([], [])
    return line,

def animate(frame):
    """Actualiza el gráfico con auto-escalado inteligente"""
    monitor.read_data()
    
    if len(monitor.force_data) > 0:
        total_samples = len(monitor.force_data)
        
        # ============ VENTANA DESLIZANTE ============
        if WINDOW_SIZE > 0 and total_samples > WINDOW_SIZE:
            # Mostrar solo las últimas WINDOW_SIZE muestras
            start_idx = total_samples - WINDOW_SIZE
            y_data = list(monitor.force_data)[start_idx:]
            x_data = list(range(start_idx + 1, total_samples + 1))
        else:
            # Mostrar todas las muestras
            y_data = list(monitor.force_data)
            x_data = list(range(1, total_samples + 1))
        
        line.set_data(x_data, y_data)
        
        # ============ AUTO-ESCALADO HORIZONTAL (X) ============
        if x_data:
            x_min = min(x_data)
            x_max = max(x_data)
            x_range = x_max - x_min
            
            if x_range == 0:
                # Solo una muestra
                ax.set_xlim(x_min - 5, x_min + 5)
            else:
                # Margen horizontal del 5%
                x_margin = max(5, x_range * 0.05)
                ax.set_xlim(x_min - x_margin, x_max + x_margin)
        
        # ============ AUTO-ESCALADO VERTICAL (Y) ============
        if y_data:
            y_min = min(y_data)
            y_max = max(y_data)
            y_range = y_max - y_min
            
            if y_range == 0:
                # Todos los valores iguales
                center = y_max
                margin = max(50, center * 0.2)  # 20% del valor o mínimo 50
                ax.set_ylim(max(0, center - margin), center + margin)
            else:
                # Margen vertical del 20%
                margin_percent = 0.20
                margin = y_range * margin_percent
                margin = max(margin, 30)  # Mínimo 30 gF de margen
                
                new_y_min = y_min - margin
                new_y_max = y_max + margin
                
                # No permitir valores negativos
                new_y_min = max(0, new_y_min)
                
                ax.set_ylim(new_y_min, new_y_max)
        
        # ============ LÍNEA DE REFERENCIA TARGET ============
        # Limpiar líneas horizontales anteriores (excepto la de datos)
        for artist in ax.lines[1:]:
            artist.remove()
        
        # Solo agregar línea de target si está dentro del rango visible
        current_ylim = ax.get_ylim()
        if current_ylim[0] <= TARGET_FORCE <= current_ylim[1]:
            ax.axhline(y=TARGET_FORCE, color='red', linestyle='--', alpha=0.8, 
                      linewidth=2, label=f'Target: {TARGET_FORCE} gF')
        
        # ============ INFORMACIÓN DINÁMICA ============
        if monitor.sample_count > 0:
            current_force = y_data[-1] if y_data else 0
            window_min = min(y_data) if y_data else 0
            window_max = max(y_data) if y_data else 0
            window_avg = sum(y_data) / len(y_data) if y_data else 0
            
            # Determinar si estamos en ventana deslizante
            window_info = f"(Ventana: últimas {len(y_data)} muestras)" if WINDOW_SIZE > 0 and total_samples > WINDOW_SIZE else ""
            
            title = f'🎯 ESP32 Gripper Force Monitor | Total: {monitor.sample_count} muestras {window_info}\n'
            title += f'📊 Actual: {current_force:.1f} gF | Min: {window_min:.1f} | Max: {window_max:.1f} | Promedio: {window_avg:.1f} gF'
            
            ax.set_title(title, fontsize=10, pad=20)
    else:
        # ============ ESTADO INICIAL ============
        ax.set_title(f'⏳ Esperando datos del ESP32... (Puerto: {SERIAL_PORT})', fontsize=12)
        ax.set_xlim(0, 50)
        ax.set_ylim(0, TARGET_FORCE * 2)
    
    return line,

def main():
    """Función principal"""
    print("=" * 60)
    print("ESP32 Gripper Force Monitor")
    print("=" * 60)
    print(f"Puerto: {SERIAL_PORT if SERIAL_PORT else 'Auto-detectar'}")
    print(f"Baud Rate: {BAUD_RATE}")
    print(f"Target Force: {TARGET_FORCE} gF")
    print(f"Max Samples: {MAX_SAMPLES if ENABLE_MAX_SAMPLES else 'Ilimitado'}")
    print(f"PID Gains - KP: {PID_KP}, KI: {PID_KI}, KD: {PID_KD}")
    print("=" * 60)
    
    # Validar configuración PID
    validate_pid_gains()
    
    # Conectar
    if not monitor.connect():
        return
    
    # Configurar ganancias PID
    print("\n🔧 Configurando ganancias PID...")
    time.sleep(0.5)
    gains_command = f"CONFIG SET GAINS {PID_KP} {PID_KI} {PID_KD}"
    monitor.send_command(gains_command)
    
    # Enviar comando de fuerza objetivo
    print("🎯 Configurando fuerza objetivo...")
    time.sleep(0.5)
    monitor.send_command(f"MOVE GRIP TFORCE {TARGET_FORCE}")
    
    # Iniciar animación
    ani = animation.FuncAnimation(
        fig, 
        animate, 
        init_func=init,
        interval=50,   # Actualizar cada 50ms para mejor fluidez
        blit=False,    # Desactivar blit para permitir auto-escalado
        cache_frame_data=False,
        repeat=True
    )
    
    print("\n✓ Graficando... (Cierra la ventana para terminar)\n")
    
    try:
        plt.show()
    except KeyboardInterrupt:
        print("\n\n✗ Interrumpido por el usuario")
    except Exception as e:
        print(f"\n\n❌ Error durante la ejecución: {e}")
    finally:
        print("\n🏠 Enviando gripper a posición HOME...")
        try:
            monitor.send_command("MOVE GRIP HOME")
            time.sleep(1)  # Esperar a que se ejecute el comando
        except Exception as e:
            print(f"⚠️ Error al enviar comando HOME: {e}")
        monitor.close()
        print("✅ Programa terminado correctamente")

if __name__ == "__main__":
    main()