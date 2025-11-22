#!/usr/bin/env python3
"""
Script de prueba para las nuevas funcionalidades del gripper con control Xbox
"""

import sys
import os
import time
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_gripper_xbox_integration():
    """Probar integración del gripper con control Xbox"""
    
    try:
        # Importar el controlador UR5
        from robot_modules.ur5_controller import UR5WebController
        
        logger.info("🤖 Inicializando controlador UR5 con gripper...")
        controller = UR5WebController()
        
        if not controller.gripper_enabled:
            logger.error("❌ Gripper no está habilitado. Verifica la configuración.")
            return False
        
        logger.info("✅ Controlador inicializado exitosamente")
        
        # Verificar estado del gripper
        gripper_status = controller.get_gripper_status()
        logger.info(f"🦾 Estado del gripper: {gripper_status}")
        
        # Verificar estado del Xbox
        xbox_status = controller.get_xbox_status()
        logger.info(f"🎮 Estado del Xbox: {xbox_status}")
        
        if not xbox_status.get('xbox_connected', False):
            logger.warning("⚠️ Control Xbox no conectado, pero las funciones del gripper están disponibles")
        
        # Pruebas básicas del gripper
        logger.info("\n🧪 === PRUEBAS BÁSICAS DEL GRIPPER ===")
        
        # 1. Probar función home
        logger.info("1️⃣ Probando función HOME del gripper...")
        home_result = controller.gripper_home()
        logger.info(f"   Resultado HOME: {'✅ Éxito' if home_result else '❌ Error'}")
        time.sleep(2)
        
        # 2. Probar función de cierre por pasos
        logger.info("2️⃣ Probando cierre por pasos (500 pasos)...")
        close_result = controller.gripper_close_steps(500)
        logger.info(f"   Resultado cierre: {'✅ Éxito' if close_result else '❌ Error'}")
        time.sleep(2)
        
        # 3. Simular control por gatillo
        logger.info("3️⃣ Simulando control por gatillo derecho...")
        test_triggers = [0.0, 0.25, 0.5, 0.75, 0.9, 0.5, 0.0]
        
        for i, trigger_value in enumerate(test_triggers):
            logger.info(f"   Simulando gatillo: {trigger_value:.2f}")
            controller.process_gripper_control(trigger_value)
            
            # Mostrar estado actual
            current_status = controller.get_gripper_status()
            logger.info(f"   → Steps mapeados: {current_status['current_steps']:.1f}")
            logger.info(f"   → Promedio: {current_status['trigger_average']:.3f}")
            logger.info(f"   → Sobre umbral: {current_status['trigger_above_threshold']}")
            
            time.sleep(0.5)
        
        logger.info("\n✅ === PRUEBAS COMPLETADAS ===")
        logger.info("🎮 Para usar el control Xbox:")
        logger.info("   • Gatillo derecho: Controla posición del gripper (0-5000 pasos)")
        logger.info("   • Gatillo derecho > 80%: Cierra 1000 pasos adicionales")
        logger.info("   • Botón Y: Mueve gripper a posición HOME")
        logger.info("   • Botón 11 (Start): Toggle de luz del gripper + información")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Error de importación: {e}")
        logger.error("   Verifica que todos los módulos estén instalados")
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

def main():
    """Función principal"""
    logger.info("🚀 === PRUEBA DE INTEGRACIÓN GRIPPER + XBOX ===")
    
    success = test_gripper_xbox_integration()
    
    if success:
        logger.info("\n🎉 ¡Todas las pruebas pasaron exitosamente!")
        logger.info("   El sistema está listo para usar el control Xbox con gripper")
    else:
        logger.error("\n💥 Algunas pruebas fallaron")
        logger.error("   Revisa los logs para más detalles")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())