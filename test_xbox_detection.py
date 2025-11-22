#!/usr/bin/env python3
"""
Script para verificar la detección de controles Xbox
"""

import pygame
import sys

def check_xbox_controllers():
    """Verificar controles Xbox disponibles"""
    print("🎮 VERIFICANDO CONTROLES XBOX")
    print("="*50)
    
    try:
        # Inicializar pygame
        pygame.init()
        pygame.joystick.init()
        
        # Contar controles
        controller_count = pygame.joystick.get_count()
        print(f"📊 Controles detectados: {controller_count}")
        
        if controller_count == 0:
            print("\n❌ NO SE DETECTARON CONTROLES XBOX")
            print("\n💡 SOLUCIONES:")
            print("1. Conecta un control Xbox al PC")
            print("2. Verifica que el control esté encendido")
            print("3. En Linux: verifica permisos con 'ls -la /dev/input/'")
            print("4. Prueba con: 'sudo usermod -a -G input $USER'")
            print("5. Reinicia la sesión después del comando anterior")
        else:
            print(f"\n✅ SE DETECTARON {controller_count} CONTROLES:")
            
            for i in range(controller_count):
                try:
                    joystick = pygame.joystick.Joystick(i)
                    joystick.init()
                    
                    print(f"\n🎮 Control {i}:")
                    print(f"   Nombre: {joystick.get_name()}")
                    print(f"   Botones: {joystick.get_numbuttons()}")
                    print(f"   Ejes: {joystick.get_numaxes()}")
                    print(f"   D-pads: {joystick.get_numhats()}")
                    
                    joystick.quit()
                    
                except Exception as e:
                    print(f"❌ Error con control {i}: {e}")
        
        pygame.quit()
        return controller_count > 0
        
    except Exception as e:
        print(f"❌ Error inicializando pygame: {e}")
        print("\n💡 SOLUCIÓN:")
        print("Instala pygame con: pip install pygame")
        return False

def test_control_input():
    """Probar entrada de un control Xbox por 10 segundos"""
    try:
        pygame.init()
        pygame.joystick.init()
        
        if pygame.joystick.get_count() == 0:
            print("❌ No hay controles para probar")
            return
        
        joystick = pygame.joystick.Joystick(0)
        joystick.init()
        
        print(f"\n🧪 PROBANDO CONTROL: {joystick.get_name()}")
        print("Presiona botones o mueve joysticks por 10 segundos...")
        print("Presiona Ctrl+C para salir antes")
        
        import time
        start_time = time.time()
        clock = pygame.time.Clock()
        
        while time.time() - start_time < 10:
            pygame.event.pump()
            
            # Verificar botones
            buttons_pressed = []
            for i in range(joystick.get_numbuttons()):
                if joystick.get_button(i):
                    buttons_pressed.append(str(i))
            
            # Verificar ejes
            axes_active = []
            for i in range(joystick.get_numaxes()):
                value = joystick.get_axis(i)
                if abs(value) > 0.3:
                    axes_active.append(f"Eje{i}:{value:.2f}")
            
            # Verificar D-pad
            hats_active = []
            for i in range(joystick.get_numhats()):
                hat_value = joystick.get_hat(i)
                if hat_value != (0, 0):
                    hats_active.append(f"Dpad{i}:{hat_value}")
            
            # Mostrar actividad
            if buttons_pressed or axes_active or hats_active:
                activity = []
                if buttons_pressed:
                    activity.append(f"Botones: {','.join(buttons_pressed)}")
                if axes_active:
                    activity.append(f"{','.join(axes_active)}")
                if hats_active:
                    activity.append(f"{','.join(hats_active)}")
                
                print(f"🎮 {' | '.join(activity)}")
            
            clock.tick(30)
        
        joystick.quit()
        pygame.quit()
        print("✅ Prueba de entrada completada")
        
    except KeyboardInterrupt:
        print("\n🛑 Prueba interrumpida por usuario")
    except Exception as e:
        print(f"❌ Error en prueba: {e}")

def main():
    print("🔍 DIAGNÓSTICO DE CONTROLES XBOX")
    print("="*50)
    
    # Verificar controles disponibles
    if check_xbox_controllers():
        print("\n¿Quieres probar la entrada del control? (y/N): ", end="")
        try:
            response = input().lower()
            if response == 'y' or response == 'yes':
                test_control_input()
        except KeyboardInterrupt:
            print("\n🛑 Saliendo...")
    else:
        print("\n❌ No hay controles para probar")
    
    print("\n✅ Diagnóstico completado")

if __name__ == "__main__":
    main()