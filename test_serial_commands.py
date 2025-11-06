#!/usr/bin/env python3
"""
Script de prueba específica para comandos serie del gripper
Verifica envío y recepción de comandos paso a paso
"""

import os
import sys
import time
import logging

# Agregar el directorio actual al path para importar los módulos
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from robot_modules.serial_gripper import SerialGripperController

# Configurar logging para ver mensajes detallados
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_send_raw_command(gripper):
    """Probar el método send_raw_command con varios comandos"""
    print("\n🧪 Probando send_raw_command...")
    
    test_commands = [
        "HELP",
        "TEST", 
        "STATUS",
        "PING",
        "INIT"
    ]
    
    results = {}
    
    for cmd in test_commands:
        print(f"\n📤 Enviando comando: '{cmd}'")
        
        try:
            success = gripper.send_raw_command(cmd)
            results[cmd] = success
            
            if success:
                print(f"✅ Comando '{cmd}' enviado exitosamente")
                
                # Intentar leer respuesta inmediatamente
                print(f"📥 Esperando respuesta...")
                response = gripper.recv_response(timeout=2.0)
                
                if response:
                    print(f"📨 Respuesta recibida: '{response}'")
                else:
                    print(f"⚠️ No se recibió respuesta para '{cmd}'")
                    
            else:
                print(f"❌ Error enviando comando '{cmd}'")
                
        except Exception as e:
            print(f"❌ Excepción enviando '{cmd}': {e}")
            results[cmd] = False
        
        # Pausa entre comandos
        time.sleep(0.5)
    
    return results

def test_recv_response_timing(gripper):
    """Probar diferentes timeouts en recv_response"""
    print("\n⏱️ Probando recv_response con diferentes timeouts...")
    
    timeouts = [0.5, 1.0, 2.0, 5.0]
    
    for timeout in timeouts:
        print(f"\n⏰ Probando timeout de {timeout}s")
        
        # Enviar comando
        success = gripper.send_raw_command("HELP")
        if success:
            start_time = time.time()
            response = gripper.recv_response(timeout=timeout)
            elapsed = time.time() - start_time
            
            print(f"⏱️ Tiempo transcurrido: {elapsed:.2f}s")
            if response:
                print(f"📨 Respuesta: '{response[:50]}...'")
            else:
                print("⚠️ Sin respuesta")
        else:
            print("❌ Error enviando comando para prueba de timeout")

def test_connection_method(gripper):
    """Probar específicamente el método test_connection"""
    print("\n🔌 Probando método test_connection()...")
    
    try:
        result = gripper.test_connection()
        
        if result:
            print("✅ test_connection() retornó True")
        else:
            print("❌ test_connection() retornó False")
            
        return result
        
    except Exception as e:
        print(f"❌ Excepción en test_connection(): {e}")
        return False

def test_gripper_specific_commands(gripper):
    """Probar comandos específicos del gripper"""
    print("\n🤖 Probando comandos específicos del gripper...")
    
    # Probar comando de apertura
    print("\n🔓 Probando apertura del gripper...")
    try:
        result = gripper.open_gripper(force=2.0)
        print(f"Resultado open_gripper(): {result}")
    except Exception as e:
        print(f"Error en open_gripper(): {e}")
    
    time.sleep(1)
    
    # Probar comando de cierre
    print("\n🔒 Probando cierre del gripper...")
    try:
        result = gripper.close_gripper(force=5.0)
        print(f"Resultado close_gripper(): {result}")
    except Exception as e:
        print(f"Error en close_gripper(): {e}")
    
    time.sleep(1)
    
    # Probar comando personalizado
    print("\n⚙️ Probando comando personalizado...")
    try:
        result, message = gripper.send_custom_command("STATUS")
        print(f"Resultado send_custom_command(): {result}")
        print(f"Mensaje: {message}")
    except Exception as e:
        print(f"Error en send_custom_command(): {e}")

def test_buffer_management(gripper):
    """Probar manejo de buffers y múltiples comandos"""
    print("\n📊 Probando manejo de buffers...")
    
    # Enviar múltiples comandos rápidamente
    commands = ["PING", "STATUS", "HELP"]
    
    print("📤 Enviando múltiples comandos rápidamente...")
    for cmd in commands:
        gripper.send_raw_command(cmd)
        time.sleep(0.1)  # Pausa muy corta
    
    # Intentar leer todas las respuestas
    print("📥 Leyendo respuestas...")
    for i in range(len(commands)):
        response = gripper.recv_response(timeout=1.0)
        if response:
            print(f"📨 Respuesta {i+1}: '{response}'")
        else:
            print(f"⚠️ Sin respuesta {i+1}")

def check_serial_connection_health(gripper):
    """Verificar salud de la conexión serie"""
    print("\n🏥 Verificando salud de la conexión...")
    
    # Verificar estado básico
    status = gripper.get_gripper_status()
    print(f"📊 Estado del gripper:")
    print(f"  - Conectado: {status['connected']}")
    print(f"  - Puerto: {status['port']}")
    print(f"  - Baudrate: {status['baudrate']}")
    
    # Verificar salud de conexión
    if hasattr(gripper, 'check_connection_health'):
        health = gripper.check_connection_health()
        print(f"  - Salud de conexión: {health}")
    
    # Verificar si el puerto serie está realmente disponible
    if gripper.serial_conn and gripper.connected:
        print(f"  - Puerto serie abierto: {gripper.serial_conn.is_open}")
        print(f"  - Bytes esperando: {gripper.serial_conn.in_waiting}")
        print(f"  - Timeout configurado: {gripper.serial_conn.timeout}")

def main():
    """Función principal de prueba"""
    print("🚀 Prueba Específica de Comandos Serie del Gripper")
    print("=" * 60)
    
    # Crear controlador con debug habilitado
    print("🔧 Creando controlador con debug habilitado...")
    gripper = SerialGripperController(debug=True)
    
    try:
        # Verificar salud inicial
        check_serial_connection_health(gripper)
        
        # Intentar conectar
        print("\n🔌 Intentando conectar...")
        connected = gripper.connect()
        
        if connected:
            print("✅ Conexión establecida exitosamente")
            
            # Verificar salud después de conectar
            check_serial_connection_health(gripper)
            
            # Ejecutar pruebas específicas
            test_send_raw_command(gripper)
            test_recv_response_timing(gripper)
            test_connection_method(gripper)
            test_buffer_management(gripper)
            test_gripper_specific_commands(gripper)
            
        else:
            print("❌ No se pudo establecer conexión")
            print("💡 Verificar:")
            print("  - Que el dispositivo esté conectado")
            print("  - Permisos del puerto serie")
            print("  - Que no esté siendo usado por otra aplicación")
            
            # Mostrar información de puertos disponibles
            import glob
            usb_ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
            if usb_ports:
                print(f"📍 Puertos USB detectados: {usb_ports}")
            else:
                print("⚠️ No se detectaron puertos USB")
        
    except KeyboardInterrupt:
        print("\n⚠️ Prueba interrumpida por usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Limpiar conexión
        print("\n🔒 Cerrando conexión...")
        try:
            gripper.disconnect()
        except:
            pass
    
    print("\n🎉 Prueba completada")

if __name__ == "__main__":
    main()