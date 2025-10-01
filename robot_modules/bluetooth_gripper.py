"""
Controlador Bluetooth del gripper para la aplicación web
Basado en test_bt.py pero adaptado para enviar comandos de fuerza y apertura
"""

import socket
import time
import threading
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class BluetoothGripperController:
    def __init__(self, esp32_mac="88:13:BF:70:40:72", port=1, debug=True):
        """
        Inicializar controlador Bluetooth del gripper
        
        Args:
            esp32_mac: Dirección MAC del ESP32
            port: Puerto RFCOMM (típicamente 1 para BluetoothSerial)
            debug: Habilitar logging detallado
        """
        self.esp32_mac = esp32_mac
        self.port = port
        self.debug = debug
        
        # Estado de conexión
        self.sock = None
        self.connected = False
        self.last_connection_attempt = 0
        self.connection_timeout = 8.0
        self.recv_timeout = 1.0
        
        # Estado del gripper
        self.current_force = 5.0      # Newtons
        self.current_position = 0.0   # Porcentaje (0-100)
        self.last_command_time = 0
        self.command_cooldown = 0.1   # 100ms entre comandos
        
        # Lock para thread safety
        self.lock = threading.Lock()
        
        # Cola de comandos
        self.command_queue = []
        
        logger.info(f"BluetoothGripperController inicializado - MAC: {esp32_mac}")

    def connect(self):
        """Establecer conexión RFCOMM con el ESP32"""
        try:
            current_time = time.time()
            
            # Evitar intentos de conexión muy frecuentes
            if current_time - self.last_connection_attempt < 2.0:
                return self.connected
            
            self.last_connection_attempt = current_time
            
            # Crear socket RFCOMM
            self.sock = socket.socket(
                socket.AF_BLUETOOTH,
                socket.SOCK_STREAM,
                socket.BTPROTO_RFCOMM
            )
            self.sock.settimeout(self.connection_timeout)
            
            if self.debug:
                logger.info(f"Conectando a ESP32 {self.esp32_mac}:{self.port}")
            
            # Intentar conexión
            self.sock.connect((self.esp32_mac, self.port))
            self.sock.settimeout(self.recv_timeout)
            
            self.connected = True
            logger.info("✅ Conexión Bluetooth establecida con gripper")
            
            # Enviar comando de inicialización
            self.send_raw_command("INIT")
            
            return True
            
        except OSError as e:
            if self.debug:
                logger.warning(f"Error conectando a gripper: {e}")
            
            self.connected = False
            if self.sock:
                try:
                    self.sock.close()
                except:
                    pass
                self.sock = None
            
            return False
        except Exception as e:
            logger.error(f"Error inesperado conectando: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Cerrar conexión Bluetooth"""
        try:
            with self.lock:
                if self.sock:
                    if self.debug:
                        logger.info("Cerrando conexión Bluetooth del gripper")
                    
                    try:
                        # Enviar comando de desconexión
                        self.send_raw_command("DISCONNECT", timeout=1.0)
                    except:
                        pass  # Ignorar errores al desconectar
                    
                    self.sock.close()
                    self.sock = None
                
                self.connected = False
            
            logger.info("✅ Desconectado del gripper Bluetooth")
            
        except Exception as e:
            logger.error(f"Error desconectando gripper: {e}")

    def send_raw_command(self, command, timeout=None):
        """Enviar comando crudo al ESP32"""
        if not self.connected or not self.sock:
            return False
        
        try:
            # Agregar salto de línea si no está presente
            data = command if command.endswith("\n") else command + "\n"
            
            # Configurar timeout temporal si se especifica
            original_timeout = None
            if timeout:
                original_timeout = self.sock.gettimeout()
                self.sock.settimeout(timeout)
            
            # Enviar comando
            self.sock.send(data.encode("utf-8"))
            
            if self.debug:
                logger.debug(f"→ TX: {command.strip()}")
            
            # Restaurar timeout original
            if original_timeout is not None:
                self.sock.settimeout(original_timeout)
            
            return True
            
        except OSError as e:
            logger.warning(f"Error enviando comando: {e}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Error inesperado enviando comando: {e}")
            return False

    def recv_response(self, timeout=None):
        """Recibir respuesta del ESP32"""
        if not self.connected or not self.sock:
            return None
        
        try:
            # Configurar timeout temporal si se especifica
            original_timeout = None
            if timeout:
                original_timeout = self.sock.gettimeout()
                self.sock.settimeout(timeout)
            
            # Leer respuesta línea por línea
            buf = b""
            while True:
                try:
                    ch = self.sock.recv(1)
                    if not ch:
                        # Conexión cerrada
                        self.connected = False
                        return None
                    
                    if ch in (b"\n", b"\r"):
                        if buf:
                            break
                        else:
                            continue  # Saltar líneas vacías
                    
                    buf += ch
                    
                    # Límite para evitar colgarse
                    if len(buf) > 1024:
                        break
                        
                except socket.timeout:
                    return None  # Timeout normal
                
            # Restaurar timeout original
            if original_timeout is not None:
                self.sock.settimeout(original_timeout)
            
            response = buf.decode("utf-8", errors="ignore").strip()
            
            if self.debug and response:
                logger.debug(f"← RX: {response}")
            
            return response
            
        except OSError as e:
            logger.warning(f"Error recibiendo respuesta: {e}")
            self.connected = False
            return None
        except Exception as e:
            logger.error(f"Error inesperado recibiendo respuesta: {e}")
            return None

    def send_gripper_command(self, force, position):
        """
        Enviar comando de control del gripper
        
        Args:
            force: Fuerza en Newtons (0.0 - 10.0)
            position: Posición en porcentaje (0.0 - 100.0)
            
        Returns:
            bool: True si el comando se envió exitosamente
        """
        try:
            # Control de cooldown
            current_time = time.time()
            if current_time - self.last_command_time < self.command_cooldown:
                logger.debug("Comando ignorado - cooldown activo")
                return False
            
            # Validar parámetros
            force = max(0.0, min(10.0, float(force)))
            position = max(0.0, min(100.0, float(position)))
            
            # Conectar si no está conectado
            if not self.connected:
                if not self.connect():
                    logger.warning("No se pudo conectar para enviar comando del gripper")
                    return False
            
            # Crear comando JSON
            command_data = {
                "type": "gripper_control",
                "force": round(force, 2),
                "position": round(position, 2),
                "timestamp": datetime.now().isoformat()
            }
            
            command_json = json.dumps(command_data)
            
            # Enviar comando
            success = self.send_raw_command(command_json)
            
            if success:
                self.last_command_time = current_time
                
                # Actualizar estado local
                with self.lock:
                    self.current_force = force
                    self.current_position = position
                
                logger.info(f"✅ Comando gripper enviado - Fuerza: {force}N, Posición: {position}%")
                
                # Intentar leer respuesta
                response = self.recv_response(timeout=0.5)
                if response:
                    logger.debug(f"Respuesta del gripper: {response}")
                
            return success
            
        except Exception as e:
            logger.error(f"❌ Error enviando comando del gripper: {e}")
            return False

    def send_simple_gripper_command(self, force, position):
        """
        Enviar comando simple del gripper (formato legacy)
        Para compatibilidad con ESP32 que espera comandos simples
        """
        try:
            # Conectar si no está conectado
            if not self.connected:
                if not self.connect():
                    return False
            
            # Validar parámetros
            force = max(0.0, min(10.0, float(force)))
            position = max(0.0, min(100.0, float(position)))
            
            # Formato simple: "GRIP:fuerza:posicion"
            command = f"GRIP:{force:.2f}:{position:.2f}"
            
            success = self.send_raw_command(command)
            
            if success:
                with self.lock:
                    self.current_force = force
                    self.current_position = position
                
                logger.info(f"✅ Comando simple enviado - {command}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error enviando comando simple: {e}")
            return False

    def open_gripper(self, force=2.0):
        """Abrir gripper completamente"""
        return self.send_gripper_command(force, 100.0)

    def close_gripper(self, force=5.0):
        """Cerrar gripper completamente"""
        return self.send_gripper_command(force, 0.0)

    def set_gripper_position(self, position, force=5.0):
        """Establecer posición específica del gripper"""
        return self.send_gripper_command(force, position)

    def emergency_stop_gripper(self):
        """Parada de emergencia del gripper"""
        try:
            if self.connected:
                success = self.send_raw_command("EMERGENCY_STOP", timeout=1.0)
                if success:
                    logger.warning("🚨 Parada de emergencia del gripper activada")
                return success
            return False
        except Exception as e:
            logger.error(f"Error en parada de emergencia del gripper: {e}")
            return False

    def get_gripper_status(self):
        """Obtener estado actual del gripper"""
        with self.lock:
            return {
                'connected': self.connected,
                'force': self.current_force,
                'position': self.current_position,
                'esp32_mac': self.esp32_mac,
                'last_command_time': self.last_command_time,
                'available_commands': [
                    'open_gripper', 'close_gripper', 'set_position', 
                    'emergency_stop', 'send_custom_command'
                ]
            }

    def test_connection(self):
        """Probar conexión enviando comando de test"""
        try:
            if not self.connected:
                if not self.connect():
                    return False
            
            # Enviar comando de test
            success = self.send_raw_command("TEST")
            
            if success:
                # Esperar respuesta
                response = self.recv_response(timeout=2.0)
                if response and "OK" in response.upper():
                    logger.info("✅ Test de conexión exitoso")
                    return True
                else:
                    logger.warning(f"Respuesta inesperada del test: {response}")
            
            return False
            
        except Exception as e:
            logger.error(f"Error en test de conexión: {e}")
            return False

    def send_custom_command(self, command):
        """Enviar comando personalizado al ESP32"""
        try:
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            success = self.send_raw_command(command)
            
            if success:
                # Intentar leer respuesta
                response = self.recv_response(timeout=1.0)
                return True, response or "Comando enviado (sin respuesta)"
            else:
                return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error enviando comando personalizado: {e}")
            return False, str(e)

    def check_connection_health(self):
        """Verificar salud de la conexión"""
        if not self.connected:
            return False
        
        try:
            # Enviar ping simple
            return self.send_raw_command("PING", timeout=0.5)
        except:
            self.connected = False
            return False

    def auto_reconnect(self, max_attempts=3):
        """Intentar reconexión automática"""
        if self.connected:
            return True
        
        logger.info("Intentando reconexión automática del gripper...")
        
        for attempt in range(max_attempts):
            if self.connect():
                logger.info(f"✅ Reconexión exitosa en intento {attempt + 1}")
                return True
            
            if attempt < max_attempts - 1:
                time.sleep(2)  # Esperar entre intentos
        
        logger.warning(f"❌ Reconexión fallida después de {max_attempts} intentos")
        return False