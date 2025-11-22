#!/usr/bin/env python3
"""
Script de prueba para el controlador UR5 con comunicación por socket y control de velocidades
"""

import time
import logging
import numpy as np
from robot_modules.ur5_controller import UR5WebController

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_ur5_socket_controller():
    """Probar el controlador UR5 con socket"""
    print("🧪 === PRUEBA DEL CONTROLADOR UR5 CON SOCKET Y VELOCIDADES ===")
    
    try:
        # Crear controlador
        print("📡 Creando controlador con comunicación por socket...")
        controller = UR5WebController(robot_ip="192.168.0.101", robot_port=30002)
        
        # Verificar estado inicial
        print(f"🔗 Conectado: {controller.is_connected()}")
        print(f"🎮 Xbox habilitado: {controller.xbox_enabled}")
        print(f"⚡ Control de velocidad activo: {controller.velocity_active}")
        print(f"🔄 Modo de control: {controller.control_mode}")
        print(f"📊 Nivel de velocidad: {controller.current_speed_level + 1}/5")
        
        # Mostrar información de velocidades
        print(f"🚀 Velocidades máximas lineales: {controller.max_linear_velocity}")
        print(f"🔧 Velocidades máximas articulares: {controller.max_joint_velocity}")
        
        # Probar comandos básicos
        print("\n🧪 Probando comandos básicos por socket...")
        
        # Comando de prueba simple
        success = controller.send_command("# Test command from Python")
        print(f"📤 Comando de prueba enviado: {'✅' if success else '❌'}")
        
        # Probar comando de parada
        success = controller.send_stopl()
        print(f"⏹️ Comando stopl enviado: {'✅' if success else '❌'}")
        
        success = controller.send_stopj()
        print(f"⏹️ Comando stopj enviado: {'✅' if success else '❌'}")
        
        # Mostrar estado del robot
        status = controller.get_robot_status()
        print(f"\n📊 Estado del robot:")
        print(f"  - Conexión: {'OK' if status['connected'] else 'ERROR'}")
        print(f"  - Puede controlar: {'SÍ' if status['can_control'] else 'NO'}")
        print(f"  - Socket lectura: {'CONECTADO' if status.get('read_socket_connected') else 'DESCONECTADO'}")
        print(f"  - Lectura posiciones: {'ACTIVA' if status.get('position_reading') else 'INACTIVA'}")
        print(f"  - Parada emergencia: {'ACTIVA' if status['emergency_stop_active'] else 'INACTIVA'}")
        print(f"  - Movimiento activo: {'SÍ' if status['movement_active'] else 'NO'}")
        print(f"  - Modo Xbox: {status.get('control_mode', 'N/A')}")
        
        # Mostrar posiciones actuales
        if status.get('read_socket_connected'):
            print(f"\n📍 Posiciones actuales del robot:")
            current_pose = controller.get_current_tcp_pose()
            print(f"  TCP: X={current_pose[0]:.3f}m, Y={current_pose[1]:.3f}m, Z={current_pose[2]:.3f}m")
            print(f"       RX={np.degrees(current_pose[3]):.1f}°, RY={np.degrees(current_pose[4]):.1f}°, RZ={np.degrees(current_pose[5]):.1f}°")
            
            joint_positions = controller.get_current_joint_positions()
            print(f"  Joints: ", end="")
            for i, joint in enumerate(joint_positions):
                print(f"J{i}={np.degrees(joint):.1f}° ", end="")
            print()
        else:
            print(f"\n⚠️ Socket de lectura no disponible - usando valores por defecto")
        
        # Información de Xbox
        if controller.joystick:
            print(f"\n🎮 Control Xbox detectado: {controller.joystick.get_name()}")
            print("🎯 Controles disponibles:")
            print("  - A: Cambiar modo (linear/joint)")
            print("  - B: Parada de emergencia")
            print("  - X: Ir a posición Home")
            print("  - Y: Detener movimientos")
            print("  - LB/RB: Cambiar velocidad")
            print("  - Start: Mostrar estado")
            print("  - Menu: Toggle debug")
            print("  - Joysticks + D-pad: Control de velocidades continuas")
        else:
            print("⚠️ No se detectó control Xbox")
        
        print(f"\n✅ Controlador configurado exitosamente!")
        print(f"📡 Comunicación: Socket en puerto {controller.robot_port}")
        print(f"⚡ Control de velocidades: {'ACTIVO' if controller.velocity_active else 'INACTIVO'}")
        
        # Test de velocidades (sin enviar al robot real)
        print(f"\n🧪 Probando cálculo de velocidades...")
        
        # Simular entrada de joystick
        test_velocities_linear = controller.calculate_linear_velocities(
            0.5, 0.3, -0.2, 0.8, (1, 0), lambda x: x**2 * (1 if x >= 0 else -1)
        )
        
        test_velocities_joint = controller.calculate_joint_velocities(
            0.5, 0.3, -0.2, 0.8, (1, 0), lambda x: x**2 * (1 if x >= 0 else -1)
        )
        
        print(f"📐 Velocidades lineales calculadas: {[f'{v:.4f}' for v in test_velocities_linear]}")
        print(f"🔧 Velocidades articulares calculadas: {[f'{v:.4f}' for v in test_velocities_joint]}")
        
        print(f"\n🎉 ¡Todas las pruebas completadas exitosamente!")
        
        return controller
        
    except Exception as e:
        print(f"❌ Error en prueba: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Función principal"""
    controller = test_ur5_socket_controller()
    
    if controller:
        print(f"\n⏰ Controlador creado. Presiona Ctrl+C para salir...")
        print(f"📡 Monitoreando posiciones cada 2 segundos...")
        
        try:
            # Mantener activo para pruebas con Xbox
            while True:
                time.sleep(2)
                
                # Mostrar posiciones actualizadas cada 2 segundos
                if controller.read_socket and controller.position_reading:
                    current_pose = controller.get_current_tcp_pose()
                    joint_positions = controller.get_current_joint_positions()
                    
                    print(f"\n📍 Posición actual:")
                    print(f"  TCP: X={current_pose[0]:.3f}m, Y={current_pose[1]:.3f}m, Z={current_pose[2]:.3f}m")
                    print(f"  Joints: ", end="")
                    for i, joint in enumerate(joint_positions):
                        print(f"J{i}={np.degrees(joint):.1f}° ", end="")
                    print()
                    
        except KeyboardInterrupt:
            print(f"\n👋 Cerrando controlador...")
            controller.disconnect()
            print("✅ Controlador cerrado correctamente")

if __name__ == "__main__":
    main()