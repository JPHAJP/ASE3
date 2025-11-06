#!/usr/bin/env python3
"""
Aplicación Web Flask para Control del Robot UR5
Integra control Xbox, simulación 3D, control Bluetooth del gripper
"""

from flask import Flask, render_template, request, jsonify, Response
from flask_socketio import SocketIO, emit
import json
import time
import threading
import logging
from datetime import datetime
import os
import sys
import numpy as np

# Importar nuestros módulos
from robot_modules.ur5_controller import UR5WebController
from robot_modules.xbox_controller_web import XboxControllerWeb
from robot_modules.serial_gripper import SerialGripperController
from robot_modules.webcam_controller import webcam_controller

# Configuración de la aplicación
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ur5_robot_control_secret_key_2024'

# Configurar archivos estáticos
app.static_folder = 'static'
app.static_url_path = '/static'

# Configurar SocketIO para comunicación en tiempo real
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('robot_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RobotWebApp:
    def __init__(self):
        """Inicializar la aplicación web del robot"""
        self.robot_ip = "192.168.1.1"  # Cambiar por la IP real del robot
        self.esp32_mac = "88:13:BF:70:40:72"  # Cambiar por la MAC real del ESP32
        
        # Estado de la aplicación
        self.app_state = {
            'robot_connected': False,
            'xbox_connected': False,
            'serial_connected': False,
            'serial_port': None,
            'control_mode': 'coordinates',  # 'coordinates' o 'xbox'
            'robot_status': 'idle',  # 'idle', 'moving', 'error'
            'current_position': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            'saved_positions': {},
            'gripper_force': 5.0,
            'gripper_position': 0.0,
            'system_logs': []
        }
        
        # Lock para acceso thread-safe al estado
        self.state_lock = threading.Lock()
        
        # Inicializar controladores después de que state_lock esté definido
        try:
            self.ur5_controller = UR5WebController(self.robot_ip)
            self.xbox_controller = XboxControllerWeb()
            self.gripper_controller = SerialGripperController()  # Auto-detecta puerto
            
            logger.info("✅ Controladores inicializados correctamente")
        except Exception as e:
            logger.error(f"❌ Error inicializando controladores: {e}")
            # Inicializar controladores en modo simulación
            self.ur5_controller = None
            self.xbox_controller = None
            self.gripper_controller = None
        
        # Hilo para monitoreo continuo
        self.monitoring_thread = None
        self.should_stop_monitoring = False
        
        logger.info("🚀 RobotWebApp inicializada")

    def add_log_message(self, message, log_type='info'):
        """Agregar mensaje al log del sistema"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            'timestamp': timestamp,
            'message': message,
            'type': log_type
        }
        
        with self.state_lock:
            self.app_state['system_logs'].append(log_entry)
            # Mantener solo los últimos 100 logs
            if len(self.app_state['system_logs']) > 100:
                self.app_state['system_logs'] = self.app_state['system_logs'][-100:]
        
        # Emitir log por WebSocket
        socketio.emit('new_log', log_entry)
        logger.info(f"[{log_type.upper()}] {message}")

    def start_monitoring(self):
        """Iniciar hilo de monitoreo del robot"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return
        
        self.should_stop_monitoring = False
        self.monitoring_thread = threading.Thread(target=self._monitor_robot, daemon=True)
        self.monitoring_thread.start()
        self.add_log_message("Monitor del robot iniciado", "info")

    def stop_monitoring(self):
        """Detener hilo de monitoreo"""
        self.should_stop_monitoring = True
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2)

    def _monitor_robot(self):
        """Hilo de monitoreo continuo del estado del robot"""
        while not self.should_stop_monitoring:
            try:
                # Actualizar estado del robot
                if self.ur5_controller and self.ur5_controller.is_connected():
                    current_pos = self.ur5_controller.get_current_pose()
                    if current_pos:
                        with self.state_lock:
                            self.app_state['current_position'] = current_pos
                            self.app_state['robot_connected'] = True
                        
                        # Emitir actualización por WebSocket
                        socketio.emit('robot_status_update', {
                            'position': current_pos,
                            'connected': True,
                            'status': self.app_state['robot_status']
                        })
                
                # Actualizar estado del Xbox controller
                if self.xbox_controller:
                    xbox_status = self.xbox_controller.check_connection()
                    with self.state_lock:
                        self.app_state['xbox_connected'] = xbox_status
                    
                    if xbox_status and self.app_state['control_mode'] == 'xbox':
                        # Procesar entrada del Xbox controller
                        self.xbox_controller.process_input()
                
                time.sleep(0.1)  # Actualizar cada 100ms
                
            except Exception as e:
                logger.error(f"Error en monitoreo: {e}")
                time.sleep(1)

