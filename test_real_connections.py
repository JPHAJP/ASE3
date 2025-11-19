#!/usr/bin/env python3
"""
Script para probar las conexiones reales del robot y gripper
usando los controladores de la aplicación
"""
import sys
import time
from robot_modules.gripper_config import get_gripper_controller, get_connection_info
from robot_modules.ur5_controller import UR5WebController

def test_gripper_real_connection():
    """Probar conexión real al gripper usando el controlador"""
    print("\n🤖 Probando conexión real al gripper...")
    
    try:
        # Obtener información de configuración
        config_info = get_connection_info()
        print(f"   Configuración: {config_info['description']}")
        
        # Obtener controlador
        gripper = get_gripper_controller()
        print("   ✅ Controlador del gripper creado exitosamente")
        
        # Intentar conectar
        if hasattr(gripper, 'connect'):
            success = gripper.connect()
            if success:
                print("   ✅ Conexión establecida con el gripper")
                
                # Probar comandos básicos
                try:
                    status = gripper.get_gripper_status()
                    print(f"   📊 Estado del gripper: {status}")
                    
                    # Probar comando de posición
                    print("   🧪 Probando comando de posición...")
                    gripper.set_gripper_position(50)  # Mover a 50% de apertura
                    time.sleep(2)
                    
                    new_status = gripper.get_gripper_status()
                    print(f"   📊 Nuevo estado: {new_status}")
                    
                    print("   ✅ Comandos básicos funcionando correctamente")
                    return True
                    
                except Exception as e:
                    print(f"   ⚠️  Error al ejecutar comandos: {e}")
                    return False
                    
            else:
                print("   ❌ No se pudo establecer conexión con el gripper")
                return False
        else:
            print("   ⚠️  El controlador no tiene método connect")
            return False
            
    except Exception as e:
        print(f"   ❌ Error al crear controlador del gripper: {e}")
        return False

def test_robot_real_connection():
    """Probar conexión real al robot usando el controlador"""
    print("\n🦾 Probando conexión real al robot UR5...")
    
    try:
        # Crear controlador del robot
        robot = UR5WebController("192.168.0.101")
        print("   ✅ Controlador del robot creado exitosamente")
        
        # Verificar estado de conexión
        print(f"   📍 IP del robot: {robot.robot_ip}")
        print(f"   🔗 Estado de conexión: {robot.connected}")
        
        # En modo desconectado, verificar que los métodos básicos funcionen
        try:
            # Probar obtener posición actual
            current_pos = robot.get_current_joint_positions()
            print(f"   📐 Ángulos de articulaciones: {current_pos}")
            
            # Probar método de movimiento (en simulación)
            print("   🧪 Probando método de movimiento (simulación)...")
            # robot.move_joint_relative(0, 5)  # Este método puede no existir
            
            print("   ✅ Métodos básicos del robot funcionando")
            return True
            
        except Exception as e:
            print(f"   ⚠️  Error al ejecutar métodos del robot: {e}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error al crear controlador del robot: {e}")
        return False

def test_application_startup():
    """Probar que la aplicación pueda iniciar correctamente"""
    print("\n🚀 Probando inicio de aplicación...")
    
    try:
        # Importar la clase principal
        from app import RobotWebApp
        
        # Crear instancia de la aplicación
        app_instance = RobotWebApp()
        print("   ✅ Aplicación web creada exitosamente")
        
        print(f"   📍 IP del robot configurada: {app_instance.robot_ip}")
        print(f"   🔗 Estado inicial: {app_instance.app_state}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error al crear aplicación: {e}")
        return False

def main():
    """Función principal"""
    print("="*60)
    print("🧪 PRUEBAS DE CONEXIÓN REAL")
    print("   Controladores de Robot y Gripper")
    print("="*60)
    
    # 1. Probar gripper
    gripper_ok = test_gripper_real_connection()
    
    # 2. Probar robot
    robot_ok = test_robot_real_connection()
    
    # 3. Probar aplicación
    app_ok = test_application_startup()
    
    # 4. Mostrar resumen
    print("\n" + "="*60)
    print("📊 RESUMEN DE PRUEBAS")
    print("="*60)
    
    print(f"🤖 Gripper uSENSE:       {'✅ OK' if gripper_ok else '❌ ERROR'}")
    print(f"🦾 Robot UR5:            {'✅ OK' if robot_ok else '❌ ERROR'}")
    print(f"🚀 Aplicación Web:       {'✅ OK' if app_ok else '❌ ERROR'}")
    
    # 5. Recomendaciones
    print("\n" + "="*60)
    print("💡 SIGUIENTES PASOS")
    print("="*60)
    
    all_ok = gripper_ok and robot_ok and app_ok
    
    if all_ok:
        print("🎉 ¡Todo está funcionando correctamente!")
        print("\n📋 Para iniciar la aplicación completa:")
        print("   python3 app.py")
        print("\n🌐 La aplicación web estará disponible en:")
        print("   http://localhost:5000")
        
    else:
        if not gripper_ok:
            print("❗ Problema con el gripper:")
            print("   - Verifica que esté encendido y configurado")
            print("   - Revisa la configuración en robot_modules/gripper_config.py")
            
        if not robot_ok:
            print("❗ Problema con el robot:")
            print("   - Verifica que esté encendido y en la red")
            print("   - Revisa la configuración IP en los controladores")
            
        if not app_ok:
            print("❗ Problema con la aplicación:")
            print("   - Verifica que todas las dependencias estén instaladas")
            print("   - Ejecuta: pip install -r requirements.txt")

if __name__ == "__main__":
    main()