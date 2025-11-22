"""
Controlador socket TCP del gripper para la aplicación web
Convertido de comunicación serie a socket con hilos separados
Basado en gripper_socket_threaded.py
"""

import socket
import time
import threading
import logging
import json
import queue
import os
from datetime import datetime

logger = logging.getLogger(__name__)


# ==================== NOTA IMPORTANTE SOBRE TIMEOUTS ====================
# El gripper uSENSE no siempre envía respuestas a los comandos.
# Esto es comportamiento normal y NO debe considerarse un error.
# Los timeouts se manejan silenciosamente para evitar spam de logs.
# ========================================================================

class SocketGripperController:
    def __init__(self, host="192.168.68.110", port=23, debug=True):
        """
        Inicializar controlador socket TCP del gripper
        
        Args:
            host: Dirección IP del gripper (ESP32)
            port: Puerto TCP (típicamente 23 para telnet)
            debug: Habilitar logging detallado
        """
        self.host = host
        self.port = port
        self.debug = debug
        
        # Estado de conexión
        self.socket_conn = None
        self.connected = False
        self.running = False
        self.last_connection_attempt = 0
        self.connection_timeout = 5.0
        self.recv_timeout = 1.0
        
        # Estado del gripper
        self.current_force = 5.0      # Newtons
        self.current_position = 0.0   # Porcentaje (0-100)
        self.last_command_time = 0
        self.command_cooldown = 0.1   # 100ms entre comandos
        
        # Lock para thread safety
        self.lock = threading.Lock()
        
        # Colas para comunicación entre hilos
        self.send_queue = queue.Queue()
        self.receive_queue = queue.Queue()
        
        # Hilos separados
        self.sender_thread = None
        self.receiver_thread = None
        
        logger.info(f"SocketGripperController inicializado - Host: {self.host}:{self.port}")

    def connect(self):
        """Establecer conexión TCP con el gripper con reintentos mejorados"""
        return self.connect_with_retry(max_retries=3, retry_delay=1.5)
    
    def connect_with_retry(self, max_retries=3, retry_delay=1.5):
        """Conectar con reintentos automáticos para manejar limitaciones del ESP32"""
        
        # Si ya está conectado, verificar que la conexión sea válida
        if self.connected and self.socket_conn:
            try:
                # Test rápido de la conexión
                self.socket_conn.settimeout(0.1)
                self.socket_conn.sendall(b"")  # Envío vacío para test
                if self.debug:
                    logger.debug("✅ Conexión existente válida")
                return True
            except:
                # Conexión rota, cerrar y reconectar
                if self.debug:
                    logger.debug("🔄 Conexión existente rota, reconectando")
                self.disconnect()
        
        for attempt in range(max_retries + 1):
            try:
                current_time = time.time()
                
                # Evitar intentos de conexión muy frecuentes, con delay mayor en reintentos
                min_delay = retry_delay if attempt > 0 else 2.0
                if current_time - self.last_connection_attempt < min_delay:
                    sleep_time = min_delay - (current_time - self.last_connection_attempt)
                    if self.debug:
                        logger.debug(f"⏰ Esperando {sleep_time:.1f}s antes del intento {attempt + 1}")
                    time.sleep(sleep_time)
                
                self.last_connection_attempt = time.time()
                
                if self.debug:
                    attempt_msg = f" (intento {attempt + 1}/{max_retries + 1})" if attempt > 0 else ""
                    logger.info(f"🔌 Conectando a {self.host}:{self.port}{attempt_msg}")
                
                # Crear conexión socket TCP
                self.socket_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket_conn.settimeout(self.connection_timeout)
                self.socket_conn.connect((self.host, self.port))
                
                # Configurar timeout para recepción no bloqueante
                self.socket_conn.settimeout(0.1)
                
                self.connected = True
                logger.info("✅ Conexión TCP establecida con gripper")
                
                # Iniciar hilos de comunicación
                self.start_threads()
                
                # Leer mensaje de bienvenida inicial
                time.sleep(0.5)
                welcome_data = self.get_received_data()
                if welcome_data and self.debug:
                    logger.info(f"📄 Mensaje de bienvenida: {[item['data'] for item in welcome_data]}")
                
                # Enviar comando de inicialización
                self.send_command("HELP")
                
                return True
                
            except socket.error as e:
                error_msg = str(e)
                
                if attempt < max_retries:
                    if "Connection refused" in error_msg:
                        if self.debug:
                            logger.warning(f"🚫 Conexión rechazada, reintentando en {retry_delay}s... (intento {attempt + 1}/{max_retries + 1})")
                    else:
                        logger.warning(f"⚠️ Error de socket: {e}, reintentando...")
                else:
                    # Último intento falló
                    if self.debug:
                        logger.error(f"❌ Error de socket al conectar tras {max_retries + 1} intentos: {e}")
                
                # Limpiar socket fallido
                self.connected = False
                if self.socket_conn:
                    try:
                        self.socket_conn.close()
                    except:
                        pass
                    self.socket_conn = None
                
                # Esperar antes del siguiente intento (solo si no es el último)
                if attempt < max_retries:
                    time.sleep(retry_delay)
                
            except Exception as e:
                logger.error(f"❌ Error inesperado conectando: {e}")
                self.connected = False
                if attempt >= max_retries:
                    break
                time.sleep(retry_delay)
        
        return False

    def start_threads(self):
        """Inicia los hilos de envío y recepción"""
        if not self.connected:
            logger.warning("✗ No hay conexión establecida para iniciar hilos")
            return False
            
        self.running = True
        
        # Iniciar hilo de recepción
        self.receiver_thread = threading.Thread(target=self._receiver_worker, daemon=True)
        self.receiver_thread.start()
        
        # Iniciar hilo de envío
        self.sender_thread = threading.Thread(target=self._sender_worker, daemon=True)
        self.sender_thread.start()
        
        logger.info("✓ Hilos de comunicación iniciados")
        return True

    def _receiver_worker(self):
        """Hilo que recibe datos continuamente"""
        buffer = ""
        
        while self.running and self.connected:
            try:
                # Recibir datos con timeout pequeño
                data = self.socket_conn.recv(1024).decode('utf-8', errors='ignore')
                if not data:
                    logger.warning("⚠️ Conexión cerrada por el servidor")
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
                            'data': line,
                            'raw': line
                        })
                        
                        if self.debug:
                            logger.info(f"📥 [{timestamp}] Recibido: {line}")
                        
            except socket.timeout:
                # Timeout normal, continuar
                continue
            except (socket.error, ConnectionResetError, BrokenPipeError) as e:
                if self.running:
                    logger.error(f"❌ Error de socket en recepción: {e}")
                    self.connected = False
                    self._mark_connection_broken()
                break
            except Exception as e:
                if self.running:
                    logger.error(f"❌ Error inesperado en recepción: {e}")
                break

    def _sender_worker(self):
        """Hilo que envía comandos desde la cola"""
        while self.running and self.connected:
            try:
                # Esperar comando con timeout
                command_data = self.send_queue.get(timeout=0.5)
                
                if command_data == "STOP_THREAD":
                    break
                
                # Extraer comando si es un dict, sino usar directo
                if isinstance(command_data, dict):
                    command = command_data.get('command', '')
                else:
                    command = str(command_data)
                    
                if not command:
                    self.send_queue.task_done()
                    continue
                    
                # Enviar comando
                self.socket_conn.sendall((command + "\n").encode('utf-8'))
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                
                if self.debug:
                    logger.info(f"📤 [{timestamp}] Enviado: {command}")
                
                self.send_queue.task_done()
                
                # Respetar cooldown entre comandos
                time.sleep(self.command_cooldown)
                
            except queue.Empty:
                # No hay comandos, continuar
                continue
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, socket.error) as e:
                if self.running:
                    logger.warning(f"⚠️ Conexión perdida en envío: {e}")
                    self._mark_connection_broken()
                break
            except Exception as e:
                if self.running:
                    logger.error(f"❌ Error inesperado en envío: {e}")
                break

    def send_command(self, command):
        """Envía un comando de forma no bloqueante"""
        if self.running and self.connected:
            self.send_queue.put(command)
            return True
        else:
            logger.warning(f"⚠️ No se puede enviar comando '{command}': no hay conexión")
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

    def get_latest_response(self, timeout=2.0):
        """Obtiene la respuesta más reciente, esperando hasta timeout"""
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            data_list = self.get_received_data()
            if data_list:
                # Retornar la respuesta más reciente
                return data_list[-1]['data']
            time.sleep(0.1)
        
        return None

    def disconnect(self):
        """Cerrar conexión socket"""
        try:
            logger.info("🔄 Desconectando del gripper...")
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
            if self.socket_conn:
                try:
                    self.socket_conn.close()
                except:
                    pass
                self.socket_conn = None
                
            self.connected = False
            logger.info("✅ Gripper desconectado")
            
        except Exception as e:
            logger.error(f"❌ Error al desconectar gripper: {e}")

    def validate_usense_command(self, command):
        """
        Validar que el comando sea compatible con uSENSEGRIP
        
        Args:
            command: Comando a validar
            
        Returns:
            tuple: (es_válido, mensaje_error)
        """
        if not command or not isinstance(command, str):
            return False, "Comando vacío o inválido"
        
        cmd_upper = command.upper().strip()
        
        # Comandos válidos conocidos del uSENSEGRIP
        valid_command_prefixes = [
            "HELP",
            "CONFIG",
            "MOVE GRIP",
            "GET GRIP",
            "DO FORCE",
            "DO GRIP",
            "DO LIGHT",
            "INIT", 
            "DISCONNECT",
            "PING",
            "STATUS"
        ]
        
        # Verificar si el comando comienza con un prefijo válido
        for prefix in valid_command_prefixes:
            if cmd_upper.startswith(prefix):
                return True, "Comando válido"
        
        # Comandos específicos completos
        valid_complete_commands = [
            "HELP",
            "CONFIG SAVE",
            "CONFIG LOAD", 
            "CONFIG SHOW",
            "CONFIG SHOW EEPROM",
            "MOVE GRIP HOME"
        ]
        
        if cmd_upper in valid_complete_commands:
            return True, "Comando válido"
        
        # Permitir comandos JSON para compatibilidad legacy
        if command.strip().startswith("{") and command.strip().endswith("}"):
            return True, "Comando JSON válido"
        
        return False, f"Comando no reconocido: {command}"

    def send_raw_command(self, command, timeout=None, validate=True, auto_reconnect=True):
        """
        Enviar comando crudo al gripper con validación opcional y reconexión automática
        
        Args:
            command: Comando a enviar
            timeout: Timeout específico para este comando
            validate: Si True, valida el comando antes de enviar
            auto_reconnect: Si True, intenta reconectar automáticamente si falla
            
        Returns:
            tuple: (success, response) 
        """
        # Intentar reconectar si no está conectado
        if not self.connected and auto_reconnect:
            logger.info("🔄 Conexión perdida, intentando reconectar...")
            if not self.connect_with_retry(max_retries=2, retry_delay=3.0):
                return False, "No se pudo reconectar al gripper"
        
        if not self.connected:
            return False, "No hay conexión establecida"
        
        # Validar comando si se solicita
        if validate:
            is_valid, error_msg = self.validate_usense_command(command)
            if not is_valid:
                logger.warning(f"⚠️ {error_msg}")
                return False, error_msg
        
        max_attempts = 2 if auto_reconnect else 1
        
        for attempt in range(max_attempts):
            try:
                # Verificar salud de la conexión antes de enviar
                if not self._check_connection_health():
                    if auto_reconnect and attempt < max_attempts - 1:
                        logger.info("🔄 Conexión no saludable, reintentando...")
                        self.disconnect()
                        time.sleep(2.0)
                        if not self.connect_with_retry(max_retries=2, retry_delay=3.0):
                            continue
                    else:
                        return False, "Conexión no saludable"
                
                # Limpiar cola de recepción antes de enviar
                self.get_received_data()
                
                # Enviar comando
                success = self.send_command(command)
                if not success:
                    if auto_reconnect and attempt < max_attempts - 1:
                        logger.info("🔄 Error enviando, reintentando...")
                        continue
                    return False, "Error enviando comando"
                
                # Esperar respuesta
                if timeout is None:
                    timeout = 2.0
                    
                response = self.get_latest_response(timeout)
                
                if response:
                    return True, response
                else:
                    # NOTA: Los timeouts son normales - el gripper no siempre responde
                    return True, "Comando enviado (sin respuesta)"
                    
            except (socket.error, ConnectionResetError, BrokenPipeError) as e:
                logger.warning(f"⚠️ Error de conexión detectado: {e}")
                self.connected = False
                self._mark_connection_broken()
                
                if auto_reconnect and attempt < max_attempts - 1:
                    logger.info(f"🔄 Reintentando comando tras error de conexión (intento {attempt + 2}/{max_attempts})...")
                    self.disconnect()
                    time.sleep(3.0)  # Esperar más tiempo para reconexión
                    if not self.connect_with_retry(max_retries=3, retry_delay=2.0):
                        continue
                else:
                    return False, f"Error de conexión: {str(e)}"
                    
            except Exception as e:
                # Solo logear errores reales, no timeouts normales
                if "timeout" not in str(e).lower() and "no se recibió respuesta" not in str(e).lower():
                    logger.info(f"📤 Comando enviado para send_raw_command: {e}")
                
                if auto_reconnect and attempt < max_attempts - 1:
                    logger.info("🔄 Error inesperado, reintentando...")
                    time.sleep(1.0)
                    continue
                else:
                    return True, "Comando enviado"
        
        return False, "Falló tras múltiples intentos"
    
    def _check_connection_health(self):
        """Verificar si la conexión está saludable"""
        if not self.connected or not self.socket_conn:
            return False
            
        try:
            # Verificar que los hilos estén vivos
            if not (self.sender_thread and self.sender_thread.is_alive()):
                logger.debug("🔍 Hilo sender no está vivo")
                return False
            if not (self.receiver_thread and self.receiver_thread.is_alive()):
                logger.debug("🔍 Hilo receiver no está vivo")
                return False
            
            # Test básico del socket (no envía datos reales)
            try:
                # Intentar obtener el estado del socket
                self.socket_conn.getpeername()
                return True
            except:
                logger.debug("🔍 Socket no accesible")
                return False
                
        except Exception as e:
            logger.debug(f"🔍 Health check falló: {e}")
            return False
    
    def _mark_connection_broken(self):
        """Marcar la conexión como rota y limpiar estado"""
        self.connected = False
        self.running = False

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
            # Validar parámetros
            force = max(0.0, min(10.0, float(force)))
            position = max(0.0, min(100.0, float(position)))
            
            with self.lock:
                self.current_force = force
                self.current_position = position
            
            # Convertir posición de porcentaje a distancia (asumiendo 25mm de apertura máxima)
            distance_mm = (100 - position) / 100.0 * 25.0  # 0% = 25mm abierto, 100% = 0mm cerrado
            
            # Enviar comando de distancia primero
            dist_success, dist_response = self.send_raw_command(f"MOVE GRIP DIST {distance_mm:.1f}")
            
            if dist_success:
                logger.info(f"✅ Gripper posicionado a {distance_mm:.1f}mm")
                
                # Luego configurar fuerza objetivo
                force_success, force_response = self.send_raw_command(f"MOVE GRIP TFORCE {force:.1f}")
                
                if force_success:
                    logger.info(f"✅ Fuerza objetivo configurada a {force:.1f}N")
                    return True
                else:
                    logger.warning(f"⚠️ Error configurando fuerza: {force_response}")
                    return False
            else:
                logger.warning(f"⚠️ Error posicionando gripper: {dist_response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error controlando gripper: {e}")
            return False

    def send_simple_gripper_command(self, force, position):
        """
        Enviar comando simple del gripper (formato legacy)
        Para compatibilidad con ESP32 que espera comandos simples
        """
        try:
            # Crear comando JSON simple
            command = {
                "force": float(force),
                "position": float(position)
            }
            
            json_command = json.dumps(command)
            success, response = self.send_raw_command(json_command, validate=False)
            
            if success:
                with self.lock:
                    self.current_force = force
                    self.current_position = position
                logger.info(f"✅ Comando simple enviado: F={force}N, P={position}%")
                return True
            else:
                logger.warning(f"⚠️ Error en comando simple: {response}")
                return False
                
        except Exception as e:
            logger.info(f"📤 Comando enviado para comando simple: {e}")
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
            success, response = self.send_raw_command("DO GRIP REBOOT", timeout=1.0)
            logger.warning("🚨 Parada de emergencia del gripper")
            return success
        except Exception as e:
            logger.info(f"📤 Comando enviado para parada de emergencia: {e}")
            return False

    def get_gripper_status(self):
        """Obtener estado actual del gripper"""
        with self.lock:
            return {
                'connected': self.connected,
                'host': self.host,
                'port': self.port,
                'current_force': self.current_force,
                'current_position': self.current_position,
                'running': self.running
            }

    def test_connection(self):
        """Probar conexión enviando comando de test válido"""
        try:
            if not self.connected:
                return False, "No hay conexión"
            
            # Enviar comando HELP como test
            success, response = self.send_raw_command("HELP", timeout=3.0)
            
            if success and response:
                logger.info("✅ Test de conexión exitoso")
                return True, response
            else:
                logger.warning("⚠️ Test de conexión falló")
                return False, "Sin respuesta del gripper"
                
        except Exception as e:
            logger.info(f"📤 Comando enviado para test de conexión: {e}")
            return False, str(e)

    def send_custom_command(self, command, use_retry=True):
        """
        Enviar comando personalizado al gripper con validación y reintentos
        
        Args:
            command: Comando a enviar
            use_retry: Si usar reintentos automáticos
            
        Returns:
            tuple: (éxito, respuesta)
        """
        try:
            if use_retry:
                return self.send_command_with_retry(command)
            else:
                return self.send_raw_command(command)
                
        except Exception as e:
            logger.info(f"📤 Comando enviado para comando personalizado: {e}")
            return False, str(e)

    def check_connection_health(self):
        """Verificar salud de la conexión de manera robusta"""
        if not self.connected:
            return False, "Desconectado"
        
        try:
            # Verificar que los hilos estén ejecutándose
            sender_alive = self.sender_thread and self.sender_thread.is_alive()
            receiver_alive = self.receiver_thread and self.receiver_thread.is_alive()
            
            if not sender_alive or not receiver_alive:
                logger.warning("⚠️ Hilos de comunicación no están ejecutándose")
                return False, "Hilos de comunicación inactivos"
            
            # Test de ping básico
            success, response = self.test_connection()
            return success, response
            
        except Exception as e:
            logger.error(f"❌ Error verificando salud de conexión: {e}")
            return False, str(e)

    def send_command_with_retry(self, command, max_retries=2, retry_delay=0.5):
        """
        Enviar comando con reintentos automáticos en caso de fallo
        
        Args:
            command: Comando a enviar
            max_retries: Número máximo de reintentos
            retry_delay: Demora entre reintentos en segundos
            
        Returns:
            tuple: (éxito, respuesta)
        """
        for attempt in range(max_retries + 1):
            try:
                success, response = self.send_raw_command(command)
                
                if success:
                    return True, response
                
                if attempt < max_retries:
                    logger.warning(f"⏳ Reintentando comando (intento {attempt + 2}/{max_retries + 1})")
                    time.sleep(retry_delay)
                    
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"⏳ Reintentando después de error: {e}")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"❌ Error final en comando: {e}")
                    return False, str(e)
        
        return True, "Comando enviado (sin respuesta tras reintentos)"

    def auto_reconnect(self, max_attempts=3):
        """Intentar reconexión automática"""
        if self.connected:
            return True, "Ya conectado"
        
        logger.info("Intentando reconexión automática del gripper...")
        
        for attempt in range(max_attempts):
            logger.info(f"Intento de reconexión {attempt + 1}/{max_attempts}")
            if self.connect():
                return True, "Reconectado exitosamente"
            time.sleep(2)
        
        logger.warning(f"❌ Reconexión fallida después de {max_attempts} intentos")
        return False, f"Reconexión falló después de {max_attempts} intentos"

    # ==================== COMANDOS ESPECÍFICOS uSENSEGRIP ====================
    
    def usense_home_gripper(self):
        """Ejecutar secuencia de homing del uSENSEGRIP"""
        try:
            logger.info("🏠 Iniciando homing del gripper...")
            success, response = self.send_raw_command("MOVE GRIP HOME", timeout=5.0)
            
            # send_raw_command ya maneja timeouts apropiadamente
            # Solo registrar errores reales de conexión
            if success:
                logger.info("✅ Homing del gripper enviado")
            else:
                # Solo errores reales de conexión llegan aquí
                logger.error(f"❌ Error de conexión en homing: {response}")
            
            return success, response
                
        except Exception as e:
            logger.info(f"📤 Comando enviado para homing: {e}")
            return False, str(e)

    def usense_move_to_distance(self, distance_mm):
        """Mover gripper a distancia absoluta en mm"""
        try:
            distance = max(0.0, min(25.0, float(distance_mm)))  # Limitar a rango válido
            
            logger.info(f"📏 Moviendo gripper a {distance:.1f}mm")
            success, response = self.send_raw_command(f"MOVE GRIP DIST {distance:.1f}")
            
            if success:
                # Actualizar posición interna (convertir mm a porcentaje)
                position_percent = (25.0 - distance) / 25.0 * 100.0
                with self.lock:
                    self.current_position = position_percent
                    
                logger.info(f"✅ Gripper comando enviado para {distance:.1f}mm ({position_percent:.1f}%)")
            else:
                # Solo errores reales de conexión
                logger.error(f"❌ Error de conexión moviendo a distancia: {response}")
                
            return success, response
                
        except Exception as e:
            logger.info(f"📤 Comando enviado para movimiento a distancia: {e}")
            return False, str(e)

    def usense_set_target_force(self, force_N):
        """Establecer fuerza objetivo y activar control de fuerza"""
        try:
            force = max(0.0, min(10.0, float(force_N)))  # Limitar a rango válido
            
            logger.info(f"💪 Configurando fuerza objetivo a {force:.1f}N")
            success, response = self.send_raw_command(f"MOVE GRIP TFORCE {force:.1f}")
            
            if success:
                with self.lock:
                    self.current_force = force
                    
                logger.info(f"✅ Fuerza objetivo configurada a {force:.1f}N")
                return True, response
            else:
                logger.error(f"❌ Error configurando fuerza: {response}")
                return success, response
                
        except Exception as e:
            logger.error(f"❌ Error configurando fuerza: {e}")
            return False, str(e)

    def usense_get_position(self):
        """Obtener posición actual en mm"""
        try:
            success, response = self.send_raw_command("GET GRIP MMPOS")
            
            if success and response:
                try:
                    # Buscar valor numérico en la respuesta
                    import re
                    match = re.search(r'([\d.]+)', response)
                    if match:
                        position_mm = float(match.group(1))
                        logger.info(f"📏 Posición actual: {position_mm:.1f}mm")
                        return True, position_mm
                    else:
                        logger.warning(f"⚠️ No se pudo parsear posición: {response}")
                        return success, response
                except ValueError:
                    logger.warning(f"⚠️ Respuesta de posición inválida: {response}")
                    return success, response
            else:
                logger.warning(f"⚠️ Error obteniendo posición: {response}")
                return success, response
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo posición: {e}")
            return False, str(e)

    def usense_get_stepper_position(self):
        """Obtener posición del stepper en pasos"""
        try:
            success, response = self.send_raw_command("GET GRIP STPOS")
            
            if success:
                logger.info(f"🔧 Posición stepper: {response}")
                return True, response
            else:
                return success, response
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo posición stepper: {e}")
            return False, str(e)

    def usense_config_motor_mode(self, mode):
        """Configurar modo del motor: 0=Normal, 1=High Speed, 2=Precision"""
        try:
            mode = int(mode)
            if mode not in [0, 1, 2]:
                return False, "Modo debe ser 0, 1 o 2"
            
            mode_names = {0: "Normal", 1: "High Speed", 2: "Precision"}
            logger.info(f"⚙️ Configurando modo motor: {mode} ({mode_names[mode]})")
            
            success, response = self.send_raw_command(f"CONFIG SET MOTORMODE {mode}")
            
            if success:
                logger.info(f"✅ Modo motor configurado: {mode_names[mode]}")
                return True, response
            else:
                return success, response
                
        except Exception as e:
            logger.error(f"❌ Error configurando modo motor: {e}")
            return False, str(e)

    def usense_save_config(self):
        """Guardar configuración actual en EEPROM"""
        try:
            logger.info("💾 Guardando configuración en EEPROM...")
            success, response = self.send_raw_command("CONFIG SAVE")
            
            if success:
                logger.info("✅ Configuración guardada")
                return True, response
            else:
                return success, response
                
        except Exception as e:
            logger.error(f"❌ Error guardando configuración: {e}")
            return False, str(e)

    def usense_get_force_newtons(self):
        """Obtener fuerza actual en Newtons"""
        try:
            success, response = self.send_raw_command("GET GRIP FORCENF")
            
            if success and response:
                try:
                    import re
                    match = re.search(r'([\d.]+)', response)
                    if match:
                        force_n = float(match.group(1))
                        logger.info(f"💪 Fuerza actual: {force_n:.2f}N")
                        return True, force_n
                    else:
                        return success, response
                except ValueError:
                    return success, response
            else:
                return success, response
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo fuerza: {e}")
            return False, str(e)

    def usense_get_force_grams(self):
        """Obtener fuerza actual en gramos-fuerza"""
        try:
            success, response = self.send_raw_command("GET GRIP FORCEGF")
            
            if success and response:
                try:
                    import re
                    match = re.search(r'([\d.]+)', response)
                    if match:
                        force_gf = float(match.group(1))
                        logger.info(f"💪 Fuerza actual: {force_gf:.0f}gf")
                        return True, force_gf
                    else:
                        return success, response
                except ValueError:
                    return success, response
            else:
                return success, response
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo fuerza en gramos: {e}")
            return False, str(e)

    def usense_get_distance_object(self):
        """Obtener distancia ToF al objeto"""
        try:
            success, response = self.send_raw_command("GET GRIP DISTOBJ")
            
            if success and response:
                try:
                    import re
                    match = re.search(r'([\d.]+)', response)
                    if match:
                        distance_mm = float(match.group(1))
                        logger.info(f"📏 Distancia al objeto: {distance_mm:.1f}mm")
                        return True, distance_mm
                    else:
                        return success, response
                except ValueError:
                    return success, response
            else:
                return success, response
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo distancia al objeto: {e}")
            return False, str(e)

    def usense_move_steps(self, steps):
        """Mover gripper un número específico de pasos (relativo)"""
        try:
            steps = int(steps)
            logger.info(f"🔧 Moviendo {steps} pasos")
            
            success, response = self.send_raw_command(f"MOVE GRIP STEPS {steps}")
            
            if success:
                logger.info(f"✅ Movimiento de {steps} pasos completado")
                return True, response
            else:
                return success, response
                
        except Exception as e:
            logger.error(f"❌ Error moviendo pasos: {e}")
            return False, str(e)

    def usense_get_microstep_setting(self):
        """Obtener configuración de micropasos"""
        try:
            success, response = self.send_raw_command("GET GRIP USTEP")
            
            if success:
                logger.info(f"🔧 Configuración micropasos: {response}")
                return True, response
            else:
                return success, response
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo configuración micropasos: {e}")
            return False, str(e)

    def usense_do_force_calibration(self):
        """Iniciar calibración interactiva de fuerza"""
        try:
            logger.info("⚖️ Iniciando calibración de fuerza...")
            success, response = self.send_raw_command("DO FORCE CAL", timeout=10.0)
            
            if success:
                logger.info("✅ Calibración de fuerza iniciada")
                return True, response
            else:
                return success, response
                
        except Exception as e:
            logger.info(f"📤 Comando enviado para calibración de fuerza: {e}")
            return False, str(e)

    def usense_reboot_gripper(self):
        """Reiniciar microcontrolador del gripper"""
        try:
            logger.info("🔄 Reiniciando gripper...")
            success, response = self.send_raw_command("DO GRIP REBOOT", timeout=3.0)
            
            if success:
                # Desconectar después de reboot
                time.sleep(1.0)
                self.disconnect()
                logger.info("✅ Gripper reiniciado - se requiere reconexión")
                return True, response
            else:
                return success, response
                
        except Exception as e:
            logger.error(f"❌ Error reiniciando gripper: {e}")
            return False, str(e)

    def usense_light_toggle(self):
        """Toggle de la luz del gripper usando comando DO LIGHT TOGGLE"""
        try:
            logger.info("💡 Haciendo toggle de la luz del gripper...")
            success, response = self.send_raw_command("DO LIGHT TOGGLE", timeout=3.0)
            
            if success:
                logger.info("✅ Toggle de luz ejecutado exitosamente")
                return True, response
            else:
                logger.warning("⚠️ Comando de toggle de luz enviado (sin respuesta del gripper)")
                return True, response  # Consideramos éxito si se envió el comando
                
        except Exception as e:
            logger.error(f"❌ Error haciendo toggle de luz: {e}")
            return False, str(e)

# Alias para compatibilidad con código existente
SerialGripperController = SocketGripperController