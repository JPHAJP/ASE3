#!/usr/bin/env python3
"""
Test del controlador mejorado con reintentos
"""

from robot_modules.gripper_config import get_gripper_controller
import time

print("=== TEST CONTROLADOR MEJORADO ===")

# Test 1: Crear controlador y conectar
print("\n1. Creando controlador...")
controller = get_gripper_controller()
print(f"Controlador: {controller.host}:{controller.port}")

print("\n2. Probando conexión con reintentos...")
success = controller.connect()
print(f"Resultado conexión: {success}")

if success:
    print("✅ Conexión exitosa!")
    
    # Test 2: Enviar comandos
    print("\n3. Enviando comandos...")
    
    commands = ["HELP", "DO LIGHT TOGGLE", "GET GRIP DIST"]
    for cmd in commands:
        print(f"\nEnviando: {cmd}")
        result = controller.send_raw_command(cmd, timeout=2.0)
        print(f"Resultado: {result}")
        time.sleep(0.5)
    
    # Test 3: Desconectar y reconectar
    print("\n4. Test reconexión...")
    controller.disconnect()
    time.sleep(2.0)
    
    success2 = controller.connect()
    print(f"Reconexión resultado: {success2}")
    
    if success2:
        result = controller.send_raw_command("DO LIGHT TOGGLE", timeout=2.0)
        print(f"Comando post-reconexión: {result}")
        controller.disconnect()
    
else:
    print("❌ Conexión inicial falló")

print("\n=== FIN TEST ===")