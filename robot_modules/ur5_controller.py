"""
Controlador UR5 adaptado para la aplicación web
Basado en move_controler.py pero adaptado para funcionar como módulo web
"""

import numpy as np
import time
import threading
import logging
from datetime import datetime

try:
    import rtde_control
    import rtde_receive
    import rtde_io
    RTDE_AVAILABLE = True
except ImportError:
    RTDE_AVAILABLE = False
    logging.warning("RTDE no disponible - funcionando en modo simulación")

logger = logging.getLogger(__name__)

class UR5WebController:
    def __init__(self, robot_ip="192.168.1.1"):
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
        self.home_joint_angles_deg = [-51.9, -71.85, -112.7, -85.96, 90, 38]
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
        """Inicializar conexión con el robot UR5e"""
        try:
            if not RTDE_AVAILABLE:
                logger.warning("RTDE no disponible - simulando conexión")
                return False
            
            self.control = rtde_control.RTDEControlInterface(self.robot_ip)
            self.receive = rtde_receive.RTDEReceiveInterface(self.robot_ip)
            self.io = rtde_io.RTDEIOInterface(self.robot_ip)
            
            self.connected = True
            logger.info(f"✅ Conexión establecida con UR5e en {self.robot_ip}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error conectando al robot: {e}")
            self.connected = False
            return False

    def is_connected(self):
        """Verificar si el robot está conectado"""
        return self.connected and RTDE_AVAILABLE

    def get_current_joint_positions(self):
        """Obtener posiciones actuales de las articulaciones"""
        if not self.is_connected():
            # Retornar posición simulada
            return self.home_joint_angles_rad
        
        try:
            return self.receive.getActualQ()
        except Exception as e:
            logger.error(f"Error obteniendo posiciones articulares: {e}")
            return self.home_joint_angles_rad

    def get_current_tcp_pose(self):
        """Obtener pose actual del TCP"""
        if not self.is_connected():
            # Retornar pose simulada
            return [0.3, -0.2, 0.5, 0, 0, 0]
        
        try:
            return self.receive.getActualTCPPose()
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
                
                if not self.is_connected():
                    logger.info(f"Simulando movimiento a {target_pose}")
                    time.sleep(2)  # Simular tiempo de movimiento
                    return True
                
                # Ejecutar movimiento real
                self.movement_active = True
                
                speed = float(self.linear_speed * self.speed_levels[self.current_speed_level])
                accel = float(self.linear_accel * self.speed_levels[self.current_speed_level])
                
                logger.info(f"Moviendo a: {target_pose}")
                self.control.moveL(target_pose, speed, accel, False)
                
                # Esperar finalización
                success = self.wait_for_movement_completion_tcp(target_pose, timeout=10.0)
                
                self.movement_active = False
                
                if success:
                    logger.info("✅ Movimiento completado exitosamente")
                else:
                    logger.warning("⚠️ Timeout en movimiento")
                
                return success
                
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
                
                if not self.is_connected():
                    logger.info("Simulando movimiento a home")
                    time.sleep(3)
                    return True
                
                logger.info("Moviendo robot a posición home...")
                self.movement_active = True
                
                speed = float(self.joint_speed * self.speed_levels[self.current_speed_level])
                accel = float(self.joint_accel * self.speed_levels[self.current_speed_level])
                
                self.control.moveJ(self.home_joint_angles_rad, speed, accel, False)
                
                success = self.wait_for_movement_completion_joint(
                    self.home_joint_angles_rad, timeout=15.0
                )
                
                self.movement_active = False
                
                if success:
                    logger.info("✅ Robot en posición home")
                else:
                    logger.warning("⚠️ Timeout moviendo a home")
                
                return success
                
        except Exception as e:
            logger.error(f"❌ Error yendo a home: {e}")
            self.movement_active = False
            return False

    def emergency_stop(self):
        """Activar parada de emergencia"""
        try:
            with self.lock:
                if self.is_connected():
                    self.control.stopJ(2.0)
                    self.control.stopL(2.0)
                
                self.movement_active = False
                self.emergency_stop_active = True
                logger.warning("🚨 PARADA DE EMERGENCIA ACTIVADA")
                return True
                
        except Exception as e:
            logger.error(f"Error en parada de emergencia: {e}")
            return False

    def deactivate_emergency_stop(self):
        """Desactivar parada de emergencia"""
        with self.lock:
            self.emergency_stop_active = False
            logger.info("✅ Parada de emergencia DESACTIVADA")

    def wait_for_movement_completion_joint(self, target_joints, timeout=5.0):
        """Esperar a que termine el movimiento articular"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.emergency_stop_active:
                return False
            
            if not self.is_connected():
                return True  # En simulación siempre completa
            
            try:
                current_joints = self.get_current_joint_positions()
                
                all_close = True
                for i in range(len(target_joints)):
                    if abs(current_joints[i] - target_joints[i]) > self.position_tolerance_joint:
                        all_close = False
                        break
                
                if all_close:
                    return True
                
                time.sleep(0.02)
                
            except Exception as e:
                logger.error(f"Error verificando posición articular: {e}")
                time.sleep(0.1)
        
        return False

    def wait_for_movement_completion_tcp(self, target_pose, timeout=5.0):
        """Esperar a que termine el movimiento lineal"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.emergency_stop_active:
                return False
            
            if not self.is_connected():
                return True  # En simulación siempre completa
            
            try:
                current_pose = self.get_current_tcp_pose()
                
                # Verificar posición (X, Y, Z)
                position_close = True
                for i in range(3):
                    if abs(current_pose[i] - target_pose[i]) > self.position_tolerance_tcp:
                        position_close = False
                        break
                
                # Verificar orientación (RX, RY, RZ)
                orientation_close = True
                for i in range(3, 6):
                    if abs(current_pose[i] - target_pose[i]) > self.position_tolerance_joint:
                        orientation_close = False
                        break
                
                if position_close and orientation_close:
                    return True
                
                time.sleep(0.02)
                
            except Exception as e:
                logger.error(f"Error verificando pose TCP: {e}")
                time.sleep(0.1)
        
        return False

    def get_robot_status(self):
        """Obtener estado completo del robot"""
        with self.lock:
            status = {
                'connected': self.connected,
                'movement_active': self.movement_active,
                'emergency_stop_active': self.emergency_stop_active,
                'current_position': self.get_current_pose(),
                'speed_level': self.current_speed_level + 1,
                'speed_percentage': int(self.speed_levels[self.current_speed_level] * 100)
            }
        
        if self.is_connected():
            try:
                # Información adicional del robot real
                joints = self.get_current_joint_positions()
                status['joint_positions'] = [np.degrees(j) for j in joints]
            except Exception as e:
                logger.error(f"Error obteniendo información del robot: {e}")
        
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
        """Desconectar del robot"""
        try:
            with self.lock:
                if self.movement_active:
                    self.emergency_stop()
                
                self.connected = False
                
                # Cerrar conexiones RTDE
                if self.control:
                    self.control = None
                if self.receive:
                    self.receive = None
                if self.io:
                    self.io = None
            
            logger.info("✅ Desconectado del robot UR5")
            
        except Exception as e:
            logger.error(f"Error desconectando: {e}")