#!/usr/bin/env python3
"""
Script de prueba para la integración del control Xbox con UR5WebController
Prueba que ambos controladores pueden trabajar juntos compartiendo la conexión RTDE
"""

import time
import sys
import os
import logging

# Agregar el directorio padre al path para importar los módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from robot_modules.ur5_controller import UR5WebController

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_xbox_integration():
    """Probar integración del control Xbox"""
    
    print("="*60)
    print("🎮 PRUEBA DE INTEGRACIÓN XBOX - UR5 WEB CONTROLLER")
    print("="*60)
    
    # Crear instancia del controlador UR5
    robot_ip = "192.168.0.101"  # Cambiar según tu configuración
    
    try:
        logger.info(f"🤖 Inicializando UR5WebController en IP: {robot_ip}")
        controller = UR5WebController(robot_ip)
        
        # Verificar estado inicial
        logger.info("📊 Estado inicial del robot:")
        status = controller.get_robot_status()
        for key, value in status.items():
            logger.info(f"  {key}: {value}")
        
        # Verificar estado Xbox inicial
        logger.info("\n🎮 Estado inicial del Xbox:")
        xbox_status = controller.get_xbox_status()
        for key, value in xbox_status.items():
            logger.info(f"  {key}: {value}")
        
        # Prueba 1: Intentar habilitar control Xbox
        print(f"\n{'='*60}")
        print("🧪 PRUEBA 1: Habilitando control Xbox")
        print("="*60)
        
        result = controller.enable_xbox_control()
        if result:
            logger.info("✅ Control Xbox habilitado exitosamente!")
            
            # Mostrar nuevo estado
            xbox_status = controller.get_xbox_status()
            logger.info("📊 Nuevo estado Xbox:")
            for key, value in xbox_status.items():
                logger.info(f"  {key}: {value}")
            
            # Esperar un poco para permitir que el usuario pruebe el control
            print(f"\n🎮 Control Xbox ACTIVO por 30 segundos...")
            print("📋 Prueba los controles:")
            print("  🅰️ A: Cambiar modo (articular/lineal)")
            print("  🅱️ B: Parada de emergencia")
            print("  ❌ X: Ir a Home")
            print("  🔽🔼 LB/RB: Cambiar velocidad")
            print("  📋 Menu: Toggle debug")
            print("  ▶️ Start: Mostrar estado")
            print("  🕹️ Joysticks: Mover robot")
            
            for i in range(30, 0, -5):
                print(f"⏱️ Tiempo restante: {i} segundos...")
                time.sleep(5)
            
            # Prueba 2: Deshabilitar control Xbox
            print(f"\n{'='*60}")
            print("🧪 PRUEBA 2: Deshabilitando control Xbox")
            print("="*60)
            
            result = controller.disable_xbox_control()
            if result:
                logger.info("✅ Control Xbox deshabilitado exitosamente!")
            else:
                logger.error("❌ Error deshabilitando control Xbox")
            
        else:
            logger.error("❌ No se pudo habilitar el control Xbox")
            logger.info("💡 Posibles causas:")
            logger.info("  - Control Xbox no conectado")
            logger.info("  - pygame no instalado")
            logger.info("  - Permisos insuficientes")
        
        # Prueba 3: Toggle control Xbox
        print(f"\n{'='*60}")
        print("🧪 PRUEBA 3: Toggle control Xbox")
        print("="*60)
        
        initial_status = controller.is_xbox_enabled()
        logger.info(f"Estado inicial: {'Habilitado' if initial_status else 'Deshabilitado'}")
        
        result = controller.toggle_xbox_control()
        new_status = controller.is_xbox_enabled()
        
        if result:
            logger.info(f"✅ Toggle exitoso: {initial_status} -> {new_status}")
        else:
            logger.error("❌ Error en toggle")
        
        # Toggle de vuelta al estado original
        controller.toggle_xbox_control()
        
        # Prueba 4: Verificar que la interfaz web sigue funcionando
        print(f"\n{'='*60}")
        print("🧪 PRUEBA 4: Funciones de interfaz web")
        print("="*60)
        
        # Obtener posición actual
        current_pos = controller.get_current_pose()
        logger.info(f"📍 Posición actual: {current_pos}")
        
        # Probar movimiento desde interfaz web (pequeño desplazamiento)
        if controller.is_connected():
            logger.info("🎯 Probando movimiento desde interfaz web...")
            new_x = current_pos[0] + 10  # Mover 10mm en X
            
            success = controller.move_to_coordinates(
                new_x, current_pos[1], current_pos[2],
                current_pos[3], current_pos[4], current_pos[5]
            )
            
            if success:
                logger.info("✅ Movimiento web exitoso")
                time.sleep(2)
                
                # Regresar a posición original
                success = controller.move_to_coordinates(
                    current_pos[0], current_pos[1], current_pos[2],
                    current_pos[3], current_pos[4], current_pos[5]
                )
                if success:
                    logger.info("✅ Regreso a posición original exitoso")
            else:
                logger.warning("⚠️ Movimiento web no completado (modo desconectado)")
        
        # Mostrar estado final
        print(f"\n{'='*60}")
        print("📊 ESTADO FINAL")
        print("="*60)
        
        final_status = controller.get_robot_status()
        logger.info("🤖 Estado final del robot:")
        for key, value in final_status.items():
            logger.info(f"  {key}: {value}")
        
        print(f"\n{'='*60}")
        print("✅ PRUEBAS COMPLETADAS")
        print("="*60)
        logger.info("🎉 Todas las pruebas de integración completadas!")
        
    except Exception as e:
        logger.error(f"❌ Error crítico en las pruebas: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        # Limpiar recursos
        try:
            if 'controller' in locals():
                controller.disconnect()
                logger.info("🧹 Recursos liberados exitosamente")
        except Exception as e:
            logger.error(f"Error liberando recursos: {e}")
    
    return True

def main():
    """Función principal"""
    try:
        return test_xbox_integration()
    except KeyboardInterrupt:
        print("\n🛑 Pruebas interrumpidas por el usuario")
        return False
    except Exception as e:
        logger.error(f"Error en main: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)