# Instancia global de la aplicación
robot_app = RobotWebApp()

# ==================== RUTAS WEB ====================

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html', app_state=robot_app.app_state)

@app.route('/api/status')
def get_status():
    """Obtener estado actual del sistema"""
    with robot_app.state_lock:
        return jsonify(robot_app.app_state)

# ==================== API REST ====================

@app.route('/api/robot/move', methods=['POST'])
def move_robot():
    """Mover robot a coordenadas específicas"""
    try:
        data = request.get_json()
        x, y, z = float(data['x']), float(data['y']), float(data['z'])
        rx, ry, rz = float(data['rx']), float(data['ry']), float(data['rz'])
        
        robot_app.add_log_message(f"Comando de movimiento: X={x}, Y={y}, Z={z}", "action")
        
        if robot_app.ur5_controller:
            # Ejecutar movimiento real
            success = robot_app.ur5_controller.move_to_coordinates(x, y, z, rx, ry, rz)
            
            if success:
                robot_app.add_log_message("Movimiento completado exitosamente", "action")
                return jsonify({
                    'success': True, 
                    'message': 'Movimiento completado'
                })
            else:
                robot_app.add_log_message("Error en movimiento del robot", "error")
                return jsonify({'success': False, 'message': 'Error en movimiento'})
        else:
            robot_app.add_log_message("Robot no conectado - comando no enviado", "warning")
            return jsonify({
                'success': False, 
                'message': 'Robot no conectado'
            })
    
    except Exception as e:
        robot_app.add_log_message(f"Error en movimiento: {str(e)}", "error")
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/robot/home', methods=['POST'])
def go_home():
    """Mover robot a posición home"""
    try:
        robot_app.add_log_message("Moviendo robot a posición home", "action")
        
        if robot_app.ur5_controller:
            success = robot_app.ur5_controller.go_home()
            if success:
                robot_app.add_log_message("Robot en posición home", "action")
                return jsonify({'success': True, 'message': 'Robot en home'})
            else:
                return jsonify({'success': False, 'message': 'Error yendo a home'})
        else:
            robot_app.add_log_message("Go home simulado", "warning")
            return jsonify({'success': True, 'message': 'Home simulado'})
    
    except Exception as e:
        robot_app.add_log_message(f"Error yendo a home: {str(e)}", "error")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/positions', methods=['GET'])
def get_positions():
    """Obtener posiciones guardadas"""
    with robot_app.state_lock:
        return jsonify(robot_app.app_state['saved_positions'])

