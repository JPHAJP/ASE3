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
logger = logging.getLogger(__name__)

class UR5WebController:
    def __init__(self, robot_ip="192.168.0.101"):
        """Inicializar controlador UR5 para aplicación web"""
        self.robot_ip = robot_ip
        self.control = None
        self.receive = None
        self.io = None
        
        # Parámetros de movimiento
        self.joint_speed = 2.0
        self.joint_accel = 3.0
        self.linear_speed = 0.5
        self.linear_accel = 1.5
        
        # Configuración de velocidades
        self.speed_levels = [0.1, 0.3, 0.5, 0.8, 1.0]
        self.current_speed_level = 1
        
        # Estados
        self.connected = False
        self.movement_active = False
        self.emergency_stop_active = False
        
        # Posición home
        self.home_joint_angles_deg = [-58.49, -78.0, -98.4, -94.67, 88.77, -109.86]
        self.home_joint_angles_rad = np.radians(self.home_joint_angles_deg)
        
        # Tolerancias
        self.position_tolerance_joint = 0.005
        self.position_tolerance_tcp = 0.001
        
        # Límites del workspace
        self.UR5E_MAX_REACH = 0.85
        self.UR5E_MIN_REACH = 0.18
        
        # Lock para acceso thread-safe
        self.lock = threading.Lock()
        
        # Intentar conectar
        if RTDE_AVAILABLE:
            self.initialize_robot()
        
        logger.info(f"UR5WebController inicializado - IP: {robot_ip}")

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
                
                self.connected = False
                
                # En modo desconectado, no hay conexiones que cerrar
                self.control = None
                self.receive = None
                self.io = None
            
            logger.info("📝 Controlador UR5 cerrado (modo desconectado)")
            
        except Exception as e:
            logger.error(f"Error cerrando controlador: {e}")