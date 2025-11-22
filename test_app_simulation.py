#!/usr/bin/env python3
"""
Test para simular el comportamiento de app.py
"""

import time
from robot_modules.gripper_config import get_gripper_controller

print("=== TEST APP.PY SIMULATION ===")

# 1. Crear controlador (como hace app.py en __init__)
print("1. Creando controlador inicial...")
controller1 = get_gripper_controller()
print(f"Controller creado: {controller1.host}:{controller1.port}")

# 2. Intentar conectar (como hace app.py cuando envías comando)
print("\n2. Conectando controlador...")
success = controller1.connect()
print(f"Conexión resultado: {success}")
print(f"Estado conectado: {controller1.connected}")

if success:
    print("✅ Controlador conectado exitosamente")
    
    # 3. Enviar un comando
    print("\n3. Enviando comando...")
    result = controller1.send_raw_command("HELP", timeout=2.0)
    print(f"Comando resultado: {result}")
    
    # 4. Simular crear otro controlador (como cuando cambias config)
    print("\n4. Desconectando y creando nuevo controlador...")
    controller1.disconnect()
    time.sleep(1)  # Esperar un poco
    
    controller2 = get_gripper_controller()
    print(f"Nuevo controller: {controller2.host}:{controller2.port}")
    
    success2 = controller2.connect()
    print(f"Segunda conexión resultado: {success2}")
    
    if success2:
        print("✅ Segunda conexión exitosa")
        result2 = controller2.send_raw_command("DO LIGHT TOGGLE", timeout=2.0)
        print(f"Segundo comando resultado: {result2}")
        controller2.disconnect()
    else:
        print("❌ Segunda conexión falló")
        
else:
    print("❌ Conexión inicial falló")

print("\n=== FIN TEST ===")