@app.route('/api/positions', methods=['POST'])
def save_position():
    """Guardar posición actual"""
    try:
        data = request.get_json()
        name = data['name']
        
        if robot_app.ur5_controller:
            current_pos = robot_app.ur5_controller.get_current_pose()
        else:
            current_pos = robot_app.app_state['current_position']
        
        with robot_app.state_lock:
            robot_app.app_state['saved_positions'][name] = {
                'coordinates': current_pos,
                'timestamp': datetime.now().isoformat()
            }
        
        robot_app.add_log_message(f"Posición '{name}' guardada", "action")
        return jsonify({'success': True, 'message': f"Posición '{name}' guardada"})
    
    except Exception as e:
        robot_app.add_log_message(f"Error guardando posición: {str(e)}", "error")
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/gripper/control', methods=['POST'])
def control_gripper():
    """Controlar gripper con fuerza y distancia"""
    try:
        data = request.get_json()
        force = float(data.get('force', 5.0))
        
        # Soporte para ambos modos: position (legacy) y distance (nuevo)
        if 'distance' in data:
            distance = float(data['distance'])
            robot_app.add_log_message(f"Control gripper: Fuerza={force}N, Distancia={distance}mm", "action")
        else:
            position = float(data.get('position', 0.0))
            distance = position  # Conversión temporal
            robot_app.add_log_message(f"Control gripper: Fuerza={force}N, Posición={position}%", "action")
        
        # Actualizar estado
        with robot_app.state_lock:
            robot_app.app_state['gripper_force'] = force
            robot_app.app_state['gripper_position'] = distance
        
        if robot_app.gripper_controller:
            # Usar el nuevo método de distancia si está disponible
            if hasattr(robot_app.gripper_controller, 'usense_move_to_distance'):
                success, response = robot_app.gripper_controller.usense_move_to_distance(distance)
                if success:
                    return jsonify({
                        'success': True, 
                        'message': 'Comando enviado al gripper',
                        'response': response
                    })
                else:
                    return jsonify({'success': False, 'message': response})
            else:
                # Fallback al método anterior
                success = robot_app.gripper_controller.send_gripper_command(force, distance)
                if success:
                    return jsonify({'success': True, 'message': 'Comando enviado al gripper'})
                else:
                    return jsonify({'success': False, 'message': 'Error comunicando con gripper'})
        else:
            robot_app.add_log_message("Control gripper simulado", "warning")
            return jsonify({'success': True, 'message': 'Control gripper simulado'})
    
    except Exception as e:
        robot_app.add_log_message(f"Error controlando gripper: {str(e)}", "error")
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/gripper/command', methods=['POST'])
def send_gripper_command():
    """Enviar comando específico al gripper uSENSE"""
    try:
        data = request.get_json()
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({'success': False, 'message': 'Comando vacío'}), 400
        
        robot_app.add_log_message(f"Comando gripper: {command}", "action")
        
        if not robot_app.gripper_controller:
            robot_app.add_log_message("Gripper no inicializado", "warning")
            return jsonify({'success': False, 'message': 'Gripper no inicializado'})
        
        # Conectar si no está conectado
        if not robot_app.gripper_controller.connected:
            if not robot_app.gripper_controller.connect():
                return jsonify({'success': False, 'message': 'No se pudo conectar al gripper'})
        
        # Manejar comandos específicos con métodos dedicados
        command_upper = command.upper()
        
        if command_upper == "MOVE GRIP HOME":
            success, response = robot_app.gripper_controller.usense_home_gripper()
        elif command_upper.startswith("MOVE GRIP DIST"):
            try:
                distance = float(command.split()[-1])
                success, response = robot_app.gripper_controller.usense_move_to_distance(distance)
            except (ValueError, IndexError):
                return jsonify({'success': False, 'message': 'Formato inválido. Usar: MOVE GRIP DIST <valor>'})
        elif command_upper.startswith("MOVE GRIP TFORCE"):
            try:
                force = float(command.split()[-1])
                success, response = robot_app.gripper_controller.usense_set_target_force(force)
            except (ValueError, IndexError):
                return jsonify({'success': False, 'message': 'Formato inválido. Usar: MOVE GRIP TFORCE <valor>'})
        elif command_upper == "GET GRIP MMPOS":
            success, response = robot_app.gripper_controller.usense_get_position()
        elif command_upper == "GET GRIP STPOS":
            success, response = robot_app.gripper_controller.usense_get_stepper_position()
        elif command_upper == "GET GRIP FORCENF":
            success, response = robot_app.gripper_controller.usense_get_force_newtons()
        elif command_upper == "GET GRIP FORCEGF":
            success, response = robot_app.gripper_controller.usense_get_force_grams()
        elif command_upper == "GET GRIP DISTOBJ":
            success, response = robot_app.gripper_controller.usense_get_distance_object()
        elif command_upper == "GET GRIP USTEP":
            success, response = robot_app.gripper_controller.usense_get_microstep_setting()
        elif command_upper.startswith("MOVE GRIP STEPS"):
            try:
                steps = int(command.split()[-1])
                success, response = robot_app.gripper_controller.usense_move_steps(steps)
            except (ValueError, IndexError):
                return jsonify({'success': False, 'message': 'Formato inválido. Usar: MOVE GRIP STEPS <número>'})
        elif command_upper.startswith("CONFIG SET MOTORMODE"):
            try:
                mode = int(command.split()[-1])
                success, response = robot_app.gripper_controller.usense_config_motor_mode(mode)
            except (ValueError, IndexError):
                return jsonify({'success': False, 'message': 'Formato inválido. Usar: CONFIG SET MOTORMODE <0|1|2>'})
        elif command_upper == "DO FORCE CAL":
            success, response = robot_app.gripper_controller.usense_do_force_calibration()
        elif command_upper == "DO GRIP REBOOT":
            success, response = robot_app.gripper_controller.usense_reboot_gripper()
        elif command_upper == "CONFIG SAVE":
            success, response = robot_app.gripper_controller.usense_save_config()
        else:
            # Usar método genérico para otros comandos
            success, response = robot_app.gripper_controller.send_custom_command(command, use_retry=True)
        
        if success:
            robot_app.add_log_message(f"Respuesta gripper: {response or 'OK'}", "info")
            return jsonify({
                'success': True,
                'message': 'Comando ejecutado exitosamente',
                'response': response or 'Sin respuesta'
            })
        else:
            robot_app.add_log_message(f"Error gripper: {response}", "error")
            return jsonify({'success': False, 'message': response or 'Error ejecutando comando'})
    
    except Exception as e:
        robot_app.add_log_message(f"Error enviando comando gripper: {str(e)}", "error")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/gripper/status')
