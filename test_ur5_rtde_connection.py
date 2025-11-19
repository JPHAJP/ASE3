#!/usr/bin/env python3
"""
Test de conexión RTDE para UR5e
Verifica que la conexión RTDE funcione correctamente con la IP 192.168.0.101
"""

import sys
import os

# Agregar directorio del módulo
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from robot_modules.ur5_controller import UR5WebController
import time
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_ur5_connection():
    """Test de conexión con el UR5e"""
    
    print("=" * 60)
    print("🤖 TEST DE CONEXIÓN UR5e CON RTDE")
    print("=" * 60)
    print()
    
    # Crear controlador
    print("📍 Creando controlador para IP: 192.168.0.101")
    controller = UR5WebController("192.168.0.101")
    
    print()
    print("🔌 Estado de conexión:")
    is_connected = controller.is_connected()
    print(f"   {'✅ CONECTADO' if is_connected else '❌ DESCONECTADO'}")
    
    if is_connected:
        print()
        print("📊 Información del robot:")
        try:
            # Obtener información básica
            joints = controller.get_current_joint_positions()
            tcp_pose = controller.get_current_tcp_pose()
            status = controller.get_robot_status()
            
            print(f"   🦾 Modo del robot: {status.get('robot_mode', 'N/A')}")
            print(f"   🛡️  Modo de seguridad: {status.get('safety_mode', 'N/A')}")
            print(f"   📍 Posición TCP: {tcp_pose[:3]}")  # Solo XYZ
            print(f"   🔄 Articulación 1: {joints[0]:.3f} rad ({joints[0]*57.3:.1f}°)")
            
            # Información adicional disponible
            if 'joint_temperatures' in status:
                temps = status['joint_temperatures']
                print(f"   🌡️  Temperatura art. 1: {temps[0]:.1f}°C")
            
            if 'runtime_state' in status:
                print(f"   ⚙️  Estado runtime: {status['runtime_state']}")
            
        except Exception as e:
            print(f"   ⚠️  Error obteniendo información: {e}")
    
    else:
        print()
        print("ℹ️  El robot no está conectado. Posibles causas:")
        print("   • Robot no encendido")
        print("   • IP incorrecta (verificar que sea 192.168.0.101)")
        print("   • Red ethernet no configurada")
        print("   • Firewall bloqueando conexión")
    
    print()
    print("🧪 Test de comando básico:")
    try:
        status = controller.get_robot_status()
        print(f"   📊 Estado obtenido: {status['mode']}")
        print(f"   🎯 Posición actual: {status['current_position'][:3]} mm")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()
    print("=" * 60)
    print("✅ Test completado")
    print("=" * 60)

if __name__ == "__main__":
    test_ur5_connection()