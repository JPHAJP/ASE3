#!/usr/bin/env python3
"""
Script para debuggear el problema de conexión del gripper
"""

print("=== DEBUGGING GRIPPER CONNECTION ===")

# 1. Verificar configuración
print("\n1. Verificando configuración...")
from robot_modules.gripper_config import get_current_config, get_connection_info
config = get_current_config()
conn_info = get_connection_info()
print(f"Config: {config}")
print(f"Connection Info: {conn_info}")

# 2. Crear controlador y verificar parámetros
print("\n2. Creando controlador...")
from robot_modules.gripper_config import get_gripper_controller
controller = get_gripper_controller()
print(f"Controller host: {controller.host}")
print(f"Controller port: {controller.port}")
print(f"Controller debug: {controller.debug}")

# 3. Probar conexión directa
print("\n3. Probando conexión directa...")
try:
    success = controller.connect()
    print(f"Conexión resultado: {success}")
    print(f"Estado conectado: {controller.connected}")
    
    if success:
        print("✅ Conexión exitosa!")
        
        # Probar envío de comando
        print("\n4. Probando comando...")
        result = controller.send_raw_command("HELP", timeout=3.0)
        print(f"Comando resultado: {result}")
        
        # Desconectar
        controller.disconnect()
    else:
        print("❌ Conexión falló")
        
except Exception as e:
    print(f"❌ Error en conexión: {e}")
    import traceback
    traceback.print_exc()

# 4. Comparar con socket directo
print("\n5. Probando socket directo...")
import socket
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    sock.connect(('192.168.0.100', 23))
    print("✅ Socket directo funciona!")
    sock.close()
except Exception as e:
    print(f"❌ Socket directo falló: {e}")

print("\n=== FIN DEBUG ===")