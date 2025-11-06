"""
Controlador UR5 en modo desconectado para la aplicación web
Versión simplificada sin cinemática, preparada para URRTDE cuando el robot esté disponible
"""

import numpy as np
import time
import threading
import logging
from datetime import datetime

# URRTDE configurado en modo desconectado por el momento
RTDE_AVAILABLE = False
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
        """Inicializar conexión con el robot UR5e - MODO DESCONECTADO"""
        try:
            logger.warning("🔌 URRTDE en modo desconectado - robot no disponible físicamente")
            self.connected = False
            return False
            
        except Exception as e:
            logger.error(f"❌ Error inicializando controlador: {e}")
            self.connected = False
            return False

    def is_connected(self):
        """Verificar si el robot está conectado - SIEMPRE FALSO EN MODO DESCONECTADO"""
        return False  # Modo desconectado

    def get_current_joint_positions(self):
        """Obtener posiciones actuales de las articulaciones - MODO DESCONECTADO"""
        # En modo desconectado, siempre retornar posición home simulada
        return self.home_joint_angles_rad

    def get_current_tcp_pose(self):
        """Obtener pose actual del TCP - MODO DESCONECTADO"""
        # En modo desconectado, siempre retornar pose home simulada
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
        """Activar parada de emergencia - MODO DESCONECTADO"""
        try:
            with self.lock:
                self.movement_active = False
                self.emergency_stop_active = True
                logger.warning("🚨 PARADA DE EMERGENCIA REGISTRADA (robot no conectado)")
                return True
                
        except Exception as e:
            logger.error(f"Error registrando parada de emergencia: {e}")
            return False

    def deactivate_emergency_stop(self):
        """Desactivar parada de emergencia"""
        with self.lock:
            self.emergency_stop_active = False
            logger.info("✅ Parada de emergencia DESACTIVADA")

    def wait_for_movement_completion_joint(self, target_joints, timeout=5.0):
        """Esperar a que termine el movimiento articular - MODO DESCONECTADO"""
        # En modo desconectado, siempre retornar éxito inmediatamente
        return not self.emergency_stop_active

    def wait_for_movement_completion_tcp(self, target_pose, timeout=5.0):
        """Esperar a que termine el movimiento lineal - MODO DESCONECTADO"""  
        # En modo desconectado, siempre retornar éxito inmediatamente
        return not self.emergency_stop_active

    def get_robot_status(self):
        """Obtener estado completo del robot - MODO DESCONECTADO"""
        with self.lock:
            status = {
                'connected': False,  # Siempre desconectado
                'movement_active': self.movement_active,
                'emergency_stop_active': self.emergency_stop_active,
                'current_position': self.get_current_pose(),
                'speed_level': self.current_speed_level + 1,
                'speed_percentage': int(self.speed_levels[self.current_speed_level] * 100),
                'mode': 'DESCONECTADO'  # Indicador de modo
            }
        
        # En modo desconectado, incluir posiciones articulares simuladas
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