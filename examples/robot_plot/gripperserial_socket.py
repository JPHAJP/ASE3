# ==================== CONFIGURACIÓN ====================
SOCKET_HOST = "192.168.0.100"  # IP del dispositivo ESP32
SOCKET_PORT = 23               # Puerto Telnet
TARGET_FORCE = 400             # Fuerza objetivo en gF
MAX_SAMPLES = 5000             # Máximo de muestras a graficar
ENABLE_MAX_SAMPLES = False     # True: limitar muestras, False: sin límite
WINDOW_SIZE = 1000             # Tamaño de ventana deslizante para visualización (0 = mostrar todo)

# ============== CONFIGURACIÓN PID GAINS ================
PID_KP = 1.0        # Ganancia proporcional
PID_KI = 0.0       # Ganancia integral  
PID_KD = 0.05        # Ganancia derivativa

"""
Script para monitorear y graficar datos de fuerza del ESP32 via Socket
"""

import socket
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import re
import time
import threading
import queue
from collections import deque
from datetime import datetime

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

class ESP32GripSocketMonitor:
    def __init__(self):
        self.socket = None
        self.connected = False
        self.running = False
        
        # Datos para gráfico
        self.force_data = deque(maxlen=MAX_SAMPLES if ENABLE_MAX_SAMPLES else None)
        self.sample_count = 0
        self.finished = False
        
        # Threading para comunicación no bloqueante
        self.send_queue = queue.Queue()
        self.receive_queue = queue.Queue()
        self.receiver_thread = None
        self.sender_thread = None
        
        # Buffer para datos sin procesar
        self.data_buffer = ""
        
    def connect(self):
        """Conecta al dispositivo via socket"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)  # Timeout inicial para conexión
            self.socket.connect((SOCKET_HOST, SOCKET_PORT))
            self.connected = True
            print(f"✓ Conectado a {SOCKET_HOST}:{SOCKET_PORT}")
            
            # Configurar socket para operación no bloqueante
            self.socket.settimeout(0.1)
            
            # Leer mensaje de bienvenida
            welcome_data = ""
            start_time = time.time()
            
            try:
                while time.time() - start_time < 2:
                    data = self.socket.recv(1024).decode('utf-8', errors='ignore')
                    if data:
                        welcome_data += data
                    else:
                        break
            except socket.timeout:
                pass
            
            if welcome_data:
                print("📄 Dispositivo conectado:")
                print(welcome_data.strip()[:200])  # Mostrar primeras líneas
            
            return True
            
        except Exception as e:
            print(f"✗ Error al conectar a {SOCKET_HOST}:{SOCKET_PORT}: {e}")
            return False
    
    def start_threads(self):
        """Inicia los hilos de comunicación"""
        if not self.connected:
            return False
            
        self.running = True
        
        # Hilo de recepción
        self.receiver_thread = threading.Thread(target=self._receiver_worker, daemon=True)
        self.receiver_thread.start()
        
        # Hilo de envío
        self.sender_thread = threading.Thread(target=self._sender_worker, daemon=True)
        self.sender_thread.start()
        
        print("✓ Hilos de comunicación iniciados")
        return True
    
    def _receiver_worker(self):
        """Hilo que recibe datos continuamente"""
        while self.running and self.connected:
            try:
                data = self.socket.recv(2048).decode('utf-8', errors='ignore')
                if not data:
                    print("⚠️ Conexión cerrada por el dispositivo")
                    self.connected = False
                    break
                
                self.data_buffer += data
                
                # Procesar líneas completas
                while '\n' in self.data_buffer:
                    line, self.data_buffer = self.data_buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        # Poner en cola para procesamiento
                        self.receive_queue.put(line)
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"❌ Error en recepción: {e}")
                break
    
    def _sender_worker(self):
        """Hilo que envía comandos desde la cola"""
        while self.running and self.connected:
            try:
                command = self.send_queue.get(timeout=0.5)
                
                if command == "STOP_THREAD":
                    break
                    
                self.socket.sendall((command + "\n").encode())
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"📤 [{timestamp}] Comando enviado: {command}")
                
                self.send_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                if self.running:
                    print(f"❌ Error en envío: {e}")
                break
    
    def send_command(self, command):
        """Envía comando de forma no bloqueante"""
        if self.running and self.connected:
            self.send_queue.put(command)
            time.sleep(0.1)  # Pequeña pausa para procesamiento
        else:
            print(f"❌ Error: Socket no disponible para enviar comando: {command}")
    
    def parse_force(self, line):
        """Parsea la línea para extraer el valor de fuerza"""
        patterns = [
            r'#(\d+(?:\.\d+)?)\*',             # Patrón #numero* (formato ESP32)
            r'Grip force:\s*(\d+(?:\.\d+)?)',  # Patrón original
            r'Force:\s*(\d+(?:\.\d+)?)',       # Patrón alternativo 1
            r'force:\s*(\d+(?:\.\d+)?)',       # Patrón alternativo 2 (minúscula)
            r'(\d+(?:\.\d+)?)\s*gF',           # Patrón con unidad gF
            r'(\d+(?:\.\d+)?)\s*g',            # Patrón con unidad g
            r'F:\s*(\d+(?:\.\d+)?)',           # Patrón corto
            r'^(\d+(?:\.\d+)?)$',              # Número simple
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line.strip(), re.IGNORECASE)
            if match:
                force_value = float(match.group(1))
                # Ya viene en gF, no necesita conversión para el patrón #numero*
                return force_value
        return None
    
    def read_data(self):
        """Lee y procesa datos de la cola de recepción"""
        new_data_count = 0
        
        try:
            while True:
                line = self.receive_queue.get_nowait()
                
                if line:
                    # Debug: mostrar línea recibida ocasionalmente
                    if self.sample_count % 10 == 0:  # Cada 10 muestras para ver más frecuente
                        print(f"📥 Línea recibida: {line}")
                    
                    force = self.parse_force(line)
                    if force is not None:
                        self.force_data.append(force)
                        self.sample_count += 1
                        new_data_count += 1
                        
                        # Mostrar progreso cada 25 muestras
                        if self.sample_count % 25 == 0:
                            print(f"✅ Muestra {self.sample_count}: {force:.1f} gF (de línea: {line})")
                        
                        # Verificar si alcanzamos el máximo
                        if ENABLE_MAX_SAMPLES and self.sample_count >= MAX_SAMPLES:
                            if not self.finished:
                                print(f"\n✓ Alcanzadas {MAX_SAMPLES} muestras")
                                self.send_command("MOVE GRIP HOME")
                                self.finished = True
                    else:
                        # Debug: mostrar líneas no parseadas más frecuentemente
                        if self.sample_count % 20 == 0:
                            print(f"⚠️ No parseado: '{line}'")
        
        except queue.Empty:
            pass
        
        return new_data_count > 0
    
    def stop(self):
        """Detiene los hilos y cierra la conexión"""
        print("🔄 Deteniendo monitor...")
        self.running = False
        
        # Señal de parada al hilo de envío
        try:
            self.send_queue.put("STOP_THREAD")
        except:
            pass
        
        # Esperar hilos
        if self.sender_thread and self.sender_thread.is_alive():
            self.sender_thread.join(timeout=2)
            
        if self.receiver_thread and self.receiver_thread.is_alive():
            self.receiver_thread.join(timeout=2)
        
        # Cerrar socket
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            
        self.connected = False
        print("📡 Conexión socket cerrada")

# Crear monitor
monitor = ESP32GripSocketMonitor()

# Configurar gráfico
fig, ax = plt.subplots(figsize=(14, 8))
line, = ax.plot([], [], 'b-', linewidth=2, marker='o', markersize=2, alpha=0.8)
ax.set_xlabel('Número de Muestra', fontsize=12, fontweight='bold')
ax.set_ylabel('Fuerza (gF)', fontsize=12, fontweight='bold')
ax.set_title(f'ESP32 Gripper Force Monitor (Socket) - Target: {TARGET_FORCE} gF', fontsize=14, fontweight='bold')
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
    # Leer nuevos datos
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
                ax.set_xlim(x_min - 5, x_min + 5)
            else:
                x_margin = max(5, x_range * 0.05)
                ax.set_xlim(x_min - x_margin, x_max + x_margin)
        
        # ============ AUTO-ESCALADO VERTICAL (Y) ============
        if y_data:
            y_min = min(y_data)
            y_max = max(y_data)
            y_range = y_max - y_min
            
            if y_range == 0:
                center = y_max
                margin = max(50, center * 0.2)
                ax.set_ylim(max(0, center - margin), center + margin)
            else:
                margin_percent = 0.20
                margin = y_range * margin_percent
                margin = max(margin, 30)
                
                new_y_min = max(0, y_min - margin)
                new_y_max = y_max + margin
                
                ax.set_ylim(new_y_min, new_y_max)
        
        # ============ LÍNEA DE REFERENCIA TARGET ============
        for artist in ax.lines[1:]:
            artist.remove()
        
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
            
            # Estado de conexión
            connection_status = "🟢 Conectado" if monitor.connected else "🔴 Desconectado"
            
            window_info = f"(Ventana: últimas {len(y_data)} muestras)" if WINDOW_SIZE > 0 and total_samples > WINDOW_SIZE else ""
            
            title = f'🌐 ESP32 Gripper Socket Monitor | {connection_status} | Total: {monitor.sample_count} muestras {window_info}\n'
            title += f'📊 Actual: {current_force:.1f} gF | Min: {window_min:.1f} | Max: {window_max:.1f} | Promedio: {window_avg:.1f} gF'
            
            ax.set_title(title, fontsize=10, pad=20)
    else:
        # ============ ESTADO INICIAL ============
        connection_status = "🟡 Conectando..." if monitor.connected else "🔴 Sin conexión"
        ax.set_title(f'{connection_status} a {SOCKET_HOST}:{SOCKET_PORT} - Esperando datos...', fontsize=12)
        ax.set_xlim(0, 50)
        ax.set_ylim(0, TARGET_FORCE * 2)
    
    return line,

def main():
    """Función principal"""
    print("=" * 60)
    print("ESP32 Gripper Force Monitor (Socket)")
    print("=" * 60)
    print(f"Host: {SOCKET_HOST}")
    print(f"Puerto: {SOCKET_PORT}")
    print(f"Target Force: {TARGET_FORCE} gF")
    print(f"Max Samples: {MAX_SAMPLES if ENABLE_MAX_SAMPLES else 'Ilimitado'}")
    print(f"PID Gains - KP: {PID_KP}, KI: {PID_KI}, KD: {PID_KD}")
    print("=" * 60)
    
    # Validar configuración PID
    validate_pid_gains()
    
    # Conectar
    if not monitor.connect():
        return
    
    # Iniciar hilos de comunicación
    if not monitor.start_threads():
        return
    
    # Configurar ganancias PID
    print("\n🔧 Configurando ganancias PID...")
    time.sleep(1.0)  # Esperar estabilización
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
        interval=100,   # Actualizar cada 100ms para mejor rendimiento con socket
        blit=False,
        cache_frame_data=False,
        repeat=True
    )
    
    print("\n✓ Monitor iniciado... (Cierra la ventana para terminar)")
    print("🔄 Los comandos se envían de forma no bloqueante\n")
    
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
            time.sleep(1)
        except Exception as e:
            print(f"⚠️ Error al enviar comando HOME: {e}")
        monitor.stop()
        print("✅ Programa terminado correctamente")

if __name__ == "__main__":
    main()