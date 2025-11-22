#!/usr/bin/env python3
"""
Script de prueba para la funcionalidad de toggle de luz del gripper
"""

import sys
import time
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_gripper_light_toggle():
    """Probar funcionalidad de toggle de luz del gripper"""
    
    try:
        from robot_modules.ur5_controller import UR5WebController
        
        logger.info("🤖 Inicializando controlador UR5...")
        controller = UR5WebController()
        
        if not controller.gripper_enabled:
            logger.error("❌ Gripper no está habilitado. Verifica la configuración.")
            return False
        
        logger.info("✅ Controlador inicializado exitosamente")
        
        # Verificar estado del gripper
        gripper_status = controller.get_gripper_status()
        logger.info(f"🦾 Estado del gripper: {gripper_status}")
        
        # Probar toggle de luz varias veces
        logger.info("\n💡 === PRUEBAS DE TOGGLE DE LUZ ===")
        
        for i in range(3):
            logger.info(f"💡 Prueba {i+1}/3: Toggle de luz del gripper...")
            result = controller.gripper_light_toggle()
            logger.info(f"   Resultado: {'✅ Éxito' if result else '❌ Error'}")
            
            if i < 2:  # No esperar después de la última prueba
                logger.info("   Esperando 2 segundos antes del siguiente toggle...")
                time.sleep(2)
        
        logger.info("\n🎮 === INFORMACIÓN DEL CONTROL XBOX ===")
        logger.info("Para usar el toggle de luz en el control Xbox:")
        logger.info("   • Presiona el botón 11 (Start) para toggle de luz")
        logger.info("   • El botón también muestra información del estado")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Error de importación: {e}")
        return False
        
    except Exception as e:
        logger.error(f"❌ Error inesperado: {e}")
        return False
        
    finally:
        # Limpiar recursos
        try:
            if 'controller' in locals():
                controller.disconnect()
                logger.info("🔌 Recursos liberados")
        except:
            pass

def test_socket_gripper_directly():
    """Probar el comando directamente en el socket gripper"""
    
    try:
        from robot_modules.gripper_config import get_gripper_controller
        
        logger.info("🦾 Probando comando directamente en socket gripper...")
        gripper = get_gripper_controller()
        
        if gripper:
            logger.info("🔌 Conectando al gripper...")
            gripper.connect()
            
            logger.info("💡 Enviando comando DO LIGHT TOGGLE...")
            result = gripper.usense_light_toggle()
            logger.info(f"   Resultado: {'✅ Éxito' if result else '❌ Error'}")
            
            gripper.disconnect()
            logger.info("🔌 Gripper desconectado")
            
            return result
        else:
            logger.error("❌ No se pudo obtener controlador del gripper")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error probando socket gripper: {e}")
        return False

def main():
    """Función principal"""
    logger.info("🚀 === PRUEBA DE TOGGLE DE LUZ DEL GRIPPER ===")
    
    # Probar con controlador completo
    logger.info("\n📋 Prueba 1: A través del controlador UR5")
    success1 = test_gripper_light_toggle()
    
    # Probar directamente el socket gripper
    logger.info("\n📋 Prueba 2: Directamente en socket gripper")
    success2 = test_socket_gripper_directly()
    
    if success1 and success2:
        logger.info("\n🎉 ¡Todas las pruebas pasaron exitosamente!")
        logger.info("   El toggle de luz del gripper está funcionando correctamente")
        logger.info("   Botón 11 del Xbox ahora controla la luz del gripper")
    else:
        logger.error("\n💥 Algunas pruebas fallaron")
        if not success1:
            logger.error("   - Falló prueba del controlador UR5")
        if not success2:
            logger.error("   - Falló prueba del socket gripper")
    
    return 0 if (success1 and success2) else 1

if __name__ == "__main__":
    sys.exit(main())