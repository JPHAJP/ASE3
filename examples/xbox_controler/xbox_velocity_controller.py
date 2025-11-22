#!/usr/bin/env python3
"""
Controlador Xbox para UR5e usando velocidades continuas por socket
Combinación de move_controler.py y test_velocity_lineal.py
"""

import socket
import pygame
import time
import numpy as np
import threading
import json

class XboxUR5eVelocityController:
    def __init__(self, robot_ip="192.168.0.101", robot_port=30002):
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
        
        # Configuración del robot
        self.robot_ip = robot_ip
        self.robot_port = robot_port
        self.socket = None
        
        # Parámetros de velocidad - múltiples niveles
        self.speed_levels = [0.2, 0.4, 0.6, 0.8, 1.0]
        self.current_speed_level = 1  # Iniciado en nivel 2 (40%)
        
        # Velocidades máximas para movimiento lineal (m/s)
        self.max_linear_velocity = {
            'xy': 0.1,   # Velocidad máxima en X e Y
            'z': 0.08,   # Velocidad máxima en Z
            'rot': 0.5   # Velocidad máxima rotacional (rad/s)
        }
        
        # Velocidades máximas para movimiento articular (rad/s)
        self.max_joint_velocity = [
            1.0,  # Joint 0 (base)
            1.0,  # Joint 1 (shoulder)
            1.5,  # Joint 2 (elbow)
            2.0,  # Joint 3 (wrist1)
            2.0,  # Joint 4 (wrist2)
            2.0   # Joint 5 (wrist3)
        ]
        
        # Configuración de deadzone
        self.deadzone = 0.15
        self.trigger_deadzone = 0.1
        
        # Aceleración para comandos de velocidad
        self.acceleration = 0.5
        self.time_step = 0.1  # Tiempo para comandos de velocidad
        
        # Modo de control
        self.control_mode = "linear"  # "linear" o "joint"
        
        # Posición home
        self.home_joint_angles_deg = [-58.49, -78.0, -98.4, -94.67, 88.77, -109.86]
        self.home_joint_angles_rad = np.radians(self.home_joint_angles_deg)
        
        # Estados para detección de cambios de botones
        self.previous_button_states = {}
        
        # Estado de parada de emergencia
        self.emergency_stop_active = False
        self.emergency_stop_time = 0
        
        # Control de hilo de velocidad
        self.velocity_thread = None
        self.velocity_active = False
        self.current_velocities = {
            'linear': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # [vx, vy, vz, wx, wy, wz]
            'joint': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]   # velocidades articulares
        }
        self.velocity_lock = threading.Lock()
        
        # Control para evitar spam de comandos de parada
        self.last_movement_state = False  # Si había movimiento en la iteración anterior
        self.stop_command_sent = False    # Si ya se envió comando de parada
        
        # Debug
        self.debug_mode = True
        self.last_debug_time = 0
        
        print("Controlador de velocidad inicializado. Conectando al robot...")
        
    def connect_robot(self):
        """Conectar al robot UR5e por socket"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.robot_ip, self.robot_port))
            print(f"Conexión establecida con UR5e en {self.robot_ip}:{self.robot_port}")
            return True
        except Exception as e:
            print(f"Error conectando al robot: {e}")
            return False
    
    def send_command(self, command):
        """Enviar comando al robot"""
        try:
            if self.socket:
                cmd_bytes = (command + "\n").encode('utf-8')
                self.socket.send(cmd_bytes)
                
                # Debug: mostrar comando enviado si el debug está activo
                # Pero no mostrar comandos de parada repetitivos
                if self.debug_mode:
                    if not (command.startswith('stopl(') or command.startswith('stopj(')):
                        print(f"📤 Comando enviado: {command}")
                    elif not hasattr(self, '_last_debug_stop') or self._last_debug_stop != command:
                        print(f"📤 Comando enviado: {command} (parada)")
                        self._last_debug_stop = command
                
                return True
            else:
                print("❌ No hay conexión con el robot")
                return False
        except Exception as e:
            print(f"❌ Error enviando comando: {e}")
            return False
    
    def send_speedl(self, vx, vy, vz, wx, wy, wz, a=None, t=None):
        """Enviar comando de velocidad lineal"""
        if a is None:
            a = self.acceleration
        if t is None:
            t = self.time_step
        
        cmd = f"speedl([{vx:.5f}, {vy:.5f}, {vz:.5f}, {wx:.5f}, {wy:.5f}, {wz:.5f}], {a}, {t})"
        return self.send_command(cmd)
    
    def send_speedj(self, q0, q1, q2, q3, q4, q5, a=None, t=None):
        """Enviar comando de velocidad articular"""
        if a is None:
            a = self.acceleration
        if t is None:
            t = self.time_step
        
        cmd = f"speedj([{q0:.5f}, {q1:.5f}, {q2:.5f}, {q3:.5f}, {q4:.5f}, {q5:.5f}], {a}, {t})"
        return self.send_command(cmd)
    
    def send_stopl(self, a=None):
        """Detener movimiento lineal"""
        if a is None:
            a = self.acceleration
        cmd = f"stopl({a})"
        return self.send_command(cmd)
    
    def send_stopj(self, a=None):
        """Detener movimiento articular"""
        if a is None:
            a = self.acceleration
        cmd = f"stopj({a})"
        return self.send_command(cmd)
    
    def go_home(self):
        """Mover robot a posición home"""
        if self.emergency_stop_active:
            print("No se puede ir a home: parada de emergencia activa")
            return False
        
        try:
            print("🏠 Moviendo robot a posición home...")
            
            # Detener cualquier movimiento actual
            self.send_stopl()
            self.send_stopj()
            time.sleep(0.1)
            
            # Usar sintaxis URScript que funciona
            joint_angles = ", ".join([f"{angle:.5f}" for angle in self.home_joint_angles_rad])
            
            # Usar la sintaxis simple que ya sabemos que funciona
            cmd = f"movej([{joint_angles}], 2.5, 1.5)"
            
            print(f"🔧 Enviando comando: {cmd}")
            success = self.send_command(cmd)
            
            if success:
                print("✅ Robot movido a posición home exitosamente")
                time.sleep(5.0)  # Tiempo estimado para llegar a home
                print("✅ Robot en posición home")
            else:
                print("❌ Error enviando comando al robot")
                
            return success
            
        except Exception as e:
            print(f"❌ Error moviendo robot a home: {e}")
            return False
    
    def test_simple_movement(self):
        """Función de prueba para enviar comandos simples"""
        print("🧪 Probando diferentes sintaxis de movimiento...")
        
        # Comandos de prueba con diferentes sintaxis
        test_commands = [
            "movej([0, -1.57, 0, -1.57, 0, 0], 1.0, 1.0)",  # Posición simple
            "movej([0, -1.57, 0, -1.57, 0, 0], 1.0, 1.0, 5.0)",  # Con tiempo
            "moveJ([0, -1.57, 0, -1.57, 0, 0], 1.0, 1.0)",  # J mayúscula
            "movej([0, -1.57, 0, -1.57, 0, 0], a=1.0, v=1.0)",  # Con parámetros nombrados
        ]
        
        for i, cmd in enumerate(test_commands, 1):
            print(f"🔧 Probando comando {i}: {cmd}")
            success = self.send_command(cmd)
            if success:
                print(f"✅ Comando {i} enviado exitosamente")
                time.sleep(3)  # Dar tiempo al movimiento
                break
            else:
                print(f"❌ Comando {i} falló")
        
        return success
    
    def go_home_alternative(self):
        """Versión alternativa para ir a home usando sintaxis URScript estándar"""
        if self.emergency_stop_active:
            print("No se puede ir a home: parada de emergencia activa")
            return False
        
        try:
            print("🏠 [ALTERNATIVA] Moviendo robot a posición home...")
            
            # Detener movimientos actuales
            self.send_stopl()
            self.send_stopj()
            time.sleep(0.1)
            
            # Usar sintaxis URScript estándar: movej(q, a, v, t, r)
            joint_angles = [f"{angle:.5f}" for angle in self.home_joint_angles_rad]
            joints_str = f"[{', '.join(joint_angles)}]"
            
            # Sintaxis más estándar para robots UR
            cmd = f"movej({joints_str}, a=1.5, v=1.0, t=0, r=0)"
            
            print(f"🔧 Comando alternativo: {cmd}")
            success = self.send_command(cmd)
            
            if success:
                print("✅ Comando alternativo enviado")
                time.sleep(6)  # Dar tiempo al movimiento
                print("✅ Movimiento alternativo completado")
            else:
                print("❌ Error en comando alternativo")
                
            return success
            
        except Exception as e:
            print(f"❌ Error en movimiento alternativo: {e}")
            return False
    
    def apply_deadzone(self, value, deadzone=None):
        """Aplicar zona muerta a valor analógico"""
        if deadzone is None:
            deadzone = self.deadzone
        return 0.0 if abs(value) < deadzone else value
    
    def velocity_control_thread(self):
        """Hilo para envío continuo de comandos de velocidad"""
        while self.velocity_active:
            try:
                with self.velocity_lock:
                    has_movement = False
                    
                    if self.control_mode == "linear":
                        vx, vy, vz, wx, wy, wz = self.current_velocities['linear']
                        if any(abs(v) > 0.001 for v in [vx, vy, vz, wx, wy, wz]):
                            self.send_speedl(vx, vy, vz, wx, wy, wz)
                            has_movement = True
                            self.stop_command_sent = False  # Reset flag de parada
                        else:
                            # Solo enviar comando de parada si había movimiento antes
                            if self.last_movement_state and not self.stop_command_sent:
                                self.send_stopl()
                                self.stop_command_sent = True
                                
                    else:  # joint mode
                        q0, q1, q2, q3, q4, q5 = self.current_velocities['joint']
                        if any(abs(q) > 0.001 for q in [q0, q1, q2, q3, q4, q5]):
                            self.send_speedj(q0, q1, q2, q3, q4, q5)
                            has_movement = True
                            self.stop_command_sent = False  # Reset flag de parada
                        else:
                            # Solo enviar comando de parada si había movimiento antes
                            if self.last_movement_state and not self.stop_command_sent:
                                self.send_stopj()
                                self.stop_command_sent = True
                    
                    # Actualizar estado de movimiento
                    self.last_movement_state = has_movement
                
                time.sleep(0.03)  # ~33 Hz
                
            except Exception as e:
                print(f"Error en hilo de velocidad: {e}")
                time.sleep(0.1)
    
    def start_velocity_control(self):
        """Iniciar control de velocidad continuo"""
        if not self.velocity_active:
            self.velocity_active = True
            self.velocity_thread = threading.Thread(target=self.velocity_control_thread)
            self.velocity_thread.daemon = True
            self.velocity_thread.start()
            print("Control de velocidad iniciado")
    
    def stop_velocity_control(self):
        """Detener control de velocidad continuo"""
        if self.velocity_active:
            self.velocity_active = False
            if self.velocity_thread:
                self.velocity_thread.join(timeout=1.0)
            
            # Enviar comando de parada
            if self.control_mode == "linear":
                self.send_stopl()
            else:
                self.send_stopj()
            
            print("Control de velocidad detenido")
    
    def update_velocities(self, velocities, mode):
        """Actualizar velocidades objetivo"""
        with self.velocity_lock:
            if mode == "linear":
                self.current_velocities['linear'] = velocities[:]
            else:
                self.current_velocities['joint'] = velocities[:]
    
    def process_xbox_input(self):
        """Procesar entrada del control Xbox"""
        pygame.event.pump()
        
        # Procesar botones
        for button_id in range(self.joystick.get_numbuttons()):
            current_state = self.joystick.get_button(button_id)
            previous_state = self.previous_button_states.get(button_id, False)
            
            # Detectar presión de botón (transición False -> True)
            if current_state and not previous_state:
                self.handle_button_press(button_id)
            
            self.previous_button_states[button_id] = current_state
        
        # Procesar entradas analógicas solo si no hay parada de emergencia
        if not self.emergency_stop_active:
            self.process_analog_input()
    
    def handle_button_press(self, button_id):
        """Manejar presión de botones específicos"""
        button_actions = {
            0: "A",          # a -> 0
            1: "B",          # b -> 1  
            3: "X",          # x -> 3
            4: "Y",          # y -> 4
            6: "LB",         # lb -> 6
            7: "RB",         # rb -> 7
            10: "Menu",      # menu -> 10
            11: "Start",     # start -> 11
        }
        
        button_name = button_actions.get(button_id, f"Btn{button_id}")
        
        if self.debug_mode:
            print(f"🎮 Botón presionado: {button_name} (ID: {button_id})")
        
        if button_id == 0:  # Botón A - Cambiar modo
            if not self.emergency_stop_active:
                old_mode = self.control_mode
                self.control_mode = "joint" if self.control_mode == "linear" else "linear"
                print(f"🔄 Modo cambiado: {old_mode} → {self.control_mode}")
                
                # Detener movimiento al cambiar modo
                self.stop_all_movement()
        
        elif button_id == 1:  # Botón B - Parada de emergencia / Desactivar
            if self.emergency_stop_active:
                self.deactivate_emergency_stop()
            else:
                self.activate_emergency_stop()
        
        elif button_id == 3:  # Botón X - Ir a posición Home
            if not self.emergency_stop_active:
                print("🏠 Yendo a posición Home...")
                self.go_home()
        
        elif button_id == 4:  # Botón Y - Detener todo movimiento
            if not self.emergency_stop_active:
                self.stop_all_movement()
                print("🛑 Todos los movimientos detenidos")
        
        elif button_id == 5:  # Botón RT (prueba) - Test simple movement
            if not self.emergency_stop_active:
                print("🧪 Probando movimiento simple...")
                self.test_simple_movement()
        
        elif button_id == 2:  # Botón RT alternativo - Home alternativo
            if not self.emergency_stop_active:
                print("🏠 [ALT] Probando home alternativo...")
                self.go_home_alternative()
        
        elif button_id == 6:  # LB - Reducir velocidad
            if not self.emergency_stop_active and self.current_speed_level > 0:
                self.current_speed_level -= 1
                print(f"🔽 Velocidad reducida: Nivel {self.current_speed_level + 1}/5 ({self.speed_levels[self.current_speed_level]*100:.0f}%)")
        
        elif button_id == 7:  # RB - Aumentar velocidad
            if not self.emergency_stop_active and self.current_speed_level < len(self.speed_levels) - 1:
                self.current_speed_level += 1
                print(f"🔼 Velocidad aumentada: Nivel {self.current_speed_level + 1}/5 ({self.speed_levels[self.current_speed_level]*100:.0f}%)")
        
        elif button_id == 11:  # Start - Mostrar información
            self.show_status()
        
        elif button_id == 10:  # Menu - Toggle debug mode
            self.debug_mode = not self.debug_mode
            print(f"🐛 Modo debug: {'ACTIVADO' if self.debug_mode else 'DESACTIVADO'}")
    
    def process_analog_input(self):
        """Procesar entrada de joysticks analógicos"""
        # Obtener valores de joysticks
        left_x = self.apply_deadzone(self.joystick.get_axis(0))
        left_y = self.apply_deadzone(-self.joystick.get_axis(1))  # Invertir Y
        right_x = self.apply_deadzone(self.joystick.get_axis(2))
        right_y = self.apply_deadzone(-self.joystick.get_axis(3))  # Invertir Y
        
        # Obtener D-pad (ahora usado en lugar de triggers)
        dpad = self.joystick.get_hat(0) if self.joystick.get_numhats() > 0 else (0, 0)
        
        # Aplicar curva de respuesta suave
        def smooth_response(value):
            return np.sign(value) * (value ** 2)
        
        # Calcular velocidades según el modo
        if self.control_mode == "linear":
            velocities = self.calculate_linear_velocities(
                left_x, left_y, right_x, right_y, dpad, smooth_response
            )
            self.update_velocities(velocities, "linear")
        else:
            velocities = self.calculate_joint_velocities(
                left_x, left_y, right_x, right_y, dpad, smooth_response
            )
            self.update_velocities(velocities, "joint")
    
    def calculate_linear_velocities(self, left_x, left_y, right_x, right_y, dpad, smooth_func):
        """Calcular velocidades lineales del TCP"""
        speed_factor = self.speed_levels[self.current_speed_level]
        
        # Velocidades lineales
        vx = smooth_func(left_x) * self.max_linear_velocity['xy'] * speed_factor
        vy = smooth_func(left_y) * self.max_linear_velocity['xy'] * speed_factor
        vz = smooth_func(right_y) * self.max_linear_velocity['z'] * speed_factor
        
        # Velocidades rotacionales
        wx = smooth_func(right_x) * self.max_linear_velocity['rot'] * speed_factor * 0.3
        
        # D-pad controla rotación Y (arriba/abajo del D-pad)
        wy = dpad[1] * self.max_linear_velocity['rot'] * speed_factor * 0.3
        
        # D-pad controla rotación Z (izquierda/derecha del D-pad)
        wz = dpad[0] * self.max_linear_velocity['rot'] * speed_factor * 0.3
        
        return [vx, vy, vz, wx, wy, wz]
    
    def calculate_joint_velocities(self, left_x, left_y, right_x, right_y, dpad, smooth_func):
        """Calcular velocidades articulares"""
        speed_factor = self.speed_levels[self.current_speed_level]
        velocities = [0.0] * 6
        
        # Joystick izquierdo controla joints 0 y 1
        velocities[0] = smooth_func(left_x) * self.max_joint_velocity[0] * speed_factor
        velocities[1] = smooth_func(left_y) * self.max_joint_velocity[1] * speed_factor
        
        # Joystick derecho controla joints 2 y 3
        velocities[2] = smooth_func(right_y) * self.max_joint_velocity[2] * speed_factor
        velocities[3] = smooth_func(right_x) * self.max_joint_velocity[3] * speed_factor
        
        # D-pad controla joint 4 (arriba/abajo del D-pad)
        velocities[4] = dpad[1] * self.max_joint_velocity[4] * speed_factor
        
        # D-pad controla joint 5 (izquierda/derecha del D-pad)
        velocities[5] = dpad[0] * self.max_joint_velocity[5] * speed_factor
        
        return velocities
    
    def stop_all_movement(self):
        """Detener todos los movimientos"""
        # Limpiar velocidades
        with self.velocity_lock:
            self.current_velocities['linear'] = [0.0] * 6
            self.current_velocities['joint'] = [0.0] * 6
        
        # Resetear flags para permitir nuevos comandos de parada cuando sea necesario
        self.last_movement_state = False
        self.stop_command_sent = False
        
        # Enviar comandos de parada una sola vez
        self.send_stopl()
        self.send_stopj()
        
        # Marcar que ya se enviaron comandos de parada
        self.stop_command_sent = True
    
    def activate_emergency_stop(self):
        """Activar parada de emergencia"""
        self.stop_all_movement()
        self.emergency_stop_active = True
        self.emergency_stop_time = time.time()
        print("🚨 ¡PARADA DE EMERGENCIA ACTIVADA!")
        print("Presiona B nuevamente para desactivar (después de 3 segundos)")
    
    def deactivate_emergency_stop(self):
        """Desactivar parada de emergencia después del timeout"""
        if not self.emergency_stop_active:
            return
            
        current_time = time.time()
        elapsed_time = current_time - self.emergency_stop_time
        
        if elapsed_time >= 3.0:
            self.emergency_stop_active = False
            print("✅ Parada de emergencia DESACTIVADA. Sistema listo para operar.")
        else:
            remaining_time = 3.0 - elapsed_time
            print(f"⏳ Espera {remaining_time:.1f} segundos más para desactivar parada de emergencia")
    
    def show_status(self):
        """Mostrar estado actual del sistema"""
        print("\n" + "="*60)
        print("🤖 ESTADO DEL CONTROLADOR UR5e POR VELOCIDAD")
        print("="*60)
        print(f"🎮 Control: {self.joystick.get_name()}")
        print(f"🔄 Modo: {self.control_mode.upper()}")
        print(f"⚡ Velocidad: Nivel {self.current_speed_level + 1}/5 ({self.speed_levels[self.current_speed_level]*100:.0f}%)")
        print(f"📡 Conexión: {'OK' if self.socket else 'ERROR'}")
        print(f"🚨 Parada emergencia: {'ACTIVA' if self.emergency_stop_active else 'INACTIVA'}")
        print(f"🐛 Debug mode: {'ON' if self.debug_mode else 'OFF'}")
        print(f"⚡ Control velocidad: {'ACTIVO' if self.velocity_active else 'INACTIVO'}")
        
        # Velocidades actuales
        with self.velocity_lock:
            if self.control_mode == "linear":
                vx, vy, vz, wx, wy, wz = self.current_velocities['linear']
                print(f"\n🎯 Velocidades lineales actuales:")
                print(f"  VX: {vx*1000:+7.1f} mm/s")
                print(f"  VY: {vy*1000:+7.1f} mm/s")
                print(f"  VZ: {vz*1000:+7.1f} mm/s")
                print(f"  WX: {np.degrees(wx):+7.1f} °/s")
                print(f"  WY: {np.degrees(wy):+7.1f} °/s")
                print(f"  WZ: {np.degrees(wz):+7.1f} °/s")
            else:
                q0, q1, q2, q3, q4, q5 = self.current_velocities['joint']
                print(f"\n🔗 Velocidades articulares actuales:")
                for i, vel in enumerate([q0, q1, q2, q3, q4, q5]):
                    print(f"  Joint {i}: {np.degrees(vel):+7.1f} °/s")
        
        print(f"\n🎮 CONTROLES:")
        print(f"  🅰️ A: Cambiar modo (linear/joint)")
        print(f"  🅱️ B: Parada de emergencia / Desactivar")
        print(f"  ❌ X: Ir a posición Home")
        print(f"  🟡 Y: Detener todos los movimientos")
        print(f"  🔽 LB: Reducir velocidad")
        print(f"  🔼 RB: Aumentar velocidad")
        print(f"  📋 Menu: Toggle debug mode")
        print(f"  ▶️ Start: Mostrar este estado")
        
        if self.control_mode == "linear":
            print(f"\n📐 MODO LINEAL (velocidad continua):")
            print(f"  🕹️ Stick izq: Velocidad X e Y")
            print(f"  🕹️ Stick der Y: Velocidad Z")
            print(f"  🕹️ Stick der X: Velocidad rotacional RX")
            print(f"  🎯 D-pad: Velocidad rotacional RY (↑↓) y RZ (←→)")
        else:
            print(f"\n🔗 MODO ARTICULAR (velocidad continua):")
            print(f"  🕹️ Stick izq: Velocidad Joints 0 y 1")
            print(f"  🕹️ Stick der: Velocidad Joints 2 y 3")
            print(f"  🎯 D-pad: Velocidad Joint 4 (↑↓) y Joint 5 (←→)")
        
        print("="*60 + "\n")
    
    def run(self):
        """Bucle principal del controlador"""
        if not self.connect_robot():
            print("❌ Error: No se pudo conectar al robot")
            return False
        
        print("\n" + "="*60)
        print("🚀 ¡CONTROLADOR XBOX-UR5e POR VELOCIDAD INICIADO!")
        print("="*60)
        print("📡 Usando conexión por socket en puerto 30002")
        print("⚡ Control de velocidad continua habilitado")
        print("🎮 Controles básicos:")
        print("  ▶️ Start: Ver todos los controles y estado")
        print("  ❌ X: Ir a posición Home")
        print("  🟡 Y: Detener todos los movimientos")
        print("  🅱️ B: Parada de emergencia")
        print("  🅰️ A: Cambiar entre modo lineal/articular")
        print("  🔽🔼 LB/RB: Cambiar velocidad")
        print("\n⚠️ IMPORTANTE: Los triggers ya no se usan, ahora usa D-pad")
        print("⌨️ Presiona Ctrl+C para salir")
        print("="*60)
        
        # Iniciar control de velocidad
        self.start_velocity_control()
        
        try:
            clock = pygame.time.Clock()
            
            while True:
                self.process_xbox_input()
                clock.tick(60)  # 60 FPS para respuesta fluida
                
        except KeyboardInterrupt:
            print("\n🛑 Desconectando controlador...")
            
        finally:
            # Detener control de velocidad
            self.stop_velocity_control()
            
            # Cerrar conexión
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
            
            pygame.quit()
            print("👋 Controlador desconectado. ¡Hasta luego!")

def main():
    """Función principal"""
    robot_ip = "192.168.0.101"
    robot_port = 30002
    
    print("🤖 Iniciando controlador Xbox-UR5e por velocidad...")
    print(f"📡 IP del robot: {robot_ip}:{robot_port}")
    
    try:
        controller = XboxUR5eVelocityController(robot_ip, robot_port)
        controller.run()
    except Exception as e:
        print(f"❌ Error crítico iniciando controlador: {e}")
        print("🔧 Verifica:")
        print("  - Control Xbox conectado")
        print("  - Robot UR5e encendido y conectado")
        print("  - IP del robot correcta")
        print("  - Puerto 30002 disponible")
        print("  - Librería pygame instalada")
        return False
    
    return True

if __name__ == "__main__":
    main()