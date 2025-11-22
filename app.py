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
from robot_modules.gripper_config import get_gripper_controller, get_connection_info, get_current_config
from robot_modules.webcam_simple import WebcamController

# Instancia global del controlador de webcam
webcam_controller = WebcamController()

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
        self.robot_ip = "192.168.0.101"  # IP del robot en la red ethernet
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
            self.gripper_controller = get_gripper_controller()  # Usa configuración automática
            
            # Mostrar información de conexión del gripper
            conn_info = get_connection_info()
            logger.info(f"📡 Gripper: {conn_info['description']}")
            
            # Conectar proactivamente al gripper en la inicialización
            logger.info("🔧 Conectando al gripper durante inicialización...")
            if self.gripper_controller.connect():
                logger.info("✅ Gripper conectado exitosamente durante inicialización")
            else:
                logger.warning("⚠️ No se pudo conectar al gripper durante inicialización (se reintentará cuando se necesite)")
            
            logger.info("✅ Controladores inicializados correctamente")
        except Exception as e:
            logger.error(f"❌ Error inicializando controladores: {e}")
            # Inicializar controladores en modo simulación
            self.ur5_controller = None
            self.gripper_controller = None
        
        # Hilo para monitoreo continuo
        self.monitoring_thread = None
        self.should_stop_monitoring = False
        
        # Hilo específico para monitoreo del gripper
        self.gripper_monitoring_thread = None
        self.should_stop_gripper_monitoring = False
        
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

    def emit_gripper_status(self):
        """Emitir estado actual del gripper por WebSocket"""
        try:
            if self.gripper_controller:
                status = self.gripper_controller.get_gripper_status() if hasattr(self.gripper_controller, 'get_gripper_status') else {'connected': self.gripper_controller.connected}
                
                # Agregar información de configuración
                from robot_modules.gripper_config import get_connection_info
                connection_info = get_connection_info()
                status['connection_info'] = connection_info
                
                socketio.emit('gripper_status', status)
            else:
                from robot_modules.gripper_config import get_connection_info
                connection_info = get_connection_info()
                socketio.emit('gripper_status', {
                    'connected': False,
                    'connection_info': connection_info
                })
        except Exception as e:
            logger.error(f"Error emitiendo estado del gripper: {e}")

    def start_monitoring(self):
        """Iniciar hilo de monitoreo del robot"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return
        
        self.should_stop_monitoring = False
        self.monitoring_thread = threading.Thread(target=self._monitor_robot, daemon=True)
        self.monitoring_thread.start()
        
        # Iniciar también monitoreo del gripper
        self.start_gripper_monitoring()

    def start_gripper_monitoring(self):
        """Iniciar hilo de monitoreo específico del gripper"""
        if self.gripper_monitoring_thread and self.gripper_monitoring_thread.is_alive():
            return
        
        if not self.gripper_controller:
            logger.warning("⚠️ No se puede iniciar monitoreo del gripper: controlador no disponible")
            return
        
        self.should_stop_gripper_monitoring = False
        self.gripper_monitoring_thread = threading.Thread(target=self._monitor_gripper, daemon=True)
        self.gripper_monitoring_thread.start()
        logger.info("🔍 Monitoreo del gripper iniciado")

    def _monitor_gripper(self):
        """Monitor continuo del gripper para capturar todas las respuestas"""
        last_emission_time = 0
        
        while not self.should_stop_gripper_monitoring:
            try:
                if self.gripper_controller and self.gripper_controller.connected:
                    # Obtener todas las respuestas recibidas
                    received_data = self.gripper_controller.get_received_data()
                    
                    current_time = time.time()
                    
                    for data_item in received_data:
                        # Emitir cada respuesta inmediatamente por WebSocket
                        socketio.emit('gripper_live_response', {
                            'response': data_item['data'],
                            'timestamp': data_item.get('timestamp', datetime.now().strftime('%H:%M:%S.%f')[:-3]),
                            'is_live': True
                        })
                        
                        # Solo agregar al log del sistema cada 2 segundos para evitar spam
                        if current_time - last_emission_time > 2.0:
                            self.add_log_message(f"Gripper Monitor → {data_item['data']}", "info")
                            last_emission_time = current_time
                
                # Pausa para no sobrecargar
                time.sleep(0.2)
                
            except Exception as e:
                if not self.should_stop_gripper_monitoring:
                    logger.error(f"❌ Error en monitoreo del gripper: {e}")
                    time.sleep(1)  # Pausa más larga en caso de error

    def stop_monitoring(self):
        """Detener hilos de monitoreo"""
        self.should_stop_monitoring = True
        self.should_stop_gripper_monitoring = True
        
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2)
        
        if self.gripper_monitoring_thread:
            self.gripper_monitoring_thread.join(timeout=2)
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
                            
                            # Actualizar estado Xbox desde UR5Controller integrado
                            xbox_status = self.ur5_controller.get_xbox_status()
                            self.app_state['xbox_connected'] = xbox_status.get('xbox_connected', False)
                        
                        # Emitir actualización por WebSocket
                        socketio.emit('robot_status_update', {
                            'position': current_pos,
                            'connected': True,
                            'status': self.app_state['robot_status'],
                            'xbox_status': xbox_status
                        })
                
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
    """Enviar comando específico al gripper uSENSE - SIN LIMITACIONES"""
    try:
        data = request.get_json()
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({'success': False, 'message': 'Comando vacío'}), 400
        
        robot_app.add_log_message(f"Comando gripper RAW: {command}", "action")
        
        if not robot_app.gripper_controller:
            robot_app.add_log_message("Gripper no inicializado", "warning")
            return jsonify({'success': False, 'message': 'Gripper no inicializado'})
        
        # Conectar si no está conectado (con reintentos mejorados)
        if not robot_app.gripper_controller.connected:
            robot_app.add_log_message("Intentando reconectar al gripper...", "info")
            if not robot_app.gripper_controller.connect():
                robot_app.add_log_message("Error: No se pudo conectar al gripper tras múltiples intentos", "error")
                return jsonify({'success': False, 'message': 'No se pudo conectar al gripper tras múltiples intentos'})
            robot_app.add_log_message("Gripper reconectado exitosamente", "info")
        
        # ENVIAR COMANDO DIRECTAMENTE SIN VALIDACIONES NI LIMITACIONES
        # Usar send_raw_command con validate=False para permitir cualquier comando
        success, response = robot_app.gripper_controller.send_raw_command(command, timeout=3.0, validate=False)
        
        if success:
            robot_app.add_log_message(f"Respuesta gripper: {response or 'OK'}", "info")
            # Emitir respuesta por WebSocket para la consola en tiempo real
            socketio.emit('gripper_response', {
                'command': command,
                'response': response or 'Sin respuesta',
                'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3]
            })
            return jsonify({
                'success': True,
                'message': 'Comando enviado exitosamente',
                'response': response or 'Sin respuesta'
            })
        else:
            # Los timeouts/sin respuesta son normales en el gripper
            if any(keyword in str(response).lower() for keyword in ['timeout', 'sin respuesta', 'no se recibió']):
                robot_app.add_log_message(f"Gripper: {response}", "info")
                socketio.emit('gripper_response', {
                    'command': command,
                    'response': response or 'Comando enviado',
                    'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3]
                })
                return jsonify({'success': True, 'message': 'Comando enviado', 'response': response})
            else:
                # Solo errores reales se tratan como errores
                robot_app.add_log_message(f"Error gripper: {response}", "error")
                # Emitir error por WebSocket
                socketio.emit('gripper_response', {
                    'command': command,
                    'response': f"ERROR: {response}",
                    'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
                    'is_error': True
                })
                return jsonify({'success': False, 'message': response or 'Error enviando comando'})
    
    except Exception as e:
        robot_app.add_log_message(f"Error enviando comando gripper: {str(e)}", "error")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/gripper/command/raw', methods=['POST'])
def send_raw_gripper_command():
    """Endpoint adicional para comandos completamente sin procesar"""
    try:
        data = request.get_json()
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({'success': False, 'message': 'Comando vacío'}), 400
        
        robot_app.add_log_message(f"Comando gripper CRUDO: {command}", "action")
        
        if not robot_app.gripper_controller:
            return jsonify({'success': False, 'message': 'Gripper no inicializado'})
        
        if not robot_app.gripper_controller.connected:
            if not robot_app.gripper_controller.connect():
                return jsonify({'success': False, 'message': 'No se pudo conectar al gripper'})
        
        # Enviar comando directamente al socket sin ningún procesamiento
        success = robot_app.gripper_controller.send_command(command)
        
        if success:
            # Esperar respuesta
            time.sleep(0.5)
            received_data = robot_app.gripper_controller.get_received_data()
            
            if received_data:
                latest_response = received_data[-1]['data'] if received_data else 'Sin respuesta'
                robot_app.add_log_message(f"Respuesta gripper RAW: {latest_response}", "info")
                
                # Emitir TODAS las respuestas por WebSocket
                for data_item in received_data:
                    socketio.emit('gripper_response', {
                        'command': command,
                        'response': data_item['data'],
                        'timestamp': data_item.get('timestamp', datetime.now().strftime('%H:%M:%S.%f')[:-3]),
                        'is_raw': True
                    })
                
                return jsonify({
                    'success': True,
                    'message': 'Comando crudo enviado',
                    'response': latest_response,
                    'all_responses': [item['data'] for item in received_data]
                })
            else:
                socketio.emit('gripper_response', {
                    'command': command,
                    'response': 'Comando enviado por socket (sin respuesta inmediata)',
                    'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
                    'is_raw': True
                })
                return jsonify({
                    'success': True,
                    'message': 'Comando enviado (sin respuesta inmediata)',
                    'response': 'Comando enviado por socket'
                })
        else:
            socketio.emit('gripper_response', {
                'command': command,
                'response': 'ERROR: No se pudo enviar comando por socket',
                'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3],
                'is_error': True,
                'is_raw': True
            })
            return jsonify({'success': False, 'message': 'Error enviando comando por socket'})
            
    except Exception as e:
        robot_app.add_log_message(f"Error comando RAW: {str(e)}", "error")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/api/gripper/status')
def get_gripper_status():
    """Obtener estado detallado del gripper"""
    try:
        if robot_app.gripper_controller:
            status = robot_app.gripper_controller.get_gripper_status()
            
            # Agregar información de configuración de conexión
            from robot_modules.gripper_config import get_connection_info
            connection_info = get_connection_info()
            status['connection_info'] = connection_info
            
            return jsonify(status)
        else:
            from robot_modules.gripper_config import get_connection_info
            connection_info = get_connection_info()
            
            return jsonify({
                'connected': False,
                'force': 0.0,
                'position': 0.0,
                'port': None,
                'connection_info': connection_info,
                'message': 'Gripper no inicializado'
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/gripper/connect', methods=['POST'])
def connect_gripper():
    """Conectar/reconectar al gripper con reintentos automáticos"""
    try:
        if not robot_app.gripper_controller:
            return jsonify({'success': False, 'message': 'Gripper no inicializado'})
        
        robot_app.add_log_message("Iniciando conexión al gripper...", "info")
        success = robot_app.gripper_controller.connect()  # Ahora usa reintentos automáticos
        
        if success:
            # Obtener información de configuración para la respuesta
            from robot_modules.gripper_config import get_connection_info
            connection_info = get_connection_info()
            
            robot_app.add_log_message("Gripper conectado exitosamente", "info")
            robot_app.emit_gripper_status()  # Emitir estado actualizado
            
            return jsonify({
                'success': True, 
                'message': 'Gripper conectado',
                'connection_info': connection_info
            })
        else:
            robot_app.add_log_message("Error: No se pudo conectar al gripper tras múltiples intentos", "error")
            robot_app.emit_gripper_status()  # Emitir estado actualizado
            return jsonify({'success': False, 'message': 'No se pudo conectar al gripper tras múltiples intentos'})
    
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
        robot_app.emit_gripper_status()  # Emitir estado actualizado
        return jsonify({'success': True, 'message': 'Gripper desconectado'})
    
    except Exception as e:
        robot_app.add_log_message(f"Error desconectando gripper: {str(e)}", "error")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/gripper/config', methods=['GET'])
def get_gripper_config():
    """Obtener configuración actual del gripper"""
    try:
        from robot_modules.gripper_config import get_current_config, get_connection_info
        
        config = get_current_config()
        conn_info = get_connection_info()
        
        return jsonify({
            'success': True, 
            'config': config,
            'connection_info': conn_info
        })
    
    except Exception as e:
        robot_app.add_log_message(f"Error obteniendo config gripper: {str(e)}", "error")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/gripper/config', methods=['POST'])
def update_gripper_config():
    """Actualizar configuración del gripper"""
    try:
        data = request.get_json()
        host = data.get('host')
        port = data.get('port')
        
        # Validar datos
        if not host or not str(host).strip():
            return jsonify({'success': False, 'message': 'IP/Host requerida'}), 400
        
        if port is not None:
            try:
                port = int(port)
                if port < 1 or port > 65535:
                    return jsonify({'success': False, 'message': 'Puerto debe estar entre 1 y 65535'}), 400
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'Puerto debe ser un número válido'}), 400
        
        # Actualizar configuración
        from robot_modules.gripper_config import update_socket_config
        updated_config = update_socket_config(host=host, port=port)
        
        # Desconectar gripper actual si está conectado
        if robot_app.gripper_controller and robot_app.gripper_controller.connected:
            robot_app.gripper_controller.disconnect()
            robot_app.add_log_message("Gripper desconectado para actualizar configuración", "info")
        
        # Crear nuevo controlador con nueva configuración
        from robot_modules.gripper_config import get_gripper_controller
        robot_app.gripper_controller = get_gripper_controller()
        
        robot_app.add_log_message(f"Configuración gripper actualizada: {host}:{port}", "action")
        robot_app.emit_gripper_status()  # Emitir estado actualizado
        
        return jsonify({
            'success': True, 
            'message': f'Configuración actualizada: {host}:{port}',
            'config': updated_config
        })
    
    except Exception as e:
        robot_app.add_log_message(f"Error actualizando config gripper: {str(e)}", "error")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/control-mode', methods=['POST'])
def toggle_control_mode():
    """Cambiar modo de control (simplificado - Xbox siempre habilitado)"""
    try:
        data = request.get_json()
        mode = data['mode']  # 'coordinates' solamente, Xbox está siempre activo
        
        with robot_app.state_lock:
            old_mode = robot_app.app_state['control_mode']
            robot_app.app_state['control_mode'] = mode
        
        robot_app.add_log_message(f"Modo de interfaz cambiado: {old_mode} -> {mode}", "action")
        
        # El control Xbox funciona en paralelo siempre
        if robot_app.ur5_controller and robot_app.ur5_controller.is_xbox_enabled():
            robot_app.add_log_message("🎮 Control Xbox funcionando en paralelo", "info")
        
        # Emitir estado actualizado por WebSocket
        socketio.emit('status_update', robot_app.app_state)
        
        return jsonify({
            'success': True, 
            'message': f'Modo de interfaz: {mode}',
            'xbox_status': robot_app.ur5_controller.get_xbox_status() if robot_app.ur5_controller else None
        })
    
    except Exception as e:
        robot_app.add_log_message(f"Error cambiando modo de control: {str(e)}", "error")
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/xbox/status')
def get_xbox_status():
    """Obtener estado del Xbox controller (siempre habilitado)"""
    try:
        if robot_app.ur5_controller:
            # Usar la funcionalidad Xbox integrada en UR5Controller
            status = robot_app.ur5_controller.get_xbox_status()
            robot_status = robot_app.ur5_controller.get_robot_status()
            
            # Combinar información para compatibilidad con la interfaz
            combined_status = {
                'connected': status.get('xbox_connected', False),
                'robot_connected': robot_status.get('connected', False),
                'xbox_control_enabled': status.get('xbox_enabled', True),  # Siempre habilitado
                'xbox_running': status.get('xbox_running', False),
                'control_mode': status.get('control_mode', 'joint'),
                'speed_level': status.get('speed_level', 1),
                'speed_percentage': status.get('speed_percent', 30),
                'debug_mode': status.get('debug_mode', False),
                'emergency_stop': robot_status.get('emergency_stop_active', False),
                'movement_active': robot_status.get('movement_active', False),
                'controller_name': 'Integrado en UR5Controller (Siempre Activo)',
                'current_position': robot_status.get('current_position', None)
            }
            
            return jsonify({
                'success': True,
                'status': combined_status
            })
        else:
            return jsonify({
                'success': False,
                'message': 'UR5 Controller no disponible',
                'status': {
                    'connected': False,
                    'robot_connected': False,
                    'xbox_control_enabled': True,  # Conceptualmente siempre habilitado
                    'xbox_running': False,
                    'control_mode': 'joint',
                    'speed_level': 1,
                    'speed_percentage': 30,
                    'debug_mode': False,
                    'emergency_stop': False,
                    'movement_active': False,
                    'controller_name': None,
                    'current_position': None
                }
            })
    except Exception as e:
        logger.error(f"Error obteniendo estado Xbox: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/xbox/check-controllers')
def check_xbox_controllers():
    """Verificar qué controles Xbox están conectados (solo informativo)"""
    try:
        import pygame
        pygame.init()
        pygame.joystick.init()
        
        controller_count = pygame.joystick.get_count()
        controllers = []
        
        if controller_count > 0:
            for i in range(controller_count):
                try:
                    joystick = pygame.joystick.Joystick(i)
                    joystick.init()
                    controllers.append({
                        'index': i,
                        'name': joystick.get_name(),
                        'buttons': joystick.get_numbuttons(),
                        'axes': joystick.get_numaxes(),
                        'hats': joystick.get_numhats()
                    })
                    joystick.quit()
                except Exception as e:
                    logger.warning(f"Error inicializando control {i}: {e}")
                    controllers.append({
                        'index': i,
                        'name': f'Controller {i}',
                        'error': str(e)
                    })
        
        pygame.quit()
        
        return jsonify({
            'success': True,
            'controller_count': controller_count,
            'controllers': controllers,
            'auto_xbox_enabled': robot_app.ur5_controller.is_xbox_enabled() if robot_app.ur5_controller else False,
            'message': f"Se encontraron {controller_count} controles conectados" if controller_count > 0 else "No se encontraron controles conectados"
        })
        
    except Exception as e:
        logger.error(f"Error verificando controles: {e}")
        return jsonify({
            'success': False, 
            'message': str(e),
            'controller_count': 0,
            'controllers': []
        }), 500

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
        photo_path = webcam_controller.capture_image()
        if photo_path:
            robot_app.add_log_message(f"Foto capturada: {photo_path}", "info")
            return jsonify({'success': True, 'photo_url': f'/static/captures/{photo_path}'})
        else:
            return jsonify({'success': False, 'message': 'No se pudo capturar la foto'}), 500
            
    except Exception as e:
        logger.error(f"Error capturando foto: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/webcam/status')
def webcam_status():
    """Obtener estado de la webcam"""
    try:
        status = {
            'is_active': webcam_controller.is_active,
            'camera_index': webcam_controller.camera_index
        }
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
    robot_app.emit_gripper_status()  # Emitir estado inicial del gripper
    robot_app.add_log_message("Cliente WebSocket conectado", "info")

@socketio.on('disconnect')
def handle_disconnect():
    """Manejar desconexión WebSocket"""
    robot_app.add_log_message("Cliente WebSocket desconectado", "info")

@socketio.on('request_status')
def handle_status_request():
    """Solicitud de estado actual"""
    emit('status_update', robot_app.app_state)

@socketio.on('start_webcam')
def handle_start_webcam():
    """Manejar inicio de webcam via WebSocket"""
    try:
        success = webcam_controller.start_camera()
        if success:
            robot_app.add_log_message("Cámara web iniciada", "info")
            emit('webcam_response', {'success': True, 'message': 'Cámara iniciada exitosamente'})
            logger.info("✅ Webcam iniciada via WebSocket")
        else:
            emit('webcam_response', {'success': False, 'error': 'No se pudo iniciar la cámara'})
            logger.error("❌ Error iniciando webcam via WebSocket")
    except Exception as e:
        logger.error(f"Error en start_webcam WebSocket: {e}")
        emit('webcam_response', {'success': False, 'error': str(e)})

@socketio.on('stop_webcam')
def handle_stop_webcam():
    """Manejar detención de webcam via WebSocket"""
    try:
        webcam_controller.stop_camera()
        robot_app.add_log_message("Cámara web detenida", "info")
        emit('webcam_response', {'success': True, 'message': 'Cámara detenida'})
        logger.info("✅ Webcam detenida via WebSocket")
    except Exception as e:
        logger.error(f"Error en stop_webcam WebSocket: {e}")
        emit('webcam_response', {'success': False, 'error': str(e)})

@socketio.on('capture_image')
def handle_capture_image():
    """Manejar captura de imagen via WebSocket"""
    try:
        photo_path = webcam_controller.capture_image()
        if photo_path:
            robot_app.add_log_message(f"Foto capturada: {photo_path}", "info")
            emit('webcam_response', {'success': True, 'filename': photo_path})
            logger.info(f"📸 Foto capturada via WebSocket: {photo_path}")
        else:
            emit('webcam_response', {'success': False, 'error': 'No se pudo capturar la foto'})
            logger.error("❌ Error capturando foto via WebSocket")
    except Exception as e:
        logger.error(f"Error en capture_image WebSocket: {e}")
        emit('webcam_response', {'success': False, 'error': str(e)})

@socketio.on('switch_camera')
def handle_switch_camera(data):
    """Manejar cambio de cámara via WebSocket"""
    try:
        # Simplemente usar la función del controlador
        webcam_controller.switch_camera()
        
        robot_app.add_log_message(f"Cambiado a cámara {webcam_controller.camera_index}", "info")
        emit('webcam_response', {'success': True, 'message': f'Cambiado a cámara {webcam_controller.camera_index}', 'camera_index': webcam_controller.camera_index})
        logger.info(f"🔄 Cambiado a cámara {webcam_controller.camera_index}")
        
    except Exception as e:
        logger.error(f"Error en switch_camera WebSocket: {e}")
        emit('webcam_response', {'success': False, 'error': str(e)})

@socketio.on('get_webcam_status')
def handle_get_webcam_status():
    """Obtener estado de la webcam via WebSocket"""
    try:
        status = {
            'is_active': webcam_controller.is_active,
            'camera_index': webcam_controller.camera_index
        }
        emit('webcam_status', status)
    except Exception as e:
        logger.error(f"Error obteniendo estado webcam: {e}")
        emit('webcam_status', {'error': str(e)})

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