import socket
import threading
import time
import queue
from datetime import datetime

HOST = "192.168.0.101"
PORT = 23

class GripperSocketMonitor:
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.running = False
        
        # Colas para comunicación entre hilos
        self.send_queue = queue.Queue()
        self.receive_queue = queue.Queue()
        
        # Hilos separados
        self.sender_thread = None
        self.receiver_thread = None
        
    def connect(self):
        """Conecta al dispositivo"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            print(f"✓ Conectado a {self.host}:{self.port}")
            
            # Configurar timeout para recepción no bloqueante
            self.socket.settimeout(0.1)
            
            return True
        except Exception as e:
            print(f"✗ Error al conectar: {e}")
            return False
    
    def start_threads(self):
        """Inicia los hilos de envío y recepción"""
        if not self.connected:
            print("✗ No hay conexión establecida")
            return False
            
        self.running = True
        
        # Iniciar hilo de recepción
        self.receiver_thread = threading.Thread(target=self._receiver_worker, daemon=True)
        self.receiver_thread.start()
        
        # Iniciar hilo de envío
        self.sender_thread = threading.Thread(target=self._sender_worker, daemon=True)
        self.sender_thread.start()
        
        print("✓ Hilos de comunicación iniciados")
        return True
    
    def _receiver_worker(self):
        """Hilo que recibe datos continuamente"""
        buffer = ""
        
        while self.running and self.connected:
            try:
                # Recibir datos con timeout pequeño
                data = self.socket.recv(1024).decode('utf-8', errors='ignore')
                if not data:
                    print("⚠️ Conexión cerrada por el servidor")
                    self.connected = False
                    break
                
                buffer += data
                
                # Procesar líneas completas
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        # Poner en cola para procesamiento
                        self.receive_queue.put({
                            'timestamp': timestamp,
                            'data': line
                        })
                        
            except socket.timeout:
                # Timeout normal, continuar
                continue
            except Exception as e:
                if self.running:
                    print(f"❌ Error en recepción: {e}")
                break
    
    def _sender_worker(self):
        """Hilo que envía comandos desde la cola"""
        while self.running and self.connected:
            try:
                # Esperar comando con timeout
                command = self.send_queue.get(timeout=0.5)
                
                if command == "STOP_THREAD":
                    break
                    
                # Enviar comando
                self.socket.sendall((command + "\n").encode())
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"📤 [{timestamp}] Enviado: {command}")
                
                self.send_queue.task_done()
                
            except queue.Empty:
                # No hay comandos, continuar
                continue
            except Exception as e:
                if self.running:
                    print(f"❌ Error en envío: {e}")
                break
    
    def send_command(self, command):
        """Envía un comando de forma no bloqueante"""
        if self.running and self.connected:
            self.send_queue.put(command)
            return True
        else:
            print(f"⚠️ No se puede enviar comando '{command}': no hay conexión")
            return False
    
    def get_received_data(self):
        """Obtiene todos los datos recibidos pendientes"""
        data_list = []
        try:
            while True:
                data = self.receive_queue.get_nowait()
                data_list.append(data)
        except queue.Empty:
            pass
        
        return data_list
    
    def stop(self):
        """Detiene los hilos y cierra la conexión"""
        print("🔄 Deteniendo monitor...")
        self.running = False
        
        # Enviar señal de parada al hilo de envío
        try:
            self.send_queue.put("STOP_THREAD")
        except:
            pass
        
        # Esperar a que terminen los hilos
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
        print("✅ Monitor detenido")

def interactive_mode():
    """Modo interactivo mejorado"""
    monitor = GripperSocketMonitor()
    
    # Conectar
    if not monitor.connect():
        return
    
    # Leer mensaje de bienvenida inicial
    welcome_data = ""
    start_time = time.time()
    monitor.socket.settimeout(2.0)
    
    try:
        while time.time() - start_time < 2:
            data = monitor.socket.recv(1024).decode('utf-8', errors='ignore')
            if data:
                welcome_data += data
            else:
                break
    except socket.timeout:
        pass
    
    if welcome_data:
        print("📄 Mensaje de bienvenida:")
        print(welcome_data.strip())
        print("-" * 50)
    
    # Iniciar hilos
    if not monitor.start_threads():
        return
    
    print("\n🎮 Modo interactivo iniciado")
    print("💡 Comandos disponibles:")
    print("   - Cualquier comando del gripper")
    print("   - 'status': Ver datos recientes recibidos")
    print("   - 'clear': Limpiar buffer de recepción")
    print("   - 'exit' o 'quit': Salir")
    print("-" * 50)
    
    try:
        last_status_time = 0
        
        while True:
            # Mostrar datos recibidos cada segundo
            current_time = time.time()
            if current_time - last_status_time >= 1.0:
                received_data = monitor.get_received_data()
                if received_data:
                    print(f"\n📥 Datos recibidos ({len(received_data)} mensajes):")
                    for item in received_data[-5:]:  # Mostrar últimos 5
                        print(f"   [{item['timestamp']}] {item['data']}")
                last_status_time = current_time
            
            # Leer comando del usuario (con timeout)
            import select
            import sys
            
            # Verificar si hay entrada disponible
            if select.select([sys.stdin], [], [], 0.1)[0]:
                cmd = input("> ").strip()
                
                if cmd.lower() in ("exit", "quit"):
                    break
                elif cmd.lower() == "status":
                    received_data = monitor.get_received_data()
                    if received_data:
                        print(f"📊 Últimos datos recibidos ({len(received_data)}):")
                        for item in received_data:
                            print(f"   [{item['timestamp']}] {item['data']}")
                    else:
                        print("📭 No hay datos recientes")
                elif cmd.lower() == "clear":
                    # Limpiar buffer
                    monitor.get_received_data()
                    print("🧹 Buffer limpiado")
                elif cmd:
                    monitor.send_command(cmd)
    
    except KeyboardInterrupt:
        print("\n\n✗ Interrumpido por el usuario")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        monitor.stop()

def monitoring_mode():
    """Modo solo monitoreo (sin comandos interactivos)"""
    monitor = GripperSocketMonitor()
    
    if not monitor.connect():
        return
        
    if not monitor.start_threads():
        return
    
    print("👁️ Modo monitoreo activo - Solo recepción de datos")
    print("Presiona Ctrl+C para salir\n")
    
    try:
        while True:
            time.sleep(0.5)
            received_data = monitor.get_received_data()
            
            for item in received_data:
                print(f"[{item['timestamp']}] {item['data']}")
    
    except KeyboardInterrupt:
        print("\n\n✗ Saliendo del modo monitoreo")
    finally:
        monitor.stop()

def main():
    print("=" * 60)
    print("ESP32 Gripper Socket Monitor con Threading")
    print("=" * 60)
    print(f"Host: {HOST}")
    print(f"Port: {PORT}")
    print("=" * 60)
    
    print("\nSelecciona el modo:")
    print("1. Interactivo (enviar comandos + recibir datos)")
    print("2. Solo monitoreo (solo recibir datos)")
    
    try:
        choice = input("\nOpción (1-2): ").strip()
        
        if choice == "1":
            interactive_mode()
        elif choice == "2":
            monitoring_mode()
        else:
            print("❌ Opción no válida")
    
    except KeyboardInterrupt:
        print("\n\n✗ Programa cancelado")

if __name__ == "__main__":
    main()