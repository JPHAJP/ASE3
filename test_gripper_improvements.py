#!/usr/bin/env python3
"""
Script para probar las mejoras específicas del módulo serial_gripper
Prueba validación de comandos, reintentos y nuevas funcionalidades
"""

import os
import sys
import time
import logging

# Agregar el directorio actual al path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from robot_modules.serial_gripper import SerialGripperController

# Configurar logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_command_validation(gripper):
    """Probar la validación de comandos"""
    print("\n🔍 Probando validación de comandos...")
    
    # Comandos válidos
    valid_commands = [
        "HELP",
        "GET GRIP MMpos", 
        "MOVE GRIP HOME",
        "CONFIG SAVE",
        "CONFIG SHOW"
    ]
    
    # Comandos inválidos
    invalid_commands = [
        "INVALID_COMMAND",
        "TEST",
        "RANDOM_STUFF",
        ""
    ]
    
    print("\n✅ Probando comandos válidos:")
    for cmd in valid_commands:
        is_valid, msg = gripper.validate_usense_command(cmd)
        print(f"  '{cmd}' -> {is_valid} ({msg})")
    
    print("\n❌ Probando comandos inválidos:")
    for cmd in invalid_commands:
        is_valid, msg = gripper.validate_usense_command(cmd)
        print(f"  '{cmd}' -> {is_valid} ({msg})")

def test_improved_recv_response(gripper):
    """Probar el recv_response mejorado con múltiples líneas"""
    print("\n📥 Probando recv_response mejorado...")
    
    if not gripper.connected:
        if not gripper.connect():
            print("❌ No se pudo conectar")
            return
    
    print("\n📋 Solicitando HELP completo (múltiples líneas):")
    success = gripper.send_raw_command("HELP", validate=False)
    
    if success:
        # Leer respuesta completa (múltiples líneas)
        full_response = gripper.recv_response(timeout=3.0, max_lines=50)
        
        if full_response:
            lines = full_response.split('\n')
            print(f"✅ Recibidas {len(lines)} líneas:")
            for i, line in enumerate(lines[:10]):  # Mostrar solo las primeras 10
                print(f"  {i+1}: {line}")
            if len(lines) > 10:
                print(f"  ... y {len(lines) - 10} líneas más")
        else:
            print("⚠️ No se recibió respuesta completa")

def test_command_with_retry(gripper):
    """Probar envío de comandos con reintentos"""
    print("\n🔄 Probando comandos con reintentos...")
    
    if not gripper.connected:
        if not gripper.connect():
            print("❌ No se pudo conectar")
            return
    
    # Probar comando válido
    print("\n✅ Comando válido con reintentos:")
    success, response = gripper.send_command_with_retry("GET GRIP MMpos")
    print(f"Resultado: {success}")
    print(f"Respuesta: {response}")
    
    # Probar comando que podría fallar
    print("\n⚠️ Comando con posible fallo:")
    success, response = gripper.send_command_with_retry("CONFIG SHOW", max_retries=1)
    print(f"Resultado: {success}")
    print(f"Respuesta: {response}")

def test_usense_specific_commands(gripper):
    """Probar comandos específicos del uSENSEGRIP"""
    print("\n🤖 Probando comandos específicos del uSENSEGRIP...")
    
    if not gripper.connected:
        if not gripper.connect():
            print("❌ No se pudo conectar")
            return
    
    # Probar obtener posición
    print("\n📍 Obteniendo posición:")
    success, response = gripper.usense_get_position()
    print(f"Resultado: {success}")
    print(f"Respuesta: {response}")
    
    time.sleep(0.5)
    
    # Probar obtener posición del stepper
    print("\n🔧 Obteniendo posición del stepper:")
    success, response = gripper.usense_get_stepper_position()
    print(f"Resultado: {success}")
    print(f"Respuesta: {response}")
    
    time.sleep(0.5)
    
    # Probar configuración del motor
    print("\n⚙️ Configurando modo de motor (Normal):")
    success, response = gripper.usense_config_motor_mode(0)
    print(f"Resultado: {success}")
    print(f"Respuesta: {response}")

def test_connection_health_monitoring(gripper):
    """Probar monitoreo de salud de la conexión"""
    print("\n🏥 Probando monitoreo de salud de conexión...")
    
    if not gripper.connected:
        if not gripper.connect():
            print("❌ No se pudo conectar")
            return
    
    # Verificar salud varias veces
    for i in range(3):
        health = gripper.check_connection_health()
        print(f"Verificación {i+1}: {'✅ Saludable' if health else '❌ Problema'}")
        time.sleep(0.5)
    
    # Probar custom command mejorado
    print("\n📤 Probando send_custom_command mejorado:")
    success, response = gripper.send_custom_command("GET GRIP MMpos", use_retry=True)
    print(f"Resultado: {success}")
    print(f"Respuesta: {response}")

def main():
    """Función principal de prueba"""
    print("🚀 Prueba de Mejoras del Serial Gripper Controller")
    print("=" * 60)
    
    # Crear controlador
    gripper = SerialGripperController(debug=True)
    
    try:
        # Ejecutar todas las pruebas
        test_command_validation(gripper)
        
        # Las siguientes pruebas requieren conexión
        if gripper.connect():
            print("\n✅ Conectado exitosamente, ejecutando pruebas avanzadas...")
            
            test_improved_recv_response(gripper)
            test_command_with_retry(gripper)
            test_usense_specific_commands(gripper)
            test_connection_health_monitoring(gripper)
            
        else:
            print("\n⚠️ No se pudo conectar - Ejecutando solo pruebas sin conexión")
        
    except KeyboardInterrupt:
        print("\n⚠️ Prueba interrumpida por usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Limpiar
        try:
            gripper.disconnect()
        except:
            pass
    
    print("\n🎉 Prueba de mejoras completada")

if __name__ == "__main__":
    main()