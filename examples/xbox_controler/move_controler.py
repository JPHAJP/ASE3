import pygame
import sys
import time
import numpy as np
import rtde_control
import rtde_receive
import rtde_io
import threading

class XboxUR5eController:
    def __init__(self, robot_ip="192.168.1.1"):
        # Inicialización de pygame para control Xbox
        pygame.init()
        pygame.joystick.init()
        
        # Verificar controles conectados
        if pygame.joystick.get_count() == 0:
            raise Exception("No se detectaron controles Xbox conectados")
        
        # Conectar al primer control
        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()
        print(f"Control conectado: {self.joystick.get_name()}")
        
        # Inicialización del robot UR5e
        self.robot_ip = robot_ip
        self.control = None
        self.receive = None
        self.io = None
        
        # Parámetros de movimiento - VALORES REDUCIDOS para movimientos más suaves
        self.joint_speed = 0.3  # Reducido de 0.5 a 0.3 rad/s
        self.joint_accel = 0.5  # Reducido de 1.0 a 0.5 rad/s²
        self.linear_speed = 0.05  # Reducido de 0.1 a 0.05 m/s
        self.linear_accel = 0.15  # Reducido de 0.3 a 0.15 m/s²
        
        # NUEVO: Parámetros de blend radius para movimientos suaves
        self.joint_blend_radius = 0.02  # metros
        self.linear_blend_radius = 0.005  # metros
        
        # Configuración de velocidades (múltiples niveles)
        self.speed_levels = [0.1, 0.3, 0.5, 0.8, 1.0]
        self.current_speed_level = 1  # CORREGIDO: Iniciado en nivel 2 (30%) en lugar de nivel 3
        
        # Modo de control
        self.control_mode = "joint"  # "joint" o "linear"
        
        # Estados para detección de cambios
        self.previous_button_states = {}
        self.movement_active = False
        self.movement_thread = None
        self.stop_movement = False
        
        # Estado de parada de emergencia
        self.emergency_stop_active = False
        self.emergency_stop_time = 0
        
        # Incrementos para movimientos - REDUCIDOS para mayor precisión
        self.joint_increment = 0.02  # Reducido de 0.05 a 0.02 radianes por paso
        self.linear_increment = 0.002  # Reducido de 0.005 a 0.002 metros por paso
        
        # Tolerancia para detectar fin de movimiento - MEJORADA
        self.position_tolerance_joint = 0.005  # Más estricta para joints
        self.position_tolerance_tcp = 0.001   # Más estricta para TCP
        
        # Workspace limits for UR5e (in meters)
        self.UR5E_MAX_REACH = 0.85
        self.UR5E_MIN_REACH = 0.18
        
        # Home position in joint angles (degrees)
        self.home_joint_angles_deg = [-51.9, -71.85, -112.7, -85.96, 90, 38]
        self.home_joint_angles_rad = np.radians(self.home_joint_angles_deg)

        # NUEVO: Debug mejorado para botones
        self.debug_mode = True
        self.last_debug_time = 0
        self.debug_interval = 0.3  # Reducido para mejor respuesta
        
        # NUEVO: Control de tiempo para evitar spam de movimientos
        self.last_movement_time = 0
        self.movement_cooldown = 0.05  # 50ms entre movimientos
        
        print("Controlador inicializado. Conectando al robot...")
        
    def initialize_robot(self):
        """Inicializar conexión con el robot UR5e"""
        try:
            self.control = rtde_control.RTDEControlInterface(self.robot_ip)
            self.receive = rtde_receive.RTDEReceiveInterface(self.robot_ip)
            self.io = rtde_io.RTDEIOInterface(self.robot_ip)
            print(f"Conexión establecida con UR5e en {self.robot_ip}")
            return True
        except Exception as e:
            print(f"Error conectando al robot: {e}")
            return False
    
    def get_current_joint_positions(self):
        """Obtener posiciones actuales de las articulaciones"""
        return self.receive.getActualQ()
    
    def get_current_tcp_pose(self):
        """Obtener pose actual del TCP"""
        return self.receive.getActualTCPPose()
    
    def is_point_within_reach(self, x, y, z):
        """Check if the point is within the robot's workspace"""
        point = np.array([x, y, z])
        distance = np.linalg.norm(point)
        return self.UR5E_MIN_REACH <= distance <= self.UR5E_MAX_REACH
    
    def go_home(self):
        """Move robot to home position"""
        if self.emergency_stop_active:
            print("No se puede mover a home: parada de emergencia activa")
            return False
            
        if self.movement_active:
            print("Movimiento en progreso, cancelando para ir a home...")
            
        try:
            print("Moviendo robot a posición home...")
            self.movement_active = True
            
            # CORREGIDO: Usar solo parámetros admitidos
            speed = float(self.joint_speed * self.speed_levels[self.current_speed_level])
            accel = float(self.joint_accel * self.speed_levels[self.current_speed_level])
            
            self.control.moveJ(self.home_joint_angles_rad, speed, accel, False)
            
            # Wait for movement completion
            success = self.wait_for_movement_completion_joint(self.home_joint_angles_rad, timeout=15.0)
            
            self.movement_active = False
            
            if success:
                print("Robot movido a posición home exitosamente")
            else:
                print("Timeout moviendo robot a home")
                
            return success
            
        except Exception as e:
            print(f"Error moviendo robot a home: {e}")
            self.movement_active = False
            return False
    
    def activate_emergency_stop(self):
        """Activate emergency stop"""
        try:
            self.control.stopJ(2.0)
            self.control.stopL(2.0)
            self.movement_active = False
            self.emergency_stop_active = True
            self.emergency_stop_time = time.time()
            print("¡PARADA DE EMERGENCIA ACTIVADA!")
            print("Presiona B nuevamente para desactivar (después de 3 segundos)")
        except Exception as e:
            print(f"Error en parada de emergencia: {e}")
    
    def deactivate_emergency_stop(self):
        """Deactivate emergency stop after timeout"""
        if not self.emergency_stop_active:
            return
            
        current_time = time.time()
        elapsed_time = current_time - self.emergency_stop_time
        
        if elapsed_time >= 3.0:  # Reducido de 5 a 3 segundos
            self.emergency_stop_active = False
            print("Parada de emergencia DESACTIVADA. Sistema listo para operar.")
        else:
            remaining_time = 3.0 - elapsed_time
            print(f"Espera {remaining_time:.1f} segundos más para desactivar parada de emergencia")
    
    def wait_for_movement_completion_joint(self, target_joints, timeout=2.0):
        """Esperar a que termine el movimiento articular comparando posiciones"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.emergency_stop_active:
                return False
                
            try:
                current_joints = self.get_current_joint_positions()
                
                # Verificar si todas las articulaciones están cerca del objetivo
                all_close = True
                for i in range(len(target_joints)):
                    if abs(current_joints[i] - target_joints[i]) > self.position_tolerance_joint:
                        all_close = False
                        break
                
                if all_close:
                    return True
                    
                time.sleep(0.02)  # Reducido de 0.05 a 0.02
                
            except Exception as e:
                print(f"Error verificando posición: {e}")
                time.sleep(0.1)
                
        return False  # Removido mensaje de timeout para movimientos incrementales
    
    def wait_for_movement_completion_tcp(self, target_pose, timeout=2.0):
        """Esperar a que termine el movimiento lineal comparando poses TCP"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.emergency_stop_active:
                return False
                
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
                    
                time.sleep(0.01)
                
            except Exception as e:
                print(f"Error verificando pose TCP: {e}")
                time.sleep(0.01)
                
        return False  # Removido mensaje de timeout
    
    def execute_simultaneous_joint_movements(self, movements):
        """Ejecutar múltiples movimientos articulares simultáneamente"""
        if self.emergency_stop_active or self.movement_active:
            return False
        
        # Control de cooldown
        current_time = time.time()
        if current_time - self.last_movement_time < self.movement_cooldown:
            return False
        
        try:
            current_joints = self.get_current_joint_positions()
            new_joints = list(current_joints)
            
            # Aplicar todos los incrementos
            movement_descriptions = []
            for joint_index, increment, description in movements:
                new_joints[joint_index] += increment
                movement_descriptions.append(description)
            
            # CORRECCIÓN: Convertir todos los valores a float de Python nativo
            new_joints = [float(joint) for joint in new_joints]
            
            # Aplicar límites de seguridad
            joint_limits = [
                (-2*np.pi, 2*np.pi), (-2*np.pi, 2*np.pi), (-np.pi, np.pi),
                (-2*np.pi, 2*np.pi), (-2*np.pi, 2*np.pi), (-2*np.pi, 2*np.pi)
            ]
            
            limits_reached = False
            for i, (min_limit, max_limit) in enumerate(joint_limits):
                if new_joints[i] > max_limit:
                    new_joints[i] = float(max_limit)
                    limits_reached = True
                elif new_joints[i] < min_limit:
                    new_joints[i] = float(min_limit)
                    limits_reached = True
            
            if limits_reached:
                print("ADVERTENCIA: Algunos joints alcanzaron sus límites")
            
            # CORREGIDO: Usar solo los parámetros admitidos por moveJ()
            speed = float(self.joint_speed * self.speed_levels[self.current_speed_level])
            accel = float(self.joint_accel * self.speed_levels[self.current_speed_level])
            
            # Llamada corregida sin parámetros nombrados adicionales
            self.control.moveJ(new_joints, speed, accel, False)
            
            self.last_movement_time = current_time
            
            # Debug más silencioso
            if self.debug_mode and current_time - self.last_debug_time > self.debug_interval:
                print(f"Mov. joints: {', '.join(movement_descriptions)}")
                self.last_debug_time = current_time
            
            return True
            
        except Exception as e:
            print(f"Error en movimientos articulares: {e}")
            return False

    def execute_simultaneous_tcp_movements(self, movements):
        """Ejecutar múltiples movimientos TCP simultáneamente"""
        if self.emergency_stop_active or self.movement_active:
            return False
        
        # Control de cooldown
        current_time = time.time()
        if current_time - self.last_movement_time < self.movement_cooldown:
            return False
        
        try:
            current_pose = self.get_current_tcp_pose()
            new_pose = list(current_pose)
            
            # Aplicar todos los incrementos
            movement_descriptions = []
            for axis, increment, description in movements:
                new_pose[axis] += increment
                movement_descriptions.append(description)
            
            # CORRECCIÓN: Convertir todos los valores a float de Python nativo
            new_pose = [float(pose) for pose in new_pose]
            
            # Verificar límites del workspace solo para posiciones XYZ
            if any(axis < 3 for axis, _, _ in movements):
                if not self.is_point_within_reach(new_pose[0], new_pose[1], new_pose[2]):
                    distance = np.linalg.norm(np.array([new_pose[0], new_pose[1], new_pose[2]]))
                    if current_time - self.last_debug_time > 1.0:  # Limitar warnings
                        print(f"ADVERTENCIA: Fuera del alcance ({distance*1000:.1f}mm)")
                        self.last_debug_time = current_time
                    return False
            
            # CORREGIDO: Usar solo los parámetros admitidos por moveL()
            speed = float(self.linear_speed * self.speed_levels[self.current_speed_level])
            accel = float(self.linear_accel * self.speed_levels[self.current_speed_level])
            
            # Llamada corregida sin parámetros nombrados adicionales
            self.control.moveL(new_pose, speed, accel, False)
            
            self.last_movement_time = current_time
            
            # Debug más silencioso
            if self.debug_mode and current_time - self.last_debug_time > self.debug_interval:
                print(f"Mov. TCP: {', '.join(movement_descriptions)}")
                self.last_debug_time = current_time
            
            return True
            
        except Exception as e:
            print(f"Error en movimientos TCP: {e}")
            return False

    def process_xbox_input(self):
        """Procesar entrada del control Xbox CON MAPEO CORREGIDO"""
        pygame.event.pump()
        
        # NUEVO: Debug completo de todos los botones presionados
        any_button_pressed = False
        pressed_buttons = []
        
        # MAPEO CORREGIDO según tu lista:
        button_mapping = {
            0: "A",          # a -> 0 ✓
            1: "B",          # b -> 1 ✓
            3: "X",          # x -> 3 ✓
            4: "Y",          # y -> 4 ✓
            6: "LB",         # lb -> 6 ✓
            7: "RB",         # rb -> start -> pero RB debería ser 7, necesitamos verificar
            10: "Menu",      # menu -> 10 ✓
            11: "Start",     # start/pausa -> 11 ✓
            12: "Xbox",      # xbox -> 12 ✓
            13: "LS_Click",  # joystickbtn izq -> 13 ✓
            14: "RS_Click",  # joystickbtn derecho -> 14 ✓
            15: "Captura"    # captura -> 15 ✓
        }
        
        # Detectar y reportar TODOS los botones presionados
        for button_id in range(self.joystick.get_numbuttons()):
            current_state = self.joystick.get_button(button_id)
            previous_state = self.previous_button_states.get(button_id, False)
            
            if current_state:
                button_name = button_mapping.get(button_id, f'Btn{button_id}')
                pressed_buttons.append(f"{button_name}")
                any_button_pressed = True
            
            # Detectar presión de botón (transición False -> True)
            if current_state and not previous_state:
                button_name = button_mapping.get(button_id, f"Button{button_id}")
                print(f"🎮 BOTÓN PRESIONADO: {button_name} (ID: {button_id})")
                self.handle_button_press(button_id)
            
            self.previous_button_states[button_id] = current_state
        
        # Mostrar botones actualmente presionados
        if pressed_buttons:
            current_time = time.time()
            if current_time - self.last_debug_time > 0.5:
                print(f"🎮 Botones activos: {', '.join(pressed_buttons)}")
                self.last_debug_time = current_time
        
        # Procesar triggers (ejes analógicos)
        self.process_triggers()
        
        # Procesar joysticks analógicos
        if not self.movement_active and not self.emergency_stop_active:
            self.process_analog_input()
    
    def process_triggers(self):
        """Procesar triggers por separado ya que son ejes, no botones"""
        # Obtener valores de triggers (según tu mapeo lt -> rt, rt -> lt)
        # Los triggers están en los ejes 2 y 5 típicamente, pero necesitamos verificar
        try:
            # Intentar obtener triggers desde diferentes ejes
            num_axes = self.joystick.get_numaxes()
            
            # Buscar triggers en los ejes comunes
            lt_value = 0
            rt_value = 0
            
            # Probar diferentes configuraciones de ejes para triggers
            if num_axes > 4:
                # Configuración común: LT en eje 4, RT en eje 5
                raw_lt = (self.joystick.get_axis(4) + 1) / 2  # Normalizar de 0 a 1
                raw_rt = (self.joystick.get_axis(5) + 1) / 2
                
                # Según tu mapeo: lt -> rt, rt -> lt (están intercambiados)
                lt_value = raw_rt  # Lo que reportas como LT está en RT
                rt_value = raw_lt  # Lo que reportas como RT está en LT
            
            # Debug triggers si están activos
            if lt_value > 0.1 or rt_value > 0.1:
                current_time = time.time()
                if current_time - self.last_debug_time > 0.3:
                    active_triggers = []
                    if lt_value > 0.1:
                        active_triggers.append(f"LT:{lt_value:.2f}")
                    if rt_value > 0.1:
                        active_triggers.append(f"RT:{rt_value:.2f}")
                    print(f"🎯 Triggers activos: {', '.join(active_triggers)}")
                    self.last_debug_time = current_time
            
        except Exception as e:
            print(f"Error procesando triggers: {e}")
    
    def handle_button_press(self, button_id):
        """Manejar presión de botones específicos - MAPEO CORREGIDO"""
        # Mapeo corregido según tu lista
        button_actions = {
            0: "A",          # a -> 0
            1: "B",          # b -> 1  
            3: "X",          # x -> 3
            4: "Y",          # y -> 4
            6: "LB",         # lb -> 6
            7: "RB",         # Asumo que RB es 7, no start
            10: "Menu",      # menu -> 10
            11: "Start",     # start/pausa -> 11
            12: "Xbox",      # xbox -> 12
            13: "LS_Click",  # joystick izq -> 13
            14: "RS_Click",  # joystick der -> 14
            15: "Captura"    # captura -> 15
        }
        
        button_name = button_actions.get(button_id, f"Btn{button_id}")
        print(f"🎮 Procesando botón: {button_name} (ID: {button_id})")
        
        if button_id == 0:  # Botón A - Cambiar modo
            if not self.emergency_stop_active:
                old_mode = self.control_mode
                self.control_mode = "linear" if self.control_mode == "joint" else "joint"
                print(f"✓ Modo cambiado de {old_mode.upper()} a {self.control_mode.upper()}")
        
        elif button_id == 1:  # Botón B - Parada de emergencia / Desactivar parada
            if self.emergency_stop_active:
                print(f"🔄 Intentando desactivar parada de emergencia...")
                self.deactivate_emergency_stop()
            else:
                print(f"🚨 ACTIVANDO PARADA DE EMERGENCIA")
                self.activate_emergency_stop()
        
        elif button_id == 3:  # Botón X - Ir a Home (ahora es el ID 3)
            if not self.emergency_stop_active:
                print(f"🏠 Comando Go Home ejecutándose...")
                success = self.go_home()
                print(f"✓ Go Home {'exitoso' if success else 'falló'}")
        
        elif button_id == 4:  # Botón Y - Nueva función o reservado
            if not self.emergency_stop_active:
                print(f"🔵 Botón Y presionado - Función no asignada")
        
        elif button_id == 6:  # LB - Reducir velocidad (ahora es ID 6)
            if not self.emergency_stop_active:
                old_level = self.current_speed_level
                if self.current_speed_level > 0:
                    self.current_speed_level -= 1
                    print(f"🔽 Velocidad reducida: Nivel {old_level+1} -> {self.current_speed_level + 1} ({self.speed_levels[self.current_speed_level]*100:.0f}%)")
                else:
                    print(f"⚠️ Ya estás en velocidad mínima")
        
        elif button_id == 7:  # RB - Aumentar velocidad (necesita verificación)
            if not self.emergency_stop_active:
                old_level = self.current_speed_level
                if self.current_speed_level < len(self.speed_levels) - 1:
                    self.current_speed_level += 1
                    print(f"🔼 Velocidad aumentada: Nivel {old_level+1} -> {self.current_speed_level + 1} ({self.speed_levels[self.current_speed_level]*100:.0f}%)")
                else:
                    print(f"⚠️ Ya estás en velocidad máxima")
        
        elif button_id == 11:  # Start - Mostrar información (ahora es ID 11)
            print(f"📊 Mostrando estado del sistema...")
            self.show_status()
        
        elif button_id == 10:  # Menu - Toggle debug mode (ahora es ID 10)
            self.debug_mode = not self.debug_mode
            print(f"🐛 Modo debug: {'ACTIVADO' if self.debug_mode else 'DESACTIVADO'}")
        
        elif button_id == 12:  # Xbox button
            print(f"🎮 Botón Xbox presionado - Sin función asignada")
        
        elif button_id == 13:  # Left Stick Click
            print(f"🕹️ Left Stick Click - Sin función asignada")
        
        elif button_id == 14:  # Right Stick Click  
            print(f"🕹️ Right Stick Click - Sin función asignada")
        
        elif button_id == 15:  # Captura
            print(f"📸 Botón Captura presionado - Sin función asignada")
        
        else:
            print(f"❓ Botón {button_name} (ID: {button_id}) no tiene función asignada")
    
    def process_analog_input(self):
        """Procesar entrada de joysticks analógicos CON DEBUG"""
        # Obtener valores de joysticks
        left_x = self.joystick.get_axis(0)
        left_y = self.joystick.get_axis(1)
        right_x = self.joystick.get_axis(2)
        right_y = self.joystick.get_axis(3)
        
        # Obtener triggers CON MAPEO CORREGIDO
        # Según tu mapeo: lt -> rt, rt -> lt
        raw_lt = (self.joystick.get_axis(4) + 1) / 2 if self.joystick.get_numaxes() > 4 else 0
        raw_rt = (self.joystick.get_axis(5) + 1) / 2 if self.joystick.get_numaxes() > 5 else 0
        
        # Intercambiar porque están mapeados al revés
        left_trigger = raw_rt  # Lo que reportas como LT está en RT
        right_trigger = raw_lt  # Lo que reportas como RT está en LT
        
        # Obtener D-pad
        dpad = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
        
        # NUEVO: Debug de entradas analógicas activas
        active_inputs = []
        deadzone = 0.2  # Aumentado para mejor control
        
        if abs(left_x) > deadzone:
            active_inputs.append(f"LX:{left_x:.2f}")
        if abs(left_y) > deadzone:
            active_inputs.append(f"LY:{left_y:.2f}")
        if abs(right_x) > deadzone:
            active_inputs.append(f"RX:{right_x:.2f}")
        if abs(right_y) > deadzone:
            active_inputs.append(f"RY:{right_y:.2f}")
        if left_trigger > 0.1:
            active_inputs.append(f"LT:{left_trigger:.2f}")
        if right_trigger > 0.1:
            active_inputs.append(f"RT:{right_trigger:.2f}")
        if dpad != (0, 0):
            active_inputs.append(f"DPAD:{dpad}")
        
        # Debug de entradas analógicas
        current_time = time.time()
        if active_inputs and self.debug_mode and current_time - self.last_debug_time > 0.3:
            print(f"🕹️ Entradas analógicas: {', '.join(active_inputs)}")
        
        # Aplicar deadzone
        def apply_deadzone(value, zone=deadzone):
            return value if abs(value) > zone else 0
        
        left_x = apply_deadzone(left_x)
        left_y = apply_deadzone(left_y)
        right_x = apply_deadzone(right_x)
        right_y = apply_deadzone(right_y)
        left_trigger = left_trigger if left_trigger > 0.1 else 0
        right_trigger = right_trigger if right_trigger > 0.1 else 0

        # Procesar según modo
        if self.control_mode == "joint":
            self.handle_joint_control(left_x, left_y, right_x, right_y, left_trigger, right_trigger, dpad)
        else:
            self.handle_linear_control(left_x, left_y, right_x, right_y, left_trigger, right_trigger, dpad)

    def handle_joint_control(self, left_x, left_y, right_x, right_y, left_trigger, right_trigger, dpad):
        """Controlar articulaciones individuales - MOVIMIENTOS SIMULTÁNEOS SUAVES"""
        movements = []
        
        # Aplicar curva de respuesta más suave
        def smooth_response(value):
            return np.sign(value) * (value ** 2)
        
        # Joystick izquierdo controla joints 0 y 1
        if abs(left_x) > 0:
            increment = smooth_response(left_x) * self.joint_increment
            movements.append((0, increment, f"J0: {np.degrees(increment):.1f}°"))
        
        if abs(left_y) > 0:
            increment = -smooth_response(left_y) * self.joint_increment
            movements.append((1, increment, f"J1: {np.degrees(increment):.1f}°"))
        
        # Joystick derecho controla joints 2 y 3
        if abs(right_y) > 0:
            increment = -smooth_response(right_y) * self.joint_increment
            movements.append((2, increment, f"J2: {np.degrees(increment):.1f}°"))
        
        if abs(right_x) > 0:
            increment = smooth_response(right_x) * self.joint_increment
            movements.append((3, increment, f"J3: {np.degrees(increment):.1f}°"))
        
        # Triggers controlan joint 4
        trigger_movement = 0
        if left_trigger > 0:
            trigger_movement -= left_trigger * self.joint_increment
        if right_trigger > 0:
            trigger_movement += right_trigger * self.joint_increment
        
        if abs(trigger_movement) > 0:
            movements.append((4, trigger_movement, f"J4: {np.degrees(trigger_movement):.1f}°"))
        
        # D-pad controla joint 5
        if dpad[0] != 0:
            increment = dpad[0] * self.joint_increment
            movements.append((5, increment, f"J5: {np.degrees(increment):.1f}°"))
        
        # Ejecutar movimientos
        if movements:
            self.execute_simultaneous_joint_movements(movements)

    def handle_linear_control(self, left_x, left_y, right_x, right_y, left_trigger, right_trigger, dpad):
       """Controlar movimiento lineal del TCP - MOVIMIENTOS SIMULTÁNEOS SUAVES"""
       movements = []
       
       # Aplicar curva de respuesta más suave
       def smooth_response(value):
           return np.sign(value) * (value ** 2)
       
       # Joystick izquierdo controla X e Y
       if abs(left_x) > 0:
           increment = smooth_response(left_x) * self.linear_increment
           movements.append((0, increment, f"X: {increment*1000:.1f}mm"))
       
       if abs(left_y) > 0:
           increment = -smooth_response(left_y) * self.linear_increment
           movements.append((1, increment, f"Y: {increment*1000:.1f}mm"))
       
       # Joystick derecho Y controla Z
       if abs(right_y) > 0:
           increment = -smooth_response(right_y) * self.linear_increment
           movements.append((2, increment, f"Z: {increment*1000:.1f}mm"))
       
       # Joystick derecho X controla rotación RX
       if abs(right_x) > 0:
           increment = smooth_response(right_x) * self.joint_increment * 0.3
           movements.append((3, increment, f"RX: {np.degrees(increment):.1f}°"))
       
       # Triggers controlan RY
       trigger_movement = 0
       if left_trigger > 0:
           trigger_movement -= left_trigger * self.joint_increment * 0.3
       if right_trigger > 0:
           trigger_movement += right_trigger * self.joint_increment * 0.3
           
       if abs(trigger_movement) > 0:
           movements.append((4, trigger_movement, f"RY: {np.degrees(trigger_movement):.1f}°"))
       
       # D-pad controla RZ
       if dpad[0] != 0:
           increment = dpad[0] * self.joint_increment * 0.3
           movements.append((5, increment, f"RZ: {np.degrees(increment):.1f}°"))
       
       # Ejecutar movimientos
       if movements:
           self.execute_simultaneous_tcp_movements(movements)

    def show_status(self):
        """Mostrar estado actual del sistema - MEJORADO CON MAPEO CORREGIDO"""
        print("\n" + "="*60)
        print("🤖 ESTADO DEL CONTROLADOR UR5e")
        print("="*60)
        print(f"🎮 Control: {self.joystick.get_name()}")
        print(f"🔄 Modo: {self.control_mode.upper()}")
        print(f"⚡ Velocidad: Nivel {self.current_speed_level + 1}/5 ({self.speed_levels[self.current_speed_level]*100:.0f}%)")
        print(f"🚀 Vel. articular: {self.joint_speed * self.speed_levels[self.current_speed_level]:.2f} rad/s")
        print(f"🚀 Vel. lineal: {self.linear_speed * self.speed_levels[self.current_speed_level]:.3f} m/s")
        print(f"🔄 Blend radius joints: {self.joint_blend_radius*1000:.1f}mm")
        print(f"🔄 Blend radius TCP: {self.linear_blend_radius*1000:.1f}mm")
        print(f"⏳ Movimiento activo: {'SÍ' if self.movement_active else 'NO'}")
        print(f"🚨 Parada emergencia: {'ACTIVA' if self.emergency_stop_active else 'INACTIVA'}")
        print(f"🐛 Debug mode: {'ON' if self.debug_mode else 'OFF'}")
        
        # Posiciones actuales
        try:
            joints = self.get_current_joint_positions()
            tcp_pose = self.get_current_tcp_pose()
            tcp_distance = np.linalg.norm(np.array([tcp_pose[0], tcp_pose[1], tcp_pose[2]]))
            within_reach = self.is_point_within_reach(tcp_pose[0], tcp_pose[1], tcp_pose[2])
            
            print(f"\n🔗 Posiciones articulares:")
            for i, angle in enumerate(joints):
                print(f"  J{i}: {np.degrees(angle):+7.1f}°")
            
            print(f"\n🎯 Posición TCP:")
            print(f"  X: {tcp_pose[0]*1000:+7.1f} mm")
            print(f"  Y: {tcp_pose[1]*1000:+7.1f} mm")
            print(f"  Z: {tcp_pose[2]*1000:+7.1f} mm")
            print(f"  RX: {np.degrees(tcp_pose[3]):+7.1f}°")
            print(f"  RY: {np.degrees(tcp_pose[4]):+7.1f}°")
            print(f"  RZ: {np.degrees(tcp_pose[5]):+7.1f}°")
            print(f"📏 Distancia desde base: {tcp_distance*1000:.1f} mm")
            print(f"✅ Dentro del alcance: {'SÍ' if within_reach else 'NO'}")
            
        except Exception as e:
            print(f"❌ Error obteniendo posiciones: {e}")
        
        print(f"\n🎮 CONTROLES CORREGIDOS:")
        print(f"  🅰️ A: Cambiar modo (articular/lineal)")
        print(f"  🅱️ B: Parada de emergencia / Desactivar")
        print(f"  ❌ X: Ir a posición Home")
        print(f"  🟡 Y: Sin función asignada")
        print(f"  🔽 LB: Reducir velocidad")
        print(f"  🔼 RB: Aumentar velocidad (verificar si funciona)")
        print(f"  📋 Menu: Toggle debug mode")
        print(f"  ▶️ Start: Mostrar este estado")
        print(f"  🎮 Xbox: Sin función")
        print(f"  📸 Captura: Sin función")
        print(f"  🕹️ LS/RS Click: Sin función")
        
        if self.control_mode == "joint":
            print(f"\n🔗 MODO ARTICULAR:")
            print(f"  🕹️ Stick izq: Joints 0 (base) y 1 (shoulder)")
            print(f"  🕹️ Stick der: Joints 2 (elbow) y 3 (wrist1)")
            print(f"  🎯 Triggers (LT/RT intercambiados): Joint 4 (wrist2)")
            print(f"  ➡️ D-pad: Joint 5 (wrist3)")
        else:
            print(f"\n📐 MODO LINEAL:")
            print(f"  🕹️ Stick izq: X e Y")
            print(f"  🕹️ Stick der Y: Z")
            print(f"  🕹️ Stick der X: RX (rotación)")
            print(f"  🎯 Triggers (LT/RT intercambiados): RY (rotación)")
            print(f"  ➡️ D-pad: RZ (rotación)")
        
        print(f"\n⚠️ NOTA: Los triggers LT y RT están intercambiados en el hardware")
        print("="*60 + "\n")

    def debug_all_inputs(self):
        """Función de debug para verificar TODOS los inputs del control"""
        print(f"\n🔍 DEBUG COMPLETO DEL CONTROL:")
        print(f"Nombre: {self.joystick.get_name()}")
        print(f"Número de botones: {self.joystick.get_numbuttons()}")
        print(f"Número de ejes: {self.joystick.get_numaxes()}")
        print(f"Número de hats (D-pads): {self.joystick.get_numhats()}")
        
        # Debug de todos los botones
        active_buttons = []
        for i in range(self.joystick.get_numbuttons()):
            if self.joystick.get_button(i):
                active_buttons.append(f"Btn{i}")
        
        if active_buttons:
            print(f"🎮 Botones activos: {', '.join(active_buttons)}")
        
        # Debug de todos los ejes
        active_axes = []
        for i in range(self.joystick.get_numaxes()):
            value = self.joystick.get_axis(i)
            if abs(value) > 0.1:  # Solo mostrar si tiene movimiento significativo
                active_axes.append(f"Eje{i}:{value:.2f}")
        
        if active_axes:
            print(f"🕹️ Ejes activos: {', '.join(active_axes)}")
        
        # Debug de hats (D-pad)
        for i in range(self.joystick.get_numhats()):
            hat_value = self.joystick.get_hat(i)
            if hat_value != (0, 0):
                print(f"🎯 Hat{i}: {hat_value}")

    def run(self):
        """Bucle principal del controlador - MEJORADO"""
        if not self.initialize_robot():
            print("❌ Error: No se pudo conectar al robot")
            return False
        
        print("\n" + "="*60)
        print("🚀 ¡CONTROLADOR XBOX-UR5e INICIADO!")
        print("="*60)
        print("🎮 Controles básicos CORREGIDOS:")
        print("  ▶️ Start (ID 11): Ver todos los controles y estado")
        print("  ❌ X (ID 3): Ir a posición Home")
        print("  🅱️ B (ID 1): Parada de emergencia")
        print("  🅰️ A (ID 0): Cambiar entre modo articular/lineal")
        print("  🔽🔼 LB (ID 6) / RB (ID ?): Cambiar velocidad")
        print("  📋 Menu (ID 10): Toggle debug mode")
        print("\n⚡ Movimientos simultáneos habilitados")
        print("🔄 Blend radius activado para movimientos suaves")
        print("🐛 Debug activado - verás todo lo que presiones")
        print("\n⚠️ IMPORTANTE: Los triggers LT y RT están intercambiados")
        print("⌨️  Presiona Ctrl+C para salir")
        print("="*60)
        
        try:
            clock = pygame.time.Clock()
            
            while True:
                self.process_xbox_input()
                
                # Debug completo cada 2 segundos si hay actividad
                current_time = time.time()
                if self.debug_mode and current_time - self.last_debug_time > 2.0:
                    # Solo hacer debug si hay algún input activo
                    has_input = False
                    for i in range(self.joystick.get_numbuttons()):
                        if self.joystick.get_button(i):
                            has_input = True
                            break
                    
                    if not has_input:
                        for i in range(self.joystick.get_numaxes()):
                            if abs(self.joystick.get_axis(i)) > 0.1:
                                has_input = True
                                break
                    
                    if has_input:
                        self.debug_all_inputs()
                        self.last_debug_time = current_time
                
                clock.tick(100)  # Aumentado a 100 FPS para mejor respuesta
                
        except KeyboardInterrupt:
            print("\n🛑 Desconectando controlador...")
            
        finally:
            # Parar cualquier movimiento en progreso
            try:
                print("🛑 Deteniendo robot...")
                self.control.stopJ(2.0)
                self.control.stopL(2.0)
                self.movement_active = False
                print("✅ Robot detenido")
            except Exception as e:
                print(f"⚠️ Error deteniendo robot: {e}")
            
            pygame.quit()
            print("👋 Controlador desconectado. ¡Hasta luego!")

def main():
   """Función principal con manejo de errores mejorado"""
   # IP del robot UR5e (cambiar según tu configuración)
   robot_ip = "192.168.1.1"
   
   print("🤖 Iniciando controlador Xbox-UR5e...")
   print(f"📡 IP del robot: {robot_ip}")
   
   try:
       controller = XboxUR5eController(robot_ip)
       controller.run()
   except Exception as e:
       print(f"❌ Error crítico iniciando controlador: {e}")
       print("🔧 Verifica:")
       print("  - Control Xbox conectado")
       print("  - Robot UR5e encendido y conectado")
       print("  - IP del robot correcta")
       print("  - Librerías pygame y rtde instaladas")
       return False
   
   return True

if __name__ == "__main__":
   main()