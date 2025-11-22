"""
Controlador UR5 con RTDE activado para la aplicación web
Versión con conexión real al robot UR5e mediante URRTDE
"""

import numpy as np
import time
import threading
import logging
from datetime import datetime

# Importaciones de RTDE para conexión real con UR5e
try:
    import rtde_control
    import rtde_receive
    import rtde_io
    RTDE_AVAILABLE = True
    print("✅ RTDE disponible - Conexión real con UR5e activada")
except ImportError as e:
    RTDE_AVAILABLE = False
    print(f"❌ RTDE no disponible: {e}")
    print("🔌 Funcionando en modo desconectado")

# Importaciones para control Xbox (opcional)
try:
    import pygame
    PYGAME_AVAILABLE = True
    print("✅ pygame disponible - Control Xbox habilitado")
except ImportError:
    PYGAME_AVAILABLE = False
    print("❌ pygame no disponible - Control Xbox deshabilitado")

logger = logging.getLogger(__name__)

class UR5WebController:
    def __init__(self, robot_ip="192.168.0.101"):
        """Inicializar controlador UR5 para aplicación web"""
        self.robot_ip = robot_ip
        self.control = None
        self.receive = None
        self.io = None
        
        # Parámetros de movimiento - Usando valores de move_controler.py
        self.joint_speed = 2.0
        self.joint_accel = 3.0
        self.linear_speed = 0.5
        self.linear_accel = 1.5
        
        # NUEVO: Parámetros de blend radius para movimientos suaves
        self.joint_blend_radius = 0.02  # metros
        self.linear_blend_radius = 0.005  # metros
        
        # Configuración de velocidades (múltiples niveles)
        self.speed_levels = [0.1, 0.3, 0.5, 0.8, 1.0]
        self.current_speed_level = 1  # Iniciado en nivel 2 (30%)
        
        # Estados
        self.connected = False
        self.movement_active = False
        self.emergency_stop_active = False
        self.emergency_stop_time = 0
        
        # Posición home
        self.home_joint_angles_deg = [-58.49, -78.0, -98.4, -94.67, 88.77, -109.86]
        self.home_joint_angles_rad = np.radians(self.home_joint_angles_deg)
        
        # Tolerancias - Mejoradas
        self.position_tolerance_joint = 0.005  # Más estricta para joints
        self.position_tolerance_tcp = 0.001   # Más estricta para TCP
        
        # Límites del workspace
        self.UR5E_MAX_REACH = 0.85
        self.UR5E_MIN_REACH = 0.18
        
        # Lock para acceso thread-safe
        self.lock = threading.Lock()
        
        # Control Xbox - SIEMPRE HABILITADO - Usando implementación de move_controler.py
        self.xbox_enabled = True  # SIEMPRE TRUE
        self.joystick = None
        self.xbox_thread = None
        self.xbox_running = False
        self.previous_button_states = {}
        self.control_mode = "joint"  # "joint" o "linear"
        
        # Estados para detección de cambios
        self.movement_thread = None
        self.stop_movement = False
        
        # Control de tiempo para evitar spam de movimientos
        self.last_movement_time = 0
        self.last_speed_change = 0  # Control de tiempo para cambios de velocidad
        self.movement_cooldown = 0.15  # AUMENTADO de 0.08 a 0.15 - reducir frecuencia drásticamente
        
        # Incrementos para movimientos - REDUCIDOS drásticamente para eliminar vibración
        self.joint_increment = 0.02  # REDUCIDO de 0.04 a 0.02 - pasos muy pequeños
        self.linear_increment = 0.003  # REDUCIDO de 0.006 a 0.003 - pasos muy pequeños
        
        # NUEVO: Sistema de filtros para suavizar movimientos
        self.input_filter = {}  # Para filtrar entrada del joystick
        self.filter_alpha = 0.1  # REDUCIDO de 0.2 a 0.1 - filtrado mucho más agresivo
        self.movement_accumulator = {}  # Acumulador para movimientos pequeños
        self.accumulated_movement = [0.0] * 6  # Acumulador de movimientos por eje
        self.accumulator_threshold = 0.01  # REDUCIDO de 0.02 a 0.01 - menos acumulación = movimientos más frecuentes
        self.movement_threshold = 0.03  # AUMENTADO de 0.01 a 0.03 - requiere más acumulación
        
        # NUEVO: Control de movimientos suaves
        self.min_movement_threshold = 0.01  # Movimiento mínimo para considerar
        self.position_check_enabled = True  # Verificar posición antes de mover
        self.last_position_check = 0
        self.position_check_interval = 0.1  # 100ms entre verificaciones de posición
        
        # Debug mejorado para botones
        self.debug_mode = True
        self.last_debug_time = 0
        self.debug_interval = 0.3
        
        # Intentar conectar al robot
        if RTDE_AVAILABLE:
            self.initialize_robot()
        
        # Inicializar Xbox controller automáticamente
        self.initialize_xbox_controller()
        
        logger.info(f"UR5WebController inicializado - IP: {robot_ip}")
        logger.info(f"🎮 Control Xbox: {'Habilitado' if self.xbox_enabled else 'Deshabilitado'}")

    def initialize_robot(self):
        """Inicializar conexión con el robot UR5e mediante RTDE"""
        try:
            if not RTDE_AVAILABLE:
                logger.warning("🔌 RTDE no disponible - funcionando en modo desconectado")
                self.connected = False
                return False
            
            logger.info(f"🤖 Conectando al robot UR5e en {self.robot_ip}...")
            
            # Intentar conexión RTDE con manejo de conflictos
            try:
                self.control = rtde_control.RTDEControlInterface(self.robot_ip)
                self.receive = rtde_receive.RTDEReceiveInterface(self.robot_ip)
                self.io = rtde_io.RTDEIOInterface(self.robot_ip)
                
                # Verificar que las conexiones estén activas
                if self.control.isConnected() and self.receive.isConnected():
                    self.connected = True
                    logger.info("✅ Robot UR5e conectado exitosamente!")
                    
                    # Verificar estado del robot
                    robot_mode = self.receive.getRobotMode()
                    safety_mode = self.receive.getSafetyMode()
                    
                    logger.info(f"🔧 Modo del robot: {robot_mode}")
                    logger.info(f"🛡️  Modo de seguridad: {safety_mode}")
                    
                    return True
                else:
                    logger.error("❌ Falló la conexión con el robot")
                    self.connected = False
                    return False
                    
            except Exception as rtde_error:
                error_msg = str(rtde_error)
                if "already in use" in error_msg or "EtherNet/IP" in error_msg:
                    logger.warning("⚠️ Conflicto con otros adaptadores de red en el robot")
                    logger.warning("💡 Solución: Desactivar EtherNet/IP, PROFINET o MODBUS en PolyScope")
                    logger.info("🔧 Funcionando en modo híbrido (conexión básica)")
                    
                    # Intentar solo conexión de recepción
                    try:
                        self.receive = rtde_receive.RTDEReceiveInterface(self.robot_ip)
                        if self.receive.isConnected():
                            self.connected = True
                            logger.info("✅ Conexión de solo lectura establecida")
                            return True
                    except:
                        pass
                        
                self.connected = False
                logger.error(f"❌ Error de conexión RTDE: {rtde_error}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error general inicializando conexión: {e}")
            self.connected = False
            return False

    def is_connected(self):
        """Verificar si el robot está conectado"""
        if not RTDE_AVAILABLE:
            return False
        
        try:
            # Verificar al menos la conexión de recepción
            return (self.connected and 
                   self.receive is not None and
                   self.receive.isConnected())
        except:
            return False
    
    def can_control(self):
        """Verificar si se pueden enviar comandos de control"""
        try:
            return (self.is_connected() and 
                   self.control is not None and 
                   self.control.isConnected())
        except:
            return False

    def get_current_joint_positions(self):
        """Obtener posiciones actuales de las articulaciones"""
        try:
            if self.is_connected():
                # Obtener posiciones reales del robot
                return self.receive.getActualQ()
            else:
                # Modo desconectado: retornar posición home simulada
                return self.home_joint_angles_rad
        except Exception as e:
            logger.error(f"Error obteniendo posiciones articulares: {e}")
            return self.home_joint_angles_rad

    def get_current_tcp_pose(self):
        """Obtener pose actual del TCP"""
        try:
            if self.is_connected():
                # Obtener pose real del robot
                return self.receive.getActualTCPPose()
            else:
                # Modo desconectado: retornar pose home simulada
                return [0.3, -0.2, 0.5, 0, 0, 0]
        except Exception as e:
            logger.error(f"Error obteniendo pose TCP: {e}")
            return [0.3, -0.2, 0.5, 0, 0, 0]

    def get_current_pose(self):
        """Obtener pose actual formateada para la web"""
        try:
            tcp_pose = self.get_current_tcp_pose()
            # Convertir a mm y grados para la interfaz
            return [
                round(tcp_pose[0] * 1000, 2),  # X en mm
                round(tcp_pose[1] * 1000, 2),  # Y en mm
                round(tcp_pose[2] * 1000, 2),  # Z en mm
                round(np.degrees(tcp_pose[3]), 2),  # RX en grados
                round(np.degrees(tcp_pose[4]), 2),  # RY en grados
                round(np.degrees(tcp_pose[5]), 2),  # RZ en grados
            ]
        except Exception as e:
            logger.error(f"Error obteniendo pose formateada: {e}")
            return [300.0, -200.0, 500.0, 0.0, 0.0, 0.0]

    def is_point_within_reach(self, x, y, z):
        """Verificar si el punto está dentro del workspace"""
        # Convertir de mm a metros si es necesario
        if abs(x) > 10:  # Probablemente está en mm
            x, y, z = x/1000, y/1000, z/1000
        
        point = np.array([x, y, z])
        distance = np.linalg.norm(point)
        return self.UR5E_MIN_REACH <= distance <= self.UR5E_MAX_REACH

    def move_to_coordinates(self, x, y, z, rx, ry, rz):
        """
        Mover robot a coordenadas especificadas
        Acepta coordenadas en mm y grados para facilitar interfaz web
        """
        try:
            with self.lock:
                if self.emergency_stop_active:
                    logger.warning("No se puede mover: parada de emergencia activa")
                    return False
                
                if self.movement_active:
                    logger.warning("Movimiento ya en progreso")
                    return False
                
                # Convertir de mm a metros y grados a radianes
                x_m = x / 1000.0 if abs(x) > 10 else x
                y_m = y / 1000.0 if abs(y) > 10 else y
                z_m = z / 1000.0 if abs(z) > 10 else z
                
                rx_rad = np.radians(rx) if abs(rx) > 0.1 else rx
                ry_rad = np.radians(ry) if abs(ry) > 0.1 else ry
                rz_rad = np.radians(rz) if abs(rz) > 0.1 else rz
                
                # Validar workspace
                if not self.is_point_within_reach(x_m, y_m, z_m):
                    distance = np.linalg.norm(np.array([x_m, y_m, z_m]))
                    logger.warning(f"Punto fuera del alcance: {distance:.3f}m")
                    return False
                
                target_pose = [x_m, y_m, z_m, rx_rad, ry_rad, rz_rad]
                
                if self.can_control():
                    # Enviar comando real al robot
                    self.movement_active = True
                    logger.info(f"🤖 Moviendo robot a: {target_pose}")
                    
                    # Usar velocidad actual
                    velocity = self.linear_speed
                    acceleration = self.linear_accel
                    
                    # Ejecutar movimiento
                    success = self.control.moveL(target_pose, velocity, acceleration)
                    self.movement_active = False
                    
                    if success:
                        logger.info("✅ Movimiento completado exitosamente")
                        return True
                    else:
                        logger.error("❌ Fallo en el movimiento")
                        return False
                elif self.is_connected():
                    # Robot conectado pero sin control
                    logger.warning("📖 Robot conectado en modo solo lectura - comando no enviado")
                    logger.info(f"📝 Comando registrado: mover a {target_pose}")
                    return True
                else:
                    # MODO DESCONECTADO - Solo loggar el comando 
                    logger.info(f"📝 Comando registrado: mover a {target_pose}")
                    logger.info("⚠️ Robot no conectado - comando no enviado")
                    time.sleep(1)  # Simular tiempo de procesamiento
                    return True
                
        except Exception as e:
            logger.error(f"❌ Error en movimiento: {e}")
            self.movement_active = False
            return False

    def go_home(self):
        """Mover robot a posición home"""
        try:
            with self.lock:
                if self.emergency_stop_active:
                    logger.warning("No se puede ir a home: parada de emergencia activa")
                    return False
                
                if self.can_control():
                    # Enviar comando real al robot
                    self.movement_active = True
                    logger.info("🏠 Moviendo robot a posición home")
                    
                    # Usar velocidades para articulaciones
                    velocity = self.joint_speed
                    acceleration = self.joint_accel
                    
                    # Mover a posición home en articulaciones
                    success = self.control.moveJ(self.home_joint_angles_rad, velocity, acceleration)
                    self.movement_active = False
                    
                    if success:
                        logger.info("✅ Robot en posición home")
                        return True
                    else:
                        logger.error("❌ Fallo moviendo a home")
                        return False
                elif self.is_connected():
                    # Robot conectado pero sin control
                    logger.warning("📖 Robot conectado en modo solo lectura - comando no enviado")
                    logger.info("📝 Comando registrado: ir a posición home")
                    return True
                else:
                    # MODO DESCONECTADO - Solo loggar el comando
                    logger.info("📝 Comando registrado: ir a posición home")
                    logger.info("⚠️ Robot no conectado - comando no enviado")
                    time.sleep(2)
                    return True
                
        except Exception as e:
            logger.error(f"❌ Error yendo a home: {e}")
            self.movement_active = False
            return False

    def emergency_stop(self):
        """Activar parada de emergencia"""
        try:
            with self.lock:
                self.movement_active = False
                self.emergency_stop_active = True
                
                if self.can_control():
                    # Ejecutar parada de emergencia real en el robot
                    logger.warning("🚨 EJECUTANDO PARADA DE EMERGENCIA EN ROBOT")
                    self.control.stopScript()  # Detener script actual
                elif self.is_connected():
                    logger.warning("🚨 PARADA DE EMERGENCIA REGISTRADA (modo solo lectura)")
                else:
                    logger.warning("🚨 PARADA DE EMERGENCIA REGISTRADA (robot no conectado)")
                
                return True
                
        except Exception as e:
            logger.error(f"Error ejecutando parada de emergencia: {e}")
            return False

    def deactivate_emergency_stop(self):
        """Desactivar parada de emergencia"""
        with self.lock:
            self.emergency_stop_active = False
            logger.info("✅ Parada de emergencia DESACTIVADA")

    def wait_for_movement_completion_joint(self, target_joints, timeout=5.0):
        """Esperar a que termine el movimiento articular"""
        if not self.is_connected():
            return not self.emergency_stop_active
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.emergency_stop_active:
                return False
            
            current_joints = self.receive.getActualQ()
            if np.allclose(current_joints, target_joints, atol=self.position_tolerance_joint):
                return True
            
            time.sleep(0.1)
        
        logger.warning("Timeout esperando completar movimiento articular")
        return False

    def wait_for_movement_completion_tcp(self, target_pose, timeout=5.0):
        """Esperar a que termine el movimiento lineal"""  
        if not self.is_connected():
            return not self.emergency_stop_active
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.emergency_stop_active:
                return False
            
            current_pose = self.receive.getActualTCPPose()
            if np.allclose(current_pose, target_pose, atol=self.position_tolerance_tcp):
                return True
            
            time.sleep(0.1)
        
        logger.warning("Timeout esperando completar movimiento lineal")
        return False

    def get_robot_status(self):
        """Obtener estado completo del robot"""
        with self.lock:
            is_connected = self.is_connected()
            
            status = {
                'connected': is_connected,
                'can_control': self.can_control() if is_connected else False,
                'movement_active': self.movement_active,
                'emergency_stop_active': self.emergency_stop_active,
                'current_position': self.get_current_pose(),
                'speed_level': self.current_speed_level + 1,
                'speed_percentage': int(self.speed_levels[self.current_speed_level] * 100),
                'mode': 'CONECTADO' if is_connected else 'DESCONECTADO',
                'robot_ip': self.robot_ip
            }
            
            # Agregar información adicional si está conectado
            if is_connected:
                try:
                    status.update({
                        'robot_mode': self.receive.getRobotMode(),
                        'safety_mode': self.receive.getSafetyMode(),
                        'joint_temperatures': self.receive.getJointTemperatures(),
                        'runtime_state': self.receive.getRuntimeState()
                    })
                except Exception as e:
                    logger.warning(f"Error obteniendo estado extendido: {e}")
        
        # Incluir posiciones articulares
        joints = self.get_current_joint_positions()
        status['joint_positions'] = [np.degrees(j) for j in joints]
        
        # Incluir información del control Xbox
        status.update(self.get_xbox_status())
        
        return status

    def set_speed_level(self, level):
        """Cambiar nivel de velocidad (0-4)"""
        if 0 <= level < len(self.speed_levels):
            with self.lock:
                self.current_speed_level = level
            logger.info(f"Velocidad cambiada a nivel {level+1} ({self.speed_levels[level]*100:.0f}%)")
            return True
        return False

    def disconnect(self):
        """Desconectar del robot - MODO DESCONECTADO"""
        try:
            with self.lock:
                if self.movement_active:
                    self.emergency_stop()
                
                # Deshabilitar control Xbox si está activo
                if self.xbox_enabled:
                    self.disable_xbox_control()
                
                self.connected = False
                
                # En modo desconectado, no hay conexiones que cerrar
                self.control = None
                self.receive = None
                self.io = None
            
            logger.info("📝 Controlador UR5 cerrado (modo desconectado)")
            
        except Exception as e:
            logger.error(f"Error cerrando controlador: {e}")

    def move_joints(self, target_joints, speed=1.0, acceleration=1.5, asynchronous=False):
        """Mover articulaciones específicas para compatibilidad con Xbox controller"""
        if not self.can_control():
            logger.warning("⚠️ Robot no puede ser controlado")
            return False
        
        try:
            with self.lock:
                if self.movement_active and not asynchronous:
                    logger.warning("⚠️ Movimiento ya en progreso")
                    return False
                
                self.movement_active = True
            
            logger.info(f"🦾 Moviendo articulaciones a: {[np.degrees(j) for j in target_joints]}")
            
            success = self.control.moveJ(target_joints, speed, acceleration, asynchronous=asynchronous)
            
            if not asynchronous:
                # Esperar a que termine el movimiento
                self.wait_for_movement_completion_joint(target_joints, timeout=5.0)
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error moviendo articulaciones: {e}")
            return False
        finally:
            if not asynchronous:
                with self.lock:
                    self.movement_active = False

    def move_linear(self, target_pose, speed=0.1, acceleration=0.3, asynchronous=False):
        """Mover TCP linealmente para compatibilidad con Xbox controller"""
        if not self.can_control():
            logger.warning("⚠️ Robot no puede ser controlado")
            return False
        
        try:
            with self.lock:
                if self.movement_active and not asynchronous:
                    logger.warning("⚠️ Movimiento ya en progreso")
                    return False
                
                self.movement_active = True
            
            logger.info(f"🎯 Moviendo TCP a: {target_pose}")
            
            success = self.control.moveL(target_pose, speed, acceleration, asynchronous=asynchronous)
            
            if not asynchronous:
                # Esperar a que termine el movimiento
                self.wait_for_movement_completion_tcp(target_pose, timeout=5.0)
            
            return success
            
            return False
        finally:
            if not asynchronous:
                with self.lock:
                    self.movement_active = False

    # ========== FUNCIONES PARA CONTROL XBOX - SIEMPRE HABILITADO ==========
    
    def initialize_xbox_controller(self):
        """Inicializar el control Xbox - SIEMPRE HABILITADO"""
        if not PYGAME_AVAILABLE:
            logger.warning("❌ pygame no disponible - Control Xbox deshabilitado")
            self.xbox_enabled = False
            return False
        
        try:
            pygame.init()
            pygame.joystick.init()
            
            # Verificar controles conectados
            if pygame.joystick.get_count() == 0:
                logger.warning("⚠️ No se detectaron controles Xbox conectados")
                self.xbox_enabled = False
                return False
            
            # Conectar al primer control
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            logger.info(f"🎮 Control conectado: {self.joystick.get_name()}")
            
            # Inicializar estados de botones
            self.previous_button_states = {}
            for i in range(self.joystick.get_numbuttons()):
                self.previous_button_states[i] = False
            
            # Iniciar hilo de control Xbox automáticamente
            self.xbox_enabled = True
            self.xbox_running = True
            self.xbox_thread = threading.Thread(target=self._xbox_control_loop, daemon=True)
            self.xbox_thread.start()
            
            logger.info("🎮 Control Xbox HABILITADO automáticamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inicializando control Xbox: {e}")
            self.xbox_enabled = False
            return False

    def disable_xbox_control(self):
        """Deshabilitar control Xbox temporalmente"""
        with self.lock:
            if not self.xbox_running:
                return True
            
            self.xbox_running = False
            if self.xbox_thread:
                self.xbox_thread.join(timeout=2)
            logger.info("🎮 Control Xbox deshabilitado temporalmente")
            return True

    def is_xbox_enabled(self):
        """Verificar si el control Xbox está habilitado"""
        return self.xbox_enabled and self.xbox_running

    def _xbox_control_loop(self):
        """Bucle principal del control Xbox - IMPLEMENTACIÓN DE move_controler.py"""
        logger.info("🎮 Iniciando bucle de control Xbox...")
        
        try:
            clock = pygame.time.Clock()
            
            while self.xbox_running and self.xbox_enabled:
                if not self.joystick:
                    break
                
                try:
                    # Procesar entrada del control
                    self._process_xbox_input()
                    
                    # Debug completo cada 2 segundos si hay actividad
                    current_time = time.time()
                    if self.debug_mode and current_time - self.last_debug_time > 2.0:
                        # Solo hacer debug si hay algún input activo
                        has_input = self._has_active_input()
                        
                        if has_input:
                            self._debug_all_inputs()
                            self.last_debug_time = current_time
                    
                    clock.tick(100)  # 100 FPS para mejor respuesta
                    
                except Exception as e:
                    logger.error(f"Error en bucle Xbox: {e}")
                    time.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Error crítico en bucle Xbox: {e}")
        finally:
            logger.info("🎮 Bucle de control Xbox terminado")

    def _has_active_input(self):
        """Verificar si hay entrada activa del usuario"""
        if not self.joystick:
            return False
            
        # Verificar botones
        for i in range(self.joystick.get_numbuttons()):
            if self.joystick.get_button(i):
                return True
        
        # Verificar ejes analógicos
        for i in range(self.joystick.get_numaxes()):
            if abs(self.joystick.get_axis(i)) > 0.1:
                return True
        
        # Verificar D-pad
        for i in range(self.joystick.get_numhats()):
            if self.joystick.get_hat(i) != (0, 0):
                return True
        
        return False

    def _process_xbox_input(self):
        """Procesar entrada del control Xbox CON MAPEO CORREGIDO"""
        pygame.event.pump()
        
        # Procesar botones
        self._process_xbox_buttons()
        
        # Procesar entrada analógica si no hay movimiento activo
        if not self.movement_active and not self.emergency_stop_active:
            self._process_xbox_analog()

    def _process_xbox_buttons(self):
        """Procesar botones del control Xbox"""
        # MAPEO CORREGIDO según move_controler.py
        button_mapping = {
            0: "A",          # Cambiar modo de control
            1: "B",          # Parada de emergencia  
            3: "X",          # Ir a home
            4: "Y",          # Deactivar emergencia
            6: "LB",         # Velocidad -
            7: "RB",         # Velocidad +
            10: "Menu",      # Toggle debug
            11: "Start",     # Show status
        }
        
        for button_id in range(self.joystick.get_numbuttons()):
            current_state = self.joystick.get_button(button_id)
            previous_state = self.previous_button_states.get(button_id, False)
            
            # Detectar presión de botón (flanco ascendente)
            if current_state and not previous_state:
                self._handle_xbox_button_press(button_id)
            
            self.previous_button_states[button_id] = current_state

    def _handle_xbox_button_press(self, button_id):
        """Manejar presión de botones específicos del Xbox - MAPEO CORREGIDO"""
        button_actions = {
            0: "A",          # Cambiar modo
            1: "B",          # Emergencia
            3: "X",          # Home
            4: "Y",          # Desactivar emergencia
            6: "LB",         # Velocidad -
            7: "RB",         # Velocidad +
            10: "Menu",      # Debug
            11: "Start",     # Status
        }
        
        button_name = button_actions.get(button_id, f"Btn{button_id}")
        logger.info(f"🎮 Procesando botón: {button_name} (ID: {button_id})")
        
        if button_id == 0:  # A - Cambiar modo
            self.control_mode = "linear" if self.control_mode == "joint" else "joint"
            logger.info(f"🔄 Modo cambiado a: {self.control_mode.upper()}")
        
        elif button_id == 1:  # B - Parada de emergencia
            self.activate_emergency_stop()
        
        elif button_id == 3:  # X - Ir a home
            logger.info("🏠 Moviendo a posición home...")
            if not self.emergency_stop_active and not self.movement_active:
                threading.Thread(target=self.go_home, daemon=True).start()
        
        elif button_id == 4:  # Y - Desactivar emergencia
            self.deactivate_emergency_stop()
        
        elif button_id == 6:  # LB - Reducir velocidad
            if self.current_speed_level > 0:
                self.current_speed_level -= 1
                speed_percent = self.speed_levels[self.current_speed_level] * 100
                logger.info(f"🔽 Velocidad reducida a {speed_percent:.0f}%")
        
        elif button_id == 7:  # RB - Aumentar velocidad
            if self.current_speed_level < len(self.speed_levels) - 1:
                self.current_speed_level += 1
                speed_percent = self.speed_levels[self.current_speed_level] * 100
                logger.info(f"🔼 Velocidad aumentada a {speed_percent:.0f}%")
        
        elif button_id == 11:  # Start - Mostrar estado
            self._show_xbox_status()
        
        elif button_id == 10:  # Menu - Toggle debug
            self.debug_mode = not self.debug_mode
            logger.info(f"🐛 Debug: {'ON' if self.debug_mode else 'OFF'}")

    def activate_emergency_stop(self):
        """Activate emergency stop"""
        try:
            if self.control and RTDE_AVAILABLE:
                self.control.stopJ(2.0)  # Parada suave en articulaciones
                self.control.stopL(2.0)  # Parada suave lineal
            self.emergency_stop_active = True
            self.emergency_stop_time = time.time()
            self.movement_active = False
            logger.warning("🚨 PARADA DE EMERGENCIA ACTIVADA")
        except Exception as e:
            logger.error(f"Error en parada de emergencia: {e}")

    def _process_xbox_analog(self):
        """Procesar entrada analógica del Xbox con filtros avanzados para suavizar"""
        # Obtener valores de joysticks
        left_x = self.joystick.get_axis(0)
        left_y = self.joystick.get_axis(1)
        right_x = self.joystick.get_axis(2)
        right_y = self.joystick.get_axis(3)
        
        # Obtener triggers CON MAPEO CORREGIDO
        raw_lt = (self.joystick.get_axis(4) + 1) / 2 if self.joystick.get_numaxes() > 4 else 0
        raw_rt = (self.joystick.get_axis(5) + 1) / 2 if self.joystick.get_numaxes() > 5 else 0
        
        # Intercambiar porque están mapeados al revés
        left_trigger = raw_rt
        right_trigger = raw_lt
        
        # Obtener D-pad
        dpad = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
        
        # === FILTRADO EXPONENCIAL MEJORADO ===
        # Alpha más bajo para mayor suavizado
        left_x = self._apply_input_filter('left_x', left_x)
        left_y = self._apply_input_filter('left_y', left_y)
        right_x = self._apply_input_filter('right_x', right_x)
        right_y = self._apply_input_filter('right_y', right_y)
        left_trigger = self._apply_input_filter('left_trigger', left_trigger)
        right_trigger = self._apply_input_filter('right_trigger', right_trigger)
        
        # === DEADZONE MEJORADA CON RAMPA SUAVE ===
        def apply_smooth_deadzone(value, zone=0.4):  # AUMENTADO de 0.3 a 0.4 - deadzone más amplia
            """Aplicar deadzone con rampa suave en lugar de corte abrupto"""
            abs_value = abs(value)
            if abs_value < zone:
                return 0.0
            # Rampa suave: transición gradual desde deadzone hasta valor máximo
            mapped = (abs_value - zone) / (1.0 - zone)
            # Curva cúbica para control aún más fino en valores bajos
            mapped = mapped ** 2.0  # AUMENTADO de 1.5 a 2.0 para respuesta más lenta
            return mapped * np.sign(value)
        
        left_x = apply_smooth_deadzone(left_x)
        left_y = apply_smooth_deadzone(left_y)
        right_x = apply_smooth_deadzone(right_x)
        right_y = apply_smooth_deadzone(right_y)
        
        # Triggers con umbral más alto
        left_trigger = left_trigger if left_trigger > 0.2 else 0
        right_trigger = right_trigger if right_trigger > 0.2 else 0
        
        # === ACUMULACIÓN TEMPORAL ===
        # Acumular pequeños movimientos antes de ejecutar
        self._accumulate_movement(left_x, left_y, right_x, right_y, left_trigger, right_trigger, dpad)
        
        # Solo ejecutar si hay movimiento acumulado significativo
        self._execute_accumulated_movement()

    def _accumulate_movement(self, left_x, left_y, right_x, right_y, left_trigger, right_trigger, dpad):
        """Acumular movimientos pequeños antes de ejecutar"""
        current_time = time.time()
        
        # Verificar cooldown más estricto
        if current_time - self.last_movement_time < self.movement_cooldown:
            return
        
        if self.control_mode == "joint":
            # Control articular - usar incrementos ULTRA PEQUEÑOS
            increment = self.joint_increment * 0.2  # REDUCIDO de 0.4 a 0.2 para incrementos mínimos
            
            if abs(left_x) > 0.02:  # AUMENTADO el threshold mínimo de 0.01 a 0.02
                self.accumulated_movement[0] += left_x * increment
            if abs(left_y) > 0.02:  # Shoulder  
                self.accumulated_movement[1] += left_y * increment
            if abs(right_x) > 0.02:  # Elbow
                self.accumulated_movement[2] += right_x * increment
            if abs(right_y) > 0.02:  # Wrist 1
                self.accumulated_movement[3] += right_y * increment
            
            # D-pad para articulaciones 4 y 5 (aún más lento)
            dpad_increment = increment * 0.2  # REDUCIDO de 0.3 a 0.2
            if dpad[0] != 0:  # Wrist 2
                self.accumulated_movement[4] += dpad[0] * dpad_increment
            if dpad[1] != 0:  # Wrist 3
                self.accumulated_movement[5] += dpad[1] * dpad_increment
                
        else:  # TCP mode
            # Control lineal - usar incrementos ULTRA PEQUEÑOS
            linear_inc = self.linear_increment * 0.3  # REDUCIDO de 0.5 a 0.3 para incrementos mínimos
            
            if abs(left_x) > 0.02:  # X - AUMENTADO el threshold mínimo
                self.accumulated_movement[0] += left_x * linear_inc
            if abs(left_y) > 0.02:  # Y
                self.accumulated_movement[1] += left_y * linear_inc
            if abs(right_y) > 0.02:  # Z
                self.accumulated_movement[2] += right_y * linear_inc
            if abs(right_x) > 0.02:  # RZ
                self.accumulated_movement[5] += right_x * 0.01  # REDUCIDO de 0.02 a 0.01
        
        # Procesar triggers para velocidad
        self._handle_speed_triggers(left_trigger, right_trigger)

    def _execute_accumulated_movement(self):
        """Ejecutar movimiento acumulado si supera threshold"""
        movements_to_execute = []
        
        if self.control_mode == "joint":
            # Threshold AUMENTADO para evitar micro-movimientos
            threshold = self.movement_threshold * 1.5  # AUMENTADO de 0.8 a 1.5
            
            for i in range(6):
                if abs(self.accumulated_movement[i]) >= threshold:
                    movements_to_execute.append((i, self.accumulated_movement[i]))
                    self.accumulated_movement[i] = 0.0  # Reset
                    
        else:  # TCP mode
            # Thresholds AUMENTADOS para posición y rotación
            for i in range(6):
                if i < 3:  # Posición X, Y, Z
                    threshold = 0.008  # AUMENTADO de 0.004 a 0.008
                else:  # Rotación RX, RY, RZ
                    threshold = 0.03  # AUMENTADO de 0.015 a 0.03
                
                if abs(self.accumulated_movement[i]) >= threshold:
                    movements_to_execute.append((i, self.accumulated_movement[i]))
                    self.accumulated_movement[i] = 0.0
        
        # Ejecutar movimientos acumulados
        if movements_to_execute:
            if self.control_mode == "joint":
                self.execute_simultaneous_joint_movements(movements_to_execute)
            else:
                self.execute_simultaneous_tcp_movements(movements_to_execute)

    def _apply_input_filter(self, input_name, new_value, alpha=None):
        """Aplicar filtro exponencial mejorado para suavizar entrada"""
        if alpha is None:
            alpha = self.filter_alpha
            
        if input_name not in self.input_filter:
            self.input_filter[input_name] = new_value
            return new_value
        
        # Filtro exponencial con detección de cambios grandes
        previous_value = self.input_filter[input_name]
        
        # Si hay un cambio grande (como soltar el joystick), usar alpha más alto
        # para respuesta más rápida
        change_magnitude = abs(new_value - previous_value)
        dynamic_alpha = min(alpha * 2, 0.8) if change_magnitude > 0.5 else alpha
        
        filtered_value = (dynamic_alpha * new_value + 
                         (1 - dynamic_alpha) * previous_value)
        
        self.input_filter[input_name] = filtered_value
        return filtered_value

    def _handle_speed_triggers(self, left_trigger, right_trigger):
        """Manejar cambios de velocidad con triggers"""
        current_time = time.time()
        
        # Evitar cambios muy frecuentes de velocidad
        if current_time - self.last_speed_change < 0.3:  # 300ms mínimo entre cambios
            return
        
        if left_trigger > 0.2:
            new_speed = max(0, self.current_speed_level - 1)
            if new_speed != self.current_speed_level:
                self.current_speed_level = new_speed
                self.last_speed_change = current_time
                logger.info(f"🔽 Velocidad: {self.current_speed_level * 20 + 10}%")
                    
        elif right_trigger > 0.2:
            new_speed = min(len(self.speed_levels) - 1, self.current_speed_level + 1)
            if new_speed != self.current_speed_level:
                self.current_speed_level = new_speed
                self.last_speed_change = current_time
                logger.info(f"🔼 Velocidad: {self.current_speed_level * 20 + 10}%")

    def _apply_input_filter(self, input_name, new_value):
        """Aplicar filtro exponencial para suavizar entrada"""
        if input_name not in self.input_filter:
            self.input_filter[input_name] = new_value
            return new_value
        
        # Filtro exponencial: output = alpha * input + (1-alpha) * previous_output
        filtered_value = (self.filter_alpha * new_value + 
                         (1 - self.filter_alpha) * self.input_filter[input_name])
        
        self.input_filter[input_name] = filtered_value
        return filtered_value

    def _get_accumulated_tcp_movements(self):
        """Obtener movimientos TCP acumulados que superen el umbral"""
        movements = []
        tcp_mapping = {'tcp_x': 0, 'tcp_y': 1, 'tcp_z': 2, 'tcp_rx': 3, 'tcp_ry': 4, 'tcp_rz': 5}
        
        for tcp_name, accumulated in list(self.movement_accumulator.items()):
            if tcp_name.startswith('tcp_') and abs(accumulated) >= self.accumulator_threshold * 0.5:  # Umbral más bajo para TCP
                axis_idx = tcp_mapping[tcp_name]
                movements.append((axis_idx, accumulated))
                # Resetear acumulador
                self.movement_accumulator[tcp_name] = 0
        
        return movements

    def execute_simultaneous_joint_movements(self, movements):
        """Ejecutar múltiples movimientos articulares simultáneamente - SUAVIZADO"""
        if self.emergency_stop_active or self.movement_active:
            return
        
        # Control de cooldown más estricto
        current_time = time.time()
        if current_time - self.last_movement_time < self.movement_cooldown:
            return
        
        try:
            if not self.can_control():
                return
            
            # Usar asíncrono para evitar bloqueos
            current_joints = self.get_current_joint_positions()
            target_joints = current_joints.copy()
            
            # Aplicar todos los movimientos
            speed_factor = self.speed_levels[self.current_speed_level]
            
            for joint_idx, increment in movements:
                if 0 <= joint_idx < 6:
                    target_joints[joint_idx] += increment * speed_factor
            
            # Verificar límites de articulaciones
            joint_limits = {
                0: (-6.28, 6.28),    # Base: ±360°
                1: (-6.28, 6.28),    # Shoulder: ±360° 
                2: (-3.14, 3.14),    # Elbow: ±180°
                3: (-6.28, 6.28),    # Wrist 1: ±360°
                4: (-6.28, 6.28),    # Wrist 2: ±360°
                5: (-6.28, 6.28)     # Wrist 3: ±360°
            }
            
            for i, angle in enumerate(target_joints):
                min_limit, max_limit = joint_limits[i]
                target_joints[i] = np.clip(angle, min_limit, max_limit)
            
            # Parámetros de movimiento ULTRA suaves
            move_speed = self.joint_speed * speed_factor * 0.3  # REDUCIDO de 0.6 a 0.3 para máxima suavidad
            move_accel = self.joint_accel * speed_factor * 0.2  # REDUCIDO de 0.4 a 0.2 para máxima suavidad
            
            # Usar blend radius aumentado para movimientos más suaves
            blend_radius = self.joint_blend_radius * 1.5  # REDUCIDO de 2 a 1.5 para evitar sobresuavizado
            
            # NUEVO: Usar moveJ con blend radius para suavidad
            try:
                self.control.moveJ(
                    target_joints,
                    speed=move_speed,
                    acceleration=move_accel,
                    asynchronous=True,  # Asíncrono para no bloquear
                    blend=blend_radius
                )
                
                if self.debug_mode and len(movements) > 1:
                    joint_names = [f"J{i}" for i, _ in movements]
                    logger.debug(f"🔄 Movimiento suave joints: {', '.join(joint_names)}")
                
            except TypeError:
                # Fallback si blend no está soportado
                self.control.moveJ(
                    target_joints,
                    speed=move_speed,
                    acceleration=move_accel,
                    asynchronous=True
                )
            
            self.last_movement_time = current_time
            
        except Exception as e:
            logger.error(f"Error en movimiento articular suave: {e}")

    def execute_simultaneous_tcp_movements(self, movements):
        """Ejecutar múltiples movimientos TCP simultáneamente - SUAVIZADO"""
        if self.emergency_stop_active or self.movement_active:
            return
        
        # Control de cooldown más estricto
        current_time = time.time()
        if current_time - self.last_movement_time < self.movement_cooldown:
            return
        
        try:
            if not self.can_control():
                return
            
            current_pose = self.get_current_tcp_pose()
            target_pose = current_pose.copy()
            
            # Aplicar todos los movimientos
            speed_factor = self.speed_levels[self.current_speed_level]
            
            for axis_idx, increment in movements:
                if 0 <= axis_idx < 6:
                    target_pose[axis_idx] += increment * speed_factor
            
            # Verificar límites del workspace para posición
            x, y, z = target_pose[:3]
            if not self.is_point_within_reach(x, y, z):
                if self.debug_mode:
                    logger.warning(f"🚫 Posición fuera del workspace: X={x:.3f}, Y={y:.3f}, Z={z:.3f}")
                return
            
            # Parámetros de movimiento ULTRA suaves
            move_speed = self.linear_speed * speed_factor * 0.25  # REDUCIDO de 0.5 a 0.25 para máxima suavidad
            move_accel = self.linear_accel * speed_factor * 0.15  # REDUCIDO de 0.3 a 0.15 para máxima suavidad
            
            # Usar blend radius aumentado
            blend_radius = self.linear_blend_radius * 2  # Mantener triplicado para TCP
            
            # NUEVO: Usar moveL con blend radius para suavidad
            try:
                self.control.moveL(
                    target_pose,
                    speed=move_speed,
                    acceleration=move_accel,
                    asynchronous=True,
                    blend=blend_radius
                )
                
                if self.debug_mode and len(movements) > 1:
                    axis_names = ['X', 'Y', 'Z', 'RX', 'RY', 'RZ']
                    moved_axes = [axis_names[i] for i, _ in movements]
                    logger.debug(f"🔄 Movimiento suave TCP: {', '.join(moved_axes)}")
                
            except TypeError:
                # Fallback si blend no está soportado
                self.control.moveL(
                    target_pose,
                    speed=move_speed,
                    acceleration=move_accel,
                    asynchronous=True
                )
            
            self.last_movement_time = current_time
            
        except Exception as e:
            logger.error(f"Error en movimiento TCP suave: {e}")

    def _show_xbox_status(self):
        """Mostrar estado del control Xbox"""
        logger.info("🎮 === ESTADO CONTROL XBOX ===")
        logger.info(f"🔄 Modo: {self.control_mode.upper()}")
        logger.info(f"⚡ Velocidad: {self.speed_levels[self.current_speed_level]*100:.0f}%")
        logger.info(f"🚨 Emergencia: {'ACTIVA' if self.emergency_stop_active else 'INACTIVA'}")
        logger.info(f"🔗 Robot conectado: {'SÍ' if self.is_connected() else 'NO'}")
        logger.info(f"🎮 Xbox habilitado: {'SÍ' if self.xbox_enabled else 'NO'}")

    def _debug_all_inputs(self):
        """Debug completo de todas las entradas"""
        if not self.joystick:
            return
            
        logger.debug("🐛 === DEBUG COMPLETO ===")
        
        # Botones
        pressed_buttons = []
        for i in range(self.joystick.get_numbuttons()):
            if self.joystick.get_button(i):
                pressed_buttons.append(f"Btn{i}")
        
        if pressed_buttons:
            logger.debug(f"🔘 Botones: {', '.join(pressed_buttons)}")
        
        # Ejes analógicos
        axes_info = []
        for i in range(self.joystick.get_numaxes()):
            value = self.joystick.get_axis(i)
            if abs(value) > 0.1:
                axes_info.append(f"Axis{i}: {value:.3f}")
        
        if axes_info:
            logger.debug(f"📊 Ejes: {', '.join(axes_info)}")
        
        # D-pad
        for i in range(self.joystick.get_numhats()):
            hat = self.joystick.get_hat(i)
            if hat != (0, 0):
                logger.debug(f"🎯 D-pad {i}: {hat}")

    def get_xbox_status(self):
        """Obtener estado del control Xbox para la interfaz web"""
        return {
            'xbox_enabled': self.xbox_enabled,
            'xbox_connected': self.joystick is not None if self.xbox_enabled else False,
            'xbox_running': self.xbox_running,
            'control_mode': self.control_mode if self.xbox_enabled else None,
            'debug_mode': self.debug_mode if self.xbox_enabled else False,
            'speed_level': self.current_speed_level,
            'speed_percent': self.speed_levels[self.current_speed_level] * 100 if self.current_speed_level < len(self.speed_levels) else 0
        }