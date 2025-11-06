"""
Controlador serie COM del gripper para la aplicación web
Convertido de Bluetooth a comunicación serie para Linux
"""

import serial
import serial.tools.list_ports
import time
import threading
import logging
import json
import glob
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class SerialGripperController:
    def __init__(self, port=None, baudrate=115200, debug=True):
        """
        Inicializar controlador serie del gripper
        
        Args:
            port: Puerto serie (ej: '/dev/ttyUSB0', '/dev/ttyACM0'). Si None, se auto-detecta
            baudrate: Velocidad de comunicación (típicamente 115200 para ESP32/Arduino)
            debug: Habilitar logging detallado
        """
        self.port = port
        self.baudrate = baudrate
        self.debug = debug
        
        # Estado de conexión
        self.serial_conn = None
        self.connected = False
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
        
        # Cola de comandos
        self.command_queue = []
        
        # Auto-detectar puerto si no se especifica
        if not self.port:
            # Priorizar /dev/ttyACM0 (típico para uSENSEGRIP)
            if os.path.exists("/dev/ttyACM0"):
                self.port = "/dev/ttyACM0"
                logger.info("🎯 Usando puerto prioritario: /dev/ttyACM0")
            else:
                self.port = self.find_gripper_port()
        
        logger.info(f"SerialGripperController inicializado - Puerto: {self.port}")

    def find_gripper_port(self):
        """
        Auto-detectar puerto serie del gripper en Linux
        Busca en puertos comunes y prueba conectarse
        """
        logger.info("🔍 Buscando puerto serie del gripper...")
        
        # Listar puertos serie disponibles
        available_ports = []
        
        # Métodos para detectar puertos en Linux
        try:
            # Usando pyserial
            ports = serial.tools.list_ports.comports()
            for port in ports:
                available_ports.append(port.device)
                if self.debug:
                    logger.debug(f"Puerto encontrado: {port.device} - {port.description}")
            
        except Exception as e:
            logger.warning(f"Error usando pyserial list_ports: {e}")
            
            # Método alternativo: buscar en /dev/
            try:
                # Puertos USB comunes en Linux
                usb_patterns = [
                    "/dev/ttyUSB*",
                    "/dev/ttyACM*", 
                    "/dev/ttyS*"
                ]
                
                for pattern in usb_patterns:
                    ports = glob.glob(pattern)
                    for port in sorted(ports):
                        if os.path.exists(port):
                            available_ports.append(port)
                            
            except Exception as e2:
                logger.error(f"Error buscando puertos manualmente: {e2}")
        
        if not available_ports:
            logger.warning("❌ No se encontraron puertos serie")
            return None
        
        logger.info(f"📋 Puertos disponibles: {available_ports}")
        
        # Probar cada puerto para detectar el gripper
        for port_path in available_ports:
            logger.info(f"🔌 Probando puerto: {port_path}")
            
            if self.test_port_for_gripper(port_path):
                logger.info(f"✅ Gripper detectado en: {port_path}")
                return port_path
        
        logger.warning("❌ No se detectó gripper en ningún puerto")
        return available_ports[0] if available_ports else None

    def test_port_for_gripper(self, port_path):
        """
        Probar si un puerto específico tiene el gripper conectado
        Intenta conectar y enviar comando HELP
        """
        try:
            # Intentar abrir puerto
            test_serial = serial.Serial(
                port=port_path,
                baudrate=self.baudrate,
                timeout=2.0,
                write_timeout=2.0
            )
            
            time.sleep(0.5)  # Esperar estabilización
            
            # Limpiar buffer
            test_serial.flushInput()
            test_serial.flushOutput()
            
            # Enviar comando HELP
            test_serial.write(b"HELP\n")
            test_serial.flush()
            
            time.sleep(0.5)
            
            # Leer respuesta
            response = ""
            start_time = time.time()
            
            while (time.time() - start_time) < 2.0:
                if test_serial.in_waiting > 0:
                    data = test_serial.read(test_serial.in_waiting).decode('utf-8', errors='ignore')
                    response += data
                    
                    # Si encontramos indicadores de gripper
                    if any(keyword in response.upper() for keyword in ['HELP', 'COMMAND', 'GRIP', 'MOTOR', 'SERVO']):
                        test_serial.close()
                        logger.info(f"✅ Respuesta del gripper en {port_path}: {response[:100]}...")
                        return True
                
                time.sleep(0.1)
            
            test_serial.close()
            
            if response.strip():
                logger.debug(f"Respuesta en {port_path}: {response[:50]}...")
            
            return False
            
        except Exception as e:
            if self.debug:
                logger.debug(f"Error probando {port_path}: {e}")
            return False

    def connect(self):
        """Establecer conexión serie con el gripper"""
        try:
            current_time = time.time()
            
            # Evitar intentos de conexión muy frecuentes
            if current_time - self.last_connection_attempt < 2.0:
                return self.connected
            
            self.last_connection_attempt = current_time
            
            # Si no hay puerto definido, intentar auto-detectar
            if not self.port:
                self.port = self.find_gripper_port()
                if not self.port:
                    logger.error("❌ No se pudo detectar puerto del gripper")
                    return False
            
            if self.debug:
                logger.info(f"Conectando a gripper en {self.port} @ {self.baudrate} bps")
            
            # Crear conexión serie
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.recv_timeout,
                write_timeout=self.connection_timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            # Esperar estabilización de la conexión
            time.sleep(1.0)
            
            # Limpiar buffers
            self.serial_conn.flushInput()
            self.serial_conn.flushOutput()
            
            self.connected = True
            logger.info("✅ Conexión serie establecida con gripper")
            
            # Enviar comando de inicialización y HELP
            self.send_raw_command("INIT")
            time.sleep(0.5)
            self.request_help_commands()
            
            return True
            
        except serial.SerialException as e:
            if self.debug:
                logger.warning(f"Error de puerto serie conectando a gripper: {e}")
            
            self.connected = False
            if self.serial_conn:
                try:
                    self.serial_conn.close()
                except:
                    pass
                self.serial_conn = None
            
            return False
        except Exception as e:
            logger.error(f"Error inesperado conectando: {e}")
            self.connected = False
            return False

    def request_help_commands(self):
        """Solicitar lista de comandos disponibles enviando HELP"""
        try:
            logger.info("📋 Solicitando comandos disponibles...")
            
            if self.send_raw_command("HELP"):
                # Leer respuesta del comando HELP
                time.sleep(0.5)  # Dar tiempo al dispositivo para responder
                
                help_response = ""
                start_time = time.time()
                
                # Leer respuesta por hasta 3 segundos
                while (time.time() - start_time) < 3.0:
                    response = self.recv_response(timeout=0.5)
                    if response:
                        help_response += response + "\n"
                    else:
                        break
                
                if help_response.strip():
                    logger.info("📋 Comandos disponibles del gripper:")
                    for line in help_response.strip().split('\n'):
                        if line.strip():
                            logger.info(f"   {line.strip()}")
                else:
                    logger.warning("⚠️ No se recibió respuesta al comando HELP")
            
        except Exception as e:
            logger.error(f"Error solicitando comandos HELP: {e}")

    def disconnect(self):
        """Cerrar conexión serie"""
        try:
            with self.lock:
                if self.serial_conn:
                    if self.debug:
                        logger.info("Cerrando conexión serie del gripper")
                    
                    try:
                        # Enviar comando de desconexión
                        self.send_raw_command("DISCONNECT", timeout=1.0)
                    except:
                        pass  # Ignorar errores al desconectar
                    
                    self.serial_conn.close()
                    self.serial_conn = None
                
                self.connected = False
            
            logger.info("✅ Desconectado del gripper serie")
            
        except Exception as e:
            logger.error(f"Error desconectando gripper: {e}")

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
            # Comandos de compatibilidad
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
        
        return False, f"Comando '{command}' no reconocido para uSENSEGRIP"

    def send_raw_command(self, command, timeout=None, validate=True):
        """
        Enviar comando crudo al gripper por puerto serie con validación opcional
        
        Args:
            command: Comando a enviar
            timeout: Timeout específico para este comando
            validate: Si True, valida el comando antes de enviar
        """
        if not self.connected or not self.serial_conn:
            return False
        
        # Validar comando si se solicita
        if validate:
            is_valid, error_msg = self.validate_usense_command(command)
            if not is_valid:
                if self.debug:
                    logger.warning(f"Comando inválido: {error_msg}")
                return False
        
        try:
            # Agregar salto de línea si no está presente
            data = command if command.endswith("\n") else command + "\n"
            
            # Configurar timeout temporal si se especifica
            original_timeout = None
            if timeout:
                original_timeout = self.serial_conn.timeout
                self.serial_conn.timeout = timeout
            
            # Enviar comando
            self.serial_conn.write(data.encode("utf-8"))
            self.serial_conn.flush()  # Asegurar envío inmediato
            
            if self.debug:
                logger.debug(f"→ TX: {command.strip()}")
            
            # Restaurar timeout original
            if original_timeout is not None:
                self.serial_conn.timeout = original_timeout
            
            return True
            
        except serial.SerialException as e:
            logger.warning(f"Error enviando comando serie: {e}")
            self.connected = False
            return False
        except Exception as e:
            logger.error(f"Error inesperado enviando comando: {e}")
            return False

    def recv_response(self, timeout=None, max_lines=1):
        """
        Recibir respuesta del gripper por puerto serie con optimizaciones
        
        Args:
            timeout: Tiempo máximo de espera en segundos
            max_lines: Máximo número de líneas a leer (1 para respuesta simple)
        """
        if not self.connected or not self.serial_conn:
            return None
        
        try:
            # Configurar timeout temporal si se especifica
            original_timeout = None
            if timeout:
                original_timeout = self.serial_conn.timeout
                self.serial_conn.timeout = timeout
            
            responses = []
            buf = b""
            start_time = time.time()
            effective_timeout = timeout or self.recv_timeout
            
            while len(responses) < max_lines:
                try:
                    # Verificar timeout total
                    if time.time() - start_time > effective_timeout:
                        break
                    
                    if self.serial_conn.in_waiting > 0:
                        # Leer todos los bytes disponibles de una vez
                        data = self.serial_conn.read(self.serial_conn.in_waiting)
                        if not data:
                            break
                        
                        buf += data
                        
                        # Procesar líneas completas en el buffer
                        while b"\n" in buf or b"\r" in buf:
                            if b"\n" in buf:
                                line_end = buf.find(b"\n")
                            else:
                                line_end = buf.find(b"\r")
                            
                            line = buf[:line_end]
                            buf = buf[line_end + 1:]
                            
                            # Limpiar caracteres de control
                            line = line.strip(b"\r\n")
                            
                            if line:  # Solo agregar líneas no vacías
                                try:
                                    decoded_line = line.decode("utf-8", errors="ignore").strip()
                                    if decoded_line:
                                        responses.append(decoded_line)
                                        if len(responses) >= max_lines:
                                            break
                                except UnicodeDecodeError:
                                    continue
                        
                        # Límite de buffer para evitar memoria excesiva
                        if len(buf) > 2048:
                            buf = buf[-1024:]  # Mantener solo los últimos 1024 bytes
                    else:
                        # No hay datos, esperar un poco más eficientemente
                        time.sleep(0.005)  # 5ms en lugar de 10ms
                        
                except serial.SerialTimeoutException:
                    break  # Timeout normal
                except serial.SerialException as e:
                    logger.warning(f"Error serie recibiendo: {e}")
                    self.connected = False
                    return None
                
            # Restaurar timeout original
            if original_timeout is not None:
                self.serial_conn.timeout = original_timeout
            
            # Retornar la primera respuesta o todas como texto
            if responses:
                if max_lines == 1:
                    result = responses[0]
                else:
                    result = "\n".join(responses)
                
                if self.debug:
                    logger.debug(f"← RX: {result}")
                
                return result
            
            # Si no hay respuestas, revisar buffer restante
            if buf:
                remaining = buf.decode("utf-8", errors="ignore").strip()
                if remaining and self.debug:
                    logger.debug(f"← RX (parcial): {remaining}")
                return remaining if remaining else None
            
            return None
            
        except serial.SerialException as e:
            logger.warning(f"Error recibiendo respuesta serie: {e}")
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
                'port': self.port,
                'baudrate': self.baudrate,
                'last_command_time': self.last_command_time,
                'available_commands': [
                    'open_gripper', 'close_gripper', 'set_position', 
                    'emergency_stop', 'send_custom_command', 'request_help'
                ]
            }

    def test_connection(self):
        """Probar conexión enviando comando de test válido"""
        try:
            if not self.connected:
                if not self.connect():
                    return False
            
            # Usar comando GET GRIP MMpos que siempre debe responder
            success = self.send_raw_command("GET GRIP MMpos")
            
            if success:
                # Esperar respuesta
                response = self.recv_response(timeout=2.0)
                if response:
                    try:
                        # Intentar parsear como número para validar respuesta
                        float(response.strip())
                        logger.info("✅ Test de conexión exitoso - Posición obtenida")
                        return True
                    except ValueError:
                        # Si no es un número, revisar si es una respuesta válida del gripper
                        if any(keyword in response.upper() for keyword in ['MM', 'POS', 'GRIP', 'ERROR']):
                            logger.info("✅ Test de conexión exitoso - Respuesta válida recibida")
                            return True
                        else:
                            logger.warning(f"Respuesta inesperada del test: {response}")
                else:
                    logger.warning("No se recibió respuesta al test de conexión")
            
            return False
            
        except Exception as e:
            logger.error(f"Error en test de conexión: {e}")
            return False

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
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            if use_retry:
                # Usar método con reintentos
                return self.send_command_with_retry(command)
            else:
                # Método simple sin reintentos
                success = self.send_raw_command(command)
                
                if success:
                    response = self.recv_response(timeout=2.0)
                    return True, response or "Comando enviado (sin respuesta)"
                else:
                    return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error enviando comando personalizado: {e}")
            return False, str(e)

    def check_connection_health(self):
        """Verificar salud de la conexión de manera robusta"""
        if not self.connected:
            return False
        
        try:
            # Verificar que el puerto sigue abierto
            if not self.serial_conn or not self.serial_conn.is_open:
                self.connected = False
                return False
            
            # Usar comando GET GRIP MMpos que siempre debe responder
            success = self.send_raw_command("GET GRIP MMpos", timeout=1.0, validate=False)
            
            if success:
                # Intentar leer respuesta
                response = self.recv_response(timeout=1.0)
                return response is not None
            
            return False
            
        except Exception as e:
            if self.debug:
                logger.debug(f"Error verificando salud de conexión: {e}")
            self.connected = False
            return False

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
                # Verificar conexión antes del intento
                if not self.connected:
                    if not self.auto_reconnect():
                        continue
                
                # Enviar comando
                success = self.send_raw_command(command)
                if success:
                    response = self.recv_response(timeout=2.0)
                    return True, response
                
                # Si falla y no es el último intento, intentar reconectar
                if attempt < max_retries:
                    logger.warning(f"Fallo enviando comando, reintentando ({attempt + 1}/{max_retries})")
                    
                    # Verificar salud de conexión
                    if not self.check_connection_health():
                        self.auto_reconnect(max_attempts=1)
                    
                    time.sleep(retry_delay)
                
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Error en intento {attempt + 1}: {e}")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Error final enviando comando: {e}")
        
        return False, "Comando falló después de todos los reintentos"

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

    # ==================== COMANDOS ESPECÍFICOS uSENSEGRIP ====================
    
    def usense_home_gripper(self):
        """Ejecutar secuencia de homing del uSENSEGRIP"""
        try:
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            success = self.send_raw_command("MOVE GRIP HOME")
            if success:
                logger.info("🏠 Iniciando homing del gripper uSENSEGRIP")
                # Esperar confirmación
                time.sleep(0.5)
                response = self.recv_response(timeout=2.0)
                return True, response or "Homing iniciado"
            else:
                return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error en homing: {e}")
            return False, str(e)

    def usense_move_to_distance(self, distance_mm):
        """Mover gripper a distancia absoluta en mm"""
        try:
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            # Validar distancia
            distance_mm = max(0.0, min(100.0, float(distance_mm)))
            
            command = f"MOVE GRIP DIST {distance_mm:.2f}"
            success = self.send_raw_command(command)
            
            if success:
                logger.info(f"📏 Moviendo gripper a {distance_mm}mm")
                time.sleep(0.5)
                response = self.recv_response(timeout=2.0)
                return True, response or f"Movimiento a {distance_mm}mm iniciado"
            else:
                return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error moviendo a distancia: {e}")
            return False, str(e)

    def usense_set_target_force(self, force_N):
        """Establecer fuerza objetivo y activar control de fuerza"""
        try:
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            # Validar fuerza
            force_N = max(0.0, min(50.0, float(force_N)))
            
            command = f"MOVE GRIP TFORCE {force_N:.2f}"
            success = self.send_raw_command(command)
            
            if success:
                logger.info(f"💪 Estableciendo fuerza objetivo: {force_N}N")
                time.sleep(0.5)
                response = self.recv_response(timeout=2.0)
                
                # Actualizar estado local
                with self.lock:
                    self.current_force = force_N
                
                return True, response or f"Fuerza objetivo: {force_N}N"
            else:
                return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error estableciendo fuerza: {e}")
            return False, str(e)

    def usense_get_position(self):
        """Obtener posición actual en mm"""
        try:
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            success = self.send_raw_command("GET GRIP MMpos")
            
            if success:
                time.sleep(0.5)
                response = self.recv_response(timeout=2.0)
                
                if response:
                    try:
                        # Parsear respuesta numérica
                        position = float(response.split()[-1])
                        logger.info(f"📍 Posición actual: {position}mm")
                        return True, f"Posición: {position}mm"
                    except:
                        return True, f"Respuesta: {response}"
                else:
                    return False, "Sin respuesta"
            else:
                return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error obteniendo posición: {e}")
            return False, str(e)

    def usense_get_stepper_position(self):
        """Obtener posición del stepper en pasos"""
        try:
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            success = self.send_raw_command("GET GRIP STpos")
            
            if success:
                time.sleep(0.5)
                response = self.recv_response(timeout=2.0)
                return True, response or "Sin respuesta"
            else:
                return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error obteniendo posición stepper: {e}")
            return False, str(e)

    def usense_config_motor_mode(self, mode):
        """Configurar modo del motor: 0=Normal, 1=High Speed, 2=Precision"""
        try:
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            # Validar modo
            mode = int(mode)
            if mode not in [0, 1, 2]:
                return False, "Modo debe ser 0, 1 o 2"
            
            mode_names = {0: "Normal", 1: "High Speed", 2: "Precision"}
            
            command = f"CONFIG SET MOTORMODE {mode}"
            success = self.send_raw_command(command)
            
            if success:
                logger.info(f"⚙️ Configurando modo motor: {mode_names[mode]} ({mode})")
                time.sleep(0.5)
                response = self.recv_response(timeout=2.0)
                return True, response or f"Modo {mode_names[mode]} establecido"
            else:
                return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error configurando modo motor: {e}")
            return False, str(e)

    def usense_save_config(self):
        """Guardar configuración actual en EEPROM"""
        try:
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            success = self.send_raw_command("CONFIG SAVE")
            
            if success:
                logger.info("💾 Guardando configuración en EEPROM")
                time.sleep(1.0)  # Dar más tiempo para escribir EEPROM
                response = self.recv_response(timeout=3.0)
                return True, response or "Configuración guardada"
            else:
                return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
            return False, str(e)

    def usense_get_force_newtons(self):
        """Obtener fuerza actual en Newtons"""
        try:
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            success = self.send_raw_command("GET GRIP ForceNf")
            
            if success:
                time.sleep(0.5)
                response = self.recv_response(timeout=2.0)
                
                if response:
                    try:
                        # Parsear respuesta numérica
                        force = float(response.split()[-1])
                        logger.info(f"💪 Fuerza actual: {force}N")
                        return True, f"Fuerza: {force}N"
                    except:
                        return True, f"Respuesta: {response}"
                else:
                    return False, "Sin respuesta"
            else:
                return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error obteniendo fuerza: {e}")
            return False, str(e)

    def usense_get_force_grams(self):
        """Obtener fuerza actual en gramos-fuerza"""
        try:
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            success = self.send_raw_command("GET GRIP ForceGf")
            
            if success:
                time.sleep(0.5)
                response = self.recv_response(timeout=2.0)
                
                if response:
                    try:
                        # Parsear respuesta numérica
                        force = float(response.split()[-1])
                        logger.info(f"💪 Fuerza actual: {force}gf")
                        return True, f"Fuerza: {force}gf"
                    except:
                        return True, f"Respuesta: {response}"
                else:
                    return False, "Sin respuesta"
            else:
                return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error obteniendo fuerza: {e}")
            return False, str(e)

    def usense_get_distance_object(self):
        """Obtener distancia ToF al objeto"""
        try:
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            success = self.send_raw_command("GET GRIP DISTobj")
            
            if success:
                time.sleep(0.5)
                response = self.recv_response(timeout=2.0)
                
                if response:
                    try:
                        # Parsear respuesta numérica
                        distance = float(response.split()[-1])
                        logger.info(f"📏 Distancia al objeto: {distance}mm")
                        return True, f"Distancia objeto: {distance}mm"
                    except:
                        return True, f"Respuesta: {response}"
                else:
                    return False, "Sin respuesta"
            else:
                return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error obteniendo distancia objeto: {e}")
            return False, str(e)

    def usense_move_steps(self, steps):
        """Mover gripper un número específico de pasos (relativo)"""
        try:
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            # Validar pasos
            steps = int(steps)
            if abs(steps) > 50000:  # Límite de seguridad
                return False, "Número de pasos excede límite de seguridad (±50000)"
            
            command = f"MOVE GRIP STEPS {steps}"
            success = self.send_raw_command(command)
            
            if success:
                logger.info(f"🔢 Moviendo {steps} pasos")
                time.sleep(0.5)
                response = self.recv_response(timeout=2.0)
                return True, response or f"Movimiento {steps} pasos iniciado"
            else:
                return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error moviendo pasos: {e}")
            return False, str(e)

    def usense_get_microstep_setting(self):
        """Obtener configuración de micropasos"""
        try:
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            success = self.send_raw_command("GET GRIP uSTEP")
            
            if success:
                time.sleep(0.5)
                response = self.recv_response(timeout=2.0)
                return True, response or "Sin respuesta"
            else:
                return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error obteniendo micropasos: {e}")
            return False, str(e)

    def usense_do_force_calibration(self):
        """Iniciar calibración interactiva de fuerza"""
        try:
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            success = self.send_raw_command("DO FORCE CAL")
            
            if success:
                logger.info("🔧 Iniciando calibración de fuerza")
                time.sleep(0.5)
                response = self.recv_response(timeout=3.0)
                return True, response or "Calibración de fuerza iniciada"
            else:
                return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error en calibración de fuerza: {e}")
            return False, str(e)

    def usense_reboot_gripper(self):
        """Reiniciar microcontrolador del gripper"""
        try:
            if not self.connected:
                if not self.connect():
                    return False, "No conectado"
            
            success = self.send_raw_command("DO GRIP REBOOT")
            
            if success:
                logger.warning("🔄 Reiniciando gripper - conexión se perderá")
                time.sleep(0.5)
                response = self.recv_response(timeout=2.0)
                
                # Desconectar después del reboot
                self.disconnect()
                
                return True, response or "Gripper reiniciado"
            else:
                return False, "Error enviando comando"
                
        except Exception as e:
            logger.error(f"Error reiniciando gripper: {e}")
            return False, str(e)