def get_gripper_status():
    """Obtener estado detallado del gripper"""
    try:
        if robot_app.gripper_controller:
            status = robot_app.gripper_controller.get_gripper_status()
            return jsonify(status)
        else:
            return jsonify({
                'connected': False,
                'force': 0.0,
                'position': 0.0,
                'port': None,
                'message': 'Gripper no inicializado'
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/gripper/connect', methods=['POST'])
def connect_gripper():
    """Conectar/reconectar al gripper"""
    try:
        if not robot_app.gripper_controller:
            return jsonify({'success': False, 'message': 'Gripper no inicializado'})
        
        success = robot_app.gripper_controller.connect()
        
        if success:
            robot_app.add_log_message("Gripper conectado exitosamente", "info")
            return jsonify({'success': True, 'message': 'Gripper conectado'})
        else:
            robot_app.add_log_message("Error conectando gripper", "error")
            return jsonify({'success': False, 'message': 'Error conectando gripper'})
    
    except Exception as e:
        robot_app.add_log_message(f"Error en conexión gripper: {str(e)}", "error")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/gripper/disconnect', methods=['POST'])
def disconnect_gripper():
    """Desconectar del gripper"""
    try:
        if robot_app.gripper_controller:
            robot_app.gripper_controller.disconnect()
        
        robot_app.add_log_message("Gripper desconectado", "info")
        return jsonify({'success': True, 'message': 'Gripper desconectado'})
    
    except Exception as e:
        robot_app.add_log_message(f"Error desconectando gripper: {str(e)}", "error")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/control-mode', methods=['POST'])
def toggle_control_mode():
    """Cambiar modo de control"""
    try:
        data = request.get_json()
        mode = data['mode']  # 'coordinates' o 'xbox'
        
        with robot_app.state_lock:
            robot_app.app_state['control_mode'] = mode
        
        robot_app.add_log_message(f"Modo de control cambiado a: {mode}", "action")
        return jsonify({'success': True, 'message': f'Modo cambiado a {mode}'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/routines/<int:routine_id>', methods=['POST'])
def run_routine(routine_id):
    """Ejecutar rutina preestablecida"""
    try:
        routines = {
            1: "Rutina de Calibración",
            2: "Ciclo de Prueba", 
            3: "Posición Inicial",
            4: "Rutina de Seguridad"
        }
        
        routine_name = routines.get(routine_id, f"Rutina {routine_id}")
        robot_app.add_log_message(f"Iniciando {routine_name}", "action")
        
        # Simular ejecución de rutina
        def run_routine_async():
            time.sleep(2)  # Simular tiempo de ejecución
            robot_app.add_log_message(f"{routine_name} completada", "action")
        
        threading.Thread(target=run_routine_async, daemon=True).start()
        
        return jsonify({'success': True, 'message': f'{routine_name} iniciada'})
    
    except Exception as e:
        robot_app.add_log_message(f"Error en rutina: {str(e)}", "error")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    """Limpiar logs del sistema"""
    with robot_app.state_lock:
        robot_app.app_state['system_logs'].clear()
    
    robot_app.add_log_message("Log del sistema limpiado", "info")
    return jsonify({'success': True, 'message': 'Logs limpiados'})

# ==================== WEBCAM ENDPOINTS ====================

@app.route('/api/webcam/start', methods=['POST'])
def start_webcam():
    """Iniciar cámara web"""
    try:
        success = webcam_controller.start_camera()
        if success:
            # También iniciar streaming automáticamente
            webcam_controller.start_streaming()
            robot_app.add_log_message("Cámara web iniciada", "info")
            return jsonify({'success': True, 'message': 'Cámara iniciada exitosamente'})
        else:
            return jsonify({'success': False, 'message': 'No se pudo iniciar la cámara'}), 500
            
    except Exception as e:
        logger.error(f"Error iniciando webcam: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/webcam/stop', methods=['POST'])
def stop_webcam():
    """Detener cámara web"""
    try:
        webcam_controller.stop_camera()
        robot_app.add_log_message("Cámara web detenida", "info")
        return jsonify({'success': True, 'message': 'Cámara detenida'})
        
    except Exception as e:
        logger.error(f"Error deteniendo webcam: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/webcam/capture', methods=['POST'])
def capture_photo():
    """Capturar foto con la webcam"""
    try:
        photo_path = webcam_controller.capture_photo()
        if photo_path:
            robot_app.add_log_message(f"Foto capturada: {photo_path}", "info")
            return jsonify({'success': True, 'photo_url': f'/static/{photo_path}'})
        else:
            return jsonify({'success': False, 'message': 'No se pudo capturar la foto'}), 500
            
    except Exception as e:
        logger.error(f"Error capturando foto: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/webcam/status')
def webcam_status():
    """Obtener estado de la webcam"""
    try:
        status = webcam_controller.get_camera_status()
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error obteniendo estado webcam: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/video_feed')
def video_feed():
    """Streaming de video de la webcam"""
    def generate():
        while True:
            try:
                frame_bytes = webcam_controller.get_frame_as_jpeg()
                if frame_bytes:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                else:
                    # Frame placeholder si no hay imagen
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + b'' + b'\r\n')
                time.sleep(1/30)  # ~30 FPS
            except Exception as e:
                logger.error(f"Error en video feed: {e}")
                break
    
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# ==================== WEBSOCKET EVENTS ====================

@socketio.on('connect')
def handle_connect():
    """Manejar conexión WebSocket"""
    emit('status_update', robot_app.app_state)
    robot_app.add_log_message("Cliente WebSocket conectado", "info")

@socketio.on('disconnect')
def handle_disconnect():
    """Manejar desconexión WebSocket"""
    robot_app.add_log_message("Cliente WebSocket desconectado", "info")

@socketio.on('request_status')
def handle_status_request():
    """Solicitud de estado actual"""
    emit('status_update', robot_app.app_state)

# ==================== ARCHIVOS ESTÁTICOS ====================

# ==================== INICIALIZACIÓN ====================

def create_directories():
    """Crear directorios necesarios"""
    directories = [
        'templates',
        'static/css',
        'static/js',
        'robot_modules'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def main():
    """Función principal"""
    create_directories()
    
    # Inicializar logs del sistema
    robot_app.add_log_message("Sistema iniciado correctamente", "info")
    robot_app.add_log_message("Servidor web Flask iniciado", "info")
    
    # Iniciar monitoreo
    robot_app.start_monitoring()
    
    try:
        # Ejecutar aplicación
        logger.info("🚀 Iniciando servidor Flask en http://localhost:5000")
        socketio.run(
            app, 
            debug=False,
            host='0.0.0.0',
            port=5000,
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        logger.info("🛑 Deteniendo aplicación...")
    finally:
        robot_app.stop_monitoring()
        logger.info("👋 Aplicación cerrada")

if __name__ == '__main__':
    main()