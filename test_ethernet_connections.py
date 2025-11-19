#!/usr/bin/env python3
"""
Script para verificar las conexiones ethernet del robot y gripper
"""
import socket
import subprocess
import sys
import time
from robot_modules.gripper_config import SOCKET_CONFIG, get_connection_info

def test_ping(host, description):
    """Probar conectividad básica con ping"""
    print(f"\n🔍 Probando conectividad con {description} ({host})...")
    try:
        result = subprocess.run(['ping', '-c', '3', '-W', '2', host], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ {description} responde al ping")
            return True
        else:
            print(f"❌ {description} NO responde al ping")
            return False
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout al hacer ping a {description}")
        return False
    except Exception as e:
        print(f"❌ Error al hacer ping a {description}: {e}")
        return False

def test_tcp_connection(host, port, description, timeout=5):
    """Probar conexión TCP"""
    print(f"\n🔌 Probando conexión TCP con {description} ({host}:{port})...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ Conexión TCP exitosa con {description}")
            return True
        else:
            print(f"❌ No se pudo conectar por TCP a {description} (código: {result})")
            return False
    except Exception as e:
        print(f"❌ Error al conectar por TCP a {description}: {e}")
        return False

def check_network_interface():
    """Verificar la interfaz de red ethernet"""
    print("\n🌐 Verificando configuración de red ethernet...")
    try:
        # Verificar IP de la interfaz ethernet
        result = subprocess.run(['ip', 'addr', 'show', 'enx68da73a62e01'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Interfaz ethernet detectada:")
            lines = result.stdout.split('\n')
            for line in lines:
                if 'inet ' in line and '192.168.0' in line:
                    print(f"   📍 {line.strip()}")
            return True
        else:
            print("❌ No se encontró la interfaz ethernet")
            return False
    except Exception as e:
        print(f"❌ Error al verificar interfaz ethernet: {e}")
        return False

def test_gripper_connection():
    """Probar conexión específica al gripper"""
    gripper_config = get_connection_info()
    print(f"\n🤖 Probando conexión al gripper...")
    print(f"   Configuración: {gripper_config['description']}")
    
    if gripper_config['type'] == 'socket':
        host = gripper_config['host']
        port = gripper_config['port']
        
        # Primero ping
        ping_ok = test_ping(host, "Gripper")
        
        # Luego TCP
        tcp_ok = test_tcp_connection(host, port, "Gripper", timeout=3)
        
        return ping_ok and tcp_ok
    else:
        print("⚠️  Gripper configurado en modo serial, no se puede probar ethernet")
        return False

def main():
    """Función principal"""
    print("="*60)
    print("🔧 VERIFICACIÓN DE CONEXIONES ETHERNET")
    print("   Robot UR5 y Gripper uSENSE")
    print("="*60)
    
    # 1. Verificar interfaz de red
    interface_ok = check_network_interface()
    
    # 2. Definir IPs a probar
    devices = {
        'PC (esta máquina)': '192.168.0.104',
        'Robot UR5': '192.168.0.101', 
        'Gripper uSENSE': '192.168.0.102'
    }
    
    # 3. Probar conectividad básica
    connectivity_results = {}
    for device, ip in devices.items():
        if device == 'PC (esta máquina)':
            print(f"\n📍 {device}: {ip} (local)")
            connectivity_results[device] = True
        else:
            connectivity_results[device] = test_ping(ip, device)
    
    # 4. Probar conexión específica del gripper
    gripper_ok = test_gripper_connection()
    
    # 5. Probar puerto típico del robot UR5 (puerto 30002 para RTDE)
    robot_tcp_ok = test_tcp_connection('192.168.0.101', 30002, 'Robot UR5 (RTDE)', timeout=3)
    
    # 6. Mostrar resumen
    print("\n" + "="*60)
    print("📊 RESUMEN DE RESULTADOS")
    print("="*60)
    
    print(f"🌐 Interfaz ethernet:     {'✅ OK' if interface_ok else '❌ ERROR'}")
    
    for device, result in connectivity_results.items():
        status = '✅ OK' if result else '❌ ERROR'
        print(f"🔍 {device:<20} {status}")
    
    print(f"🤖 Gripper TCP:          {'✅ OK' if gripper_ok else '❌ ERROR'}")
    print(f"🦾 Robot UR5 TCP:        {'✅ OK' if robot_tcp_ok else '❌ ERROR'}")
    
    # 7. Recomendaciones
    print("\n" + "="*60)
    print("💡 RECOMENDACIONES")
    print("="*60)
    
    if not interface_ok:
        print("❗ Problema con la interfaz ethernet:")
        print("   - Verifica que el cable ethernet esté conectado")
        print("   - Verifica que la interfaz tenga IP 192.168.0.104")
    
    if not connectivity_results.get('Robot UR5', False):
        print("❗ Robot UR5 no responde:")
        print("   - Verifica que el robot esté encendido")
        print("   - Configura la IP del robot a 192.168.0.101")
        print("   - Verifica la configuración de red del robot")
    
    if not gripper_ok:
        print("❗ Gripper no responde:")
        print("   - Verifica que el gripper esté encendido")
        print("   - Configura la IP del gripper a 192.168.0.102")
        print("   - Verifica que el puerto 23 esté disponible")
    
    if not robot_tcp_ok:
        print("❗ Puerto RTDE del robot no disponible:")
        print("   - Habilita RTDE en la configuración del robot")
        print("   - Verifica que el puerto 30002 esté abierto")
    
    # 8. Estado general
    all_ok = (interface_ok and 
              connectivity_results.get('Robot UR5', False) and 
              gripper_ok and robot_tcp_ok)
    
    print(f"\n🎯 Estado general: {'🟢 LISTO' if all_ok else '🔴 REQUIERE ATENCIÓN'}")
    
    if all_ok:
        print("✅ Todas las conexiones ethernet están funcionando correctamente!")
    else:
        print("⚠️  Algunas conexiones requieren configuración adicional.")

if __name__ == "__main__":
    main()