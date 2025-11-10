"""
Configuración del controlador del gripper
Permite cambiar fácilmente entre socket TCP y puerto serial

IMPORTANTE: Los timeouts/sin respuesta son comportamiento NORMAL del gripper uSENSE.
No todos los comandos generan respuestas, y esto no debe considerarse un error.
El sistema ahora maneja estos casos silenciosamente.
"""

import os

# ==================== CONFIGURACIÓN DEL GRIPPER ====================

# Tipo de conexión: 'socket' o 'serial'
GRIPPER_CONNECTION_TYPE = 'socket'

# Configuración para conexión socket TCP
SOCKET_CONFIG = {
    'host': '192.168.68.125',  # IP del ESP32 gripper
    'port': 23,                # Puerto TCP (típicamente 23 para telnet)
    'timeout': 5.0,            # Timeout de conexión en segundos
    'debug': True              # Habilitar logging detallado
}

# Configuración para conexión serial (legacy)
SERIAL_CONFIG = {
    'port': '/dev/ttyACM0',    # Puerto serie, None para auto-detectar
    'baudrate': 115200,        # Velocidad de comunicación
    'timeout': 5.0,            # Timeout de conexión
    'debug': True              # Habilitar logging detallado
}

# ==================== FUNCIÓN HELPER ====================

def get_gripper_controller():
    """
    Retorna la instancia correcta del controlador según la configuración
    
    Returns:
        GripperController: Instancia del controlador configurado
    """
    if GRIPPER_CONNECTION_TYPE == 'socket':
        from robot_modules.socket_gripper import SocketGripperController
        return SocketGripperController(
            host=SOCKET_CONFIG['host'],
            port=SOCKET_CONFIG['port'],
            debug=SOCKET_CONFIG['debug']
        )
    elif GRIPPER_CONNECTION_TYPE == 'serial':
        from robot_modules.serial_gripper import SerialGripperController
        return SerialGripperController(
            port=SERIAL_CONFIG['port'],
            baudrate=SERIAL_CONFIG['baudrate'],
            debug=SERIAL_CONFIG['debug']
        )
    else:
        raise ValueError(f"Tipo de conexión no soportado: {GRIPPER_CONNECTION_TYPE}")

def update_socket_config(host=None, port=None):
    """
    Actualiza la configuración del socket TCP dinámicamente
    
    Args:
        host (str, optional): Nueva dirección IP del gripper
        port (int, optional): Nuevo puerto TCP del gripper
    
    Returns:
        dict: Configuración actualizada
    """
    global SOCKET_CONFIG
    
    if host is not None:
        SOCKET_CONFIG['host'] = host
    
    if port is not None:
        SOCKET_CONFIG['port'] = int(port)
    
    return SOCKET_CONFIG.copy()

def get_current_config():
    """
    Obtiene la configuración actual completa
    
    Returns:
        dict: Configuración completa actual
    """
    return {
        'connection_type': GRIPPER_CONNECTION_TYPE,
        'socket_config': SOCKET_CONFIG.copy(),
        'serial_config': SERIAL_CONFIG.copy()
    }

def get_connection_info():
    """
    Retorna información sobre la configuración actual
    
    Returns:
        dict: Información de la configuración
    """
    if GRIPPER_CONNECTION_TYPE == 'socket':
        return {
            'type': 'socket',
            'host': SOCKET_CONFIG['host'],
            'port': SOCKET_CONFIG['port'],
            'description': f"Socket TCP {SOCKET_CONFIG['host']}:{SOCKET_CONFIG['port']}"
        }
    elif GRIPPER_CONNECTION_TYPE == 'serial':
        return {
            'type': 'serial',
            'port': SERIAL_CONFIG['port'],
            'baudrate': SERIAL_CONFIG['baudrate'],
            'description': f"Puerto serie {SERIAL_CONFIG['port']} @ {SERIAL_CONFIG['baudrate']}"
        }
    else:
        return {
            'type': 'unknown',
            'description': 'Configuración no válida'
        }