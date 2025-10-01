"""
Controlador Xbox adaptado para la aplicación web
Basado en move_controler.py pero adaptado para funcionar sin bucle principal
"""

import pygame
import time
import threading
import logging
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

class XboxControllerWeb:
    def __init__(self):
        """Inicializar controlador Xbox para aplicación web"""
        # Inicialización de pygame
        pygame.init()
        pygame.joystick.init()
        
        self.joystick = None
        self.connected = False
        self.last_check_time = 0
        
        # Estado del controlador
        self.control_mode = "joint"  # "joint" o "linear"
        self.movement_active = False
        self.debug_mode = True
        
        # Parámetros de movimiento
        self.joint_increment = 0.05
        self.linear_increment = 0.008
        self.speed_levels = [0.1, 0.3, 0.5, 0.8, 1.0]
        self.current_speed_level = 1
        
        # Estados previos de botones para detectar cambios
        self.previous_button_states = {}
        self.last_movement_time = 0
        self.movement_cooldown = 0.05
        self.last_debug_time = 0
        self.debug_interval = 0.3
        
        # Callbacks para eventos
        self.on_button_press = None
        self.on_movement = None
        self.on_mode_change = None
        
        # Lock para thread safety
        self.lock = threading.Lock()
        
        # Intentar conectar
        self.check_connection()
        
        logger.info("XboxControllerWeb inicializado")

    def check_connection(self):
        """Verificar y actualizar estado de conexión del controlador"""
        current_time = time.time()
        
        # Solo verificar cada segundo para no saturar
        if current_time - self.last_check_time < 1.0:
            return self.connected
        
        self.last_check_time = current_time
        
        try:
            pygame.joystick.quit()
            pygame.joystick.init()
            
            joystick_count = pygame.joystick.get_count()
            
            if joystick_count > 0 and not self.connected:
                # Conectar al primer controlador
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
                self.connected = True
                logger.info(f"✅ Xbox Controller conectado: {self.joystick.get_name()}")
                
                # Reiniciar estados de botones
                self.previous_button_states = {}
                
            elif joystick_count == 0 and self.connected:
                # Desconectar
                self.connected = False
                self.joystick = None
                logger.info("❌ Xbox Controller desconectado")
            
            return self.connected
            
        except Exception as e:
            logger.error(f"Error verificando controlador Xbox: {e}")
            self.connected = False
            self.joystick = None
            return False

    def process_input(self):
        """Procesar entrada del controlador Xbox"""
        if not self.check_connection():
            return None
        
        try:
            pygame.event.pump()
            
            # Procesar botones
            button_events = self.process_buttons()
            
            # Procesar entrada analógica si no hay parada de emergencia
            movement_commands = []
            if not self.movement_active:
                movement_commands = self.process_analog_input()
            
            return {
                'button_events': button_events,
                'movement_commands': movement_commands,
                'connected': self.connected,
                'control_mode': self.control_mode
            }
            
        except Exception as e:
            logger.error(f"Error procesando entrada Xbox: {e}")
            self.connected = False
            return None

    def process_buttons(self):
        """Procesar presiones de botones"""
        if not self.connected or not self.joystick:
            return []
        
        button_events = []
        
        # Mapeo de botones corregido
        button_mapping = {
            0: "A",     # Cambiar modo
            1: "B",     # Parada de emergencia
            3: "X",     # Go Home
            4: "Y",     # Función extra
            6: "LB",    # Reducir velocidad
            7: "RB",    # Aumentar velocidad
            10: "Menu", # Toggle debug
            11: "Start" # Mostrar estado
        }
        
        try:
            for button_id in range(self.joystick.get_numbuttons()):
                current_state = self.joystick.get_button(button_id)
                previous_state = self.previous_button_states.get(button_id, False)
                
                # Detectar presión (transición False -> True)
                if current_state and not previous_state:
                    button_name = button_mapping.get(button_id, f"Button{button_id}")
                    
                    event = self.handle_button_press(button_id, button_name)
                    if event:
                        button_events.append(event)
                
                self.previous_button_states[button_id] = current_state
            
            return button_events
            
        except Exception as e:
            logger.error(f"Error procesando botones: {e}")
            return []

    def handle_button_press(self, button_id, button_name):
        """Manejar presión de botón específico"""
        try:
            event = {
                'button_id': button_id,
                'button_name': button_name,
                'action': None,
                'timestamp': datetime.now().isoformat()
            }
            
            if button_id == 0:  # Botón A - Cambiar modo
                old_mode = self.control_mode
                self.control_mode = "linear" if self.control_mode == "joint" else "joint"
                event['action'] = 'mode_change'
                event['old_mode'] = old_mode
                event['new_mode'] = self.control_mode
                
                if self.on_mode_change:
                    self.on_mode_change(old_mode, self.control_mode)
            
            elif button_id == 1:  # Botón B - Parada de emergencia
                event['action'] = 'emergency_stop'
            
            elif button_id == 3:  # Botón X - Go Home
                event['action'] = 'go_home'
            
            elif button_id == 4:  # Botón Y - Función extra
                event['action'] = 'extra_function'
            
            elif button_id == 6:  # LB - Reducir velocidad
                old_level = self.current_speed_level
                if self.current_speed_level > 0:
                    self.current_speed_level -= 1
                    event['action'] = 'speed_decrease'
                    event['old_level'] = old_level
                    event['new_level'] = self.current_speed_level
                
            elif button_id == 7:  # RB - Aumentar velocidad
                old_level = self.current_speed_level
                if self.current_speed_level < len(self.speed_levels) - 1:
                    self.current_speed_level += 1
                    event['action'] = 'speed_increase'
                    event['old_level'] = old_level
                    event['new_level'] = self.current_speed_level
            
            elif button_id == 10:  # Menu - Toggle debug
                self.debug_mode = not self.debug_mode
                event['action'] = 'toggle_debug'
                event['debug_mode'] = self.debug_mode
            
            elif button_id == 11:  # Start - Mostrar estado
                event['action'] = 'show_status'
            
            # Llamar callback si existe
            if self.on_button_press and event['action']:
                self.on_button_press(event)
            
            return event if event['action'] else None
            
        except Exception as e:
            logger.error(f"Error manejando botón {button_name}: {e}")
            return None

    def process_analog_input(self):
        """Procesar entrada analógica de joysticks y triggers"""
        if not self.connected or not self.joystick:
            return []
        
        try:
            # Control de cooldown
            current_time = time.time()
            if current_time - self.last_movement_time < self.movement_cooldown:
                return []
            
            # Obtener valores de ejes
            left_x = self.apply_deadzone(self.joystick.get_axis(0))
            left_y = self.apply_deadzone(self.joystick.get_axis(1))
            right_x = self.apply_deadzone(self.joystick.get_axis(2))
            right_y = self.apply_deadzone(self.joystick.get_axis(3))
            
            # Triggers (intercambiados según el hardware)
            raw_lt = (self.joystick.get_axis(4) + 1) / 2 if self.joystick.get_numaxes() > 4 else 0
            raw_rt = (self.joystick.get_axis(5) + 1) / 2 if self.joystick.get_numaxes() > 5 else 0
            left_trigger = raw_rt  # Intercambiados
            right_trigger = raw_lt
            
            # D-pad
            dpad = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
            
            # Generar comandos de movimiento según el modo
            movement_commands = []
            
            if self.control_mode == "joint":
                movement_commands = self.generate_joint_movements(
                    left_x, left_y, right_x, right_y, left_trigger, right_trigger, dpad
                )
            else:
                movement_commands = self.generate_linear_movements(
                    left_x, left_y, right_x, right_y, left_trigger, right_trigger, dpad
                )
            
            if movement_commands:
                self.last_movement_time = current_time
            
            return movement_commands
            
        except Exception as e:
            logger.error(f"Error procesando entrada analógica: {e}")
            return []

    def apply_deadzone(self, value, zone=0.2):
        """Aplicar zona muerta a valor analógico"""
        return value if abs(value) > zone else 0

    def smooth_response(self, value):
        """Aplicar curva de respuesta suave"""
        return np.sign(value) * (value ** 2)

    def generate_joint_movements(self, left_x, left_y, right_x, right_y, left_trigger, right_trigger, dpad):
        """Generar comandos de movimiento articular"""
        movements = []
        
        # Joystick izquierdo controla joints 0 y 1
        if abs(left_x) > 0:
            increment = self.smooth_response(left_x) * self.joint_increment
            movements.append({
                'type': 'joint',
                'joint': 0,
                'increment': increment,
                'description': f"J0: {np.degrees(increment):.1f}°"
            })
        
        if abs(left_y) > 0:
            increment = -self.smooth_response(left_y) * self.joint_increment
            movements.append({
                'type': 'joint',
                'joint': 1,
                'increment': increment,
                'description': f"J1: {np.degrees(increment):.1f}°"
            })
        
        # Joystick derecho controla joints 2 y 3
        if abs(right_y) > 0:
            increment = -self.smooth_response(right_y) * self.joint_increment
            movements.append({
                'type': 'joint',
                'joint': 2,
                'increment': increment,
                'description': f"J2: {np.degrees(increment):.1f}°"
            })
        
        if abs(right_x) > 0:
            increment = self.smooth_response(right_x) * self.joint_increment
            movements.append({
                'type': 'joint',
                'joint': 3,
                'increment': increment,
                'description': f"J3: {np.degrees(increment):.1f}°"
            })
        
        # Triggers controlan joint 4
        trigger_movement = 0
        if left_trigger > 0:
            trigger_movement -= left_trigger * self.joint_increment
        if right_trigger > 0:
            trigger_movement += right_trigger * self.joint_increment
        
        if abs(trigger_movement) > 0:
            movements.append({
                'type': 'joint',
                'joint': 4,
                'increment': trigger_movement,
                'description': f"J4: {np.degrees(trigger_movement):.1f}°"
            })
        
        # D-pad controla joint 5
        if dpad[0] != 0:
            increment = dpad[0] * self.joint_increment
            movements.append({
                'type': 'joint',
                'joint': 5,
                'increment': increment,
                'description': f"J5: {np.degrees(increment):.1f}°"
            })
        
        return movements

    def generate_linear_movements(self, left_x, left_y, right_x, right_y, left_trigger, right_trigger, dpad):
        """Generar comandos de movimiento lineal TCP"""
        movements = []
        
        # Joystick izquierdo controla X e Y
        if abs(left_x) > 0:
            increment = self.smooth_response(left_x) * self.linear_increment
            movements.append({
                'type': 'linear',
                'axis': 'X',
                'increment': increment,
                'description': f"X: {increment*1000:.1f}mm"
            })
        
        if abs(left_y) > 0:
            increment = -self.smooth_response(left_y) * self.linear_increment
            movements.append({
                'type': 'linear',
                'axis': 'Y',
                'increment': increment,
                'description': f"Y: {increment*1000:.1f}mm"
            })
        
        # Joystick derecho Y controla Z
        if abs(right_y) > 0:
            increment = -self.smooth_response(right_y) * self.linear_increment
            movements.append({
                'type': 'linear',
                'axis': 'Z',
                'increment': increment,
                'description': f"Z: {increment*1000:.1f}mm"
            })
        
        # Joystick derecho X controla RX
        if abs(right_x) > 0:
            increment = self.smooth_response(right_x) * self.joint_increment * 0.3
            movements.append({
                'type': 'linear',
                'axis': 'RX',
                'increment': increment,
                'description': f"RX: {np.degrees(increment):.1f}°"
            })
        
        # Triggers controlan RY
        trigger_movement = 0
        if left_trigger > 0:
            trigger_movement -= left_trigger * self.joint_increment * 0.3
        if right_trigger > 0:
            trigger_movement += right_trigger * self.joint_increment * 0.3
        
        if abs(trigger_movement) > 0:
            movements.append({
                'type': 'linear',
                'axis': 'RY',
                'increment': trigger_movement,
                'description': f"RY: {np.degrees(trigger_movement):.1f}°"
            })
        
        # D-pad controla RZ
        if dpad[0] != 0:
            increment = dpad[0] * self.joint_increment * 0.3
            movements.append({
                'type': 'linear',
                'axis': 'RZ',
                'increment': increment,
                'description': f"RZ: {np.degrees(increment):.1f}°"
            })
        
        return movements

    def get_status(self):
        """Obtener estado actual del controlador"""
        with self.lock:
            return {
                'connected': self.connected,
                'control_mode': self.control_mode,
                'speed_level': self.current_speed_level + 1,
                'speed_percentage': int(self.speed_levels[self.current_speed_level] * 100),
                'debug_mode': self.debug_mode,
                'controller_name': self.joystick.get_name() if self.joystick else None
            }

    def set_callbacks(self, on_button_press=None, on_movement=None, on_mode_change=None):
        """Configurar callbacks para eventos"""
        self.on_button_press = on_button_press
        self.on_movement = on_movement
        self.on_mode_change = on_mode_change

    def disconnect(self):
        """Desconectar controlador"""
        try:
            with self.lock:
                self.connected = False
                if self.joystick:
                    self.joystick.quit()
                    self.joystick = None
                
            pygame.joystick.quit()
            logger.info("✅ Xbox Controller desconectado")
            
        except Exception as e:
            logger.error(f"Error desconectando Xbox Controller: {e}")