import pygame
import sys

def main():
    # Inicializar pygame
    pygame.init()
    pygame.joystick.init()
    
    # Verificar si hay controles conectados
    if pygame.joystick.get_count() == 0:
        print("No se detectaron controles conectados.")
        return
    
    # Conectar al primer control
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    
    print(f"Control conectado: {joystick.get_name()}")
    print(f"Número de botones: {joystick.get_numbuttons()}")
    print(f"Número de ejes: {joystick.get_numaxes()}")
    print(f"Número de hats (D-pad): {joystick.get_numhats()}")
    print("\nPresiona botones en el control (Ctrl+C para salir):")
    print("-" * 50)
    
    # Mapeo de botones para Xbox (puede variar según el sistema)
    button_names = {
        0: "A",
        1: "B", 
        2: "X",
        3: "Y",
        4: "LB (Left Bumper)",
        5: "RB (Right Bumper)",
        6: "Back/View",
        7: "Start/Menu",
        8: "Left Stick Click",
        9: "Right Stick Click",
        10: "Xbox Button"
    }
    
    # Estado previo de botones para detectar cambios
    button_states = [False] * joystick.get_numbuttons()
    
    try:
        clock = pygame.time.Clock()
        
        while True:
            # Procesar eventos
            pygame.event.pump()
            
            # Revisar estado de botones
            for i in range(joystick.get_numbuttons()):
                current_state = joystick.get_button(i)
                
                # Si el botón cambió de no presionado a presionado
                if current_state and not button_states[i]:
                    button_name = button_names.get(i, f"Botón {i}")
                    print(f"Botón presionado: {button_name}")
                
                # Si el botón cambió de presionado a no presionado
                elif not current_state and button_states[i]:
                    button_name = button_names.get(i, f"Botón {i}")
                    print(f"Botón liberado: {button_name}")
                
                button_states[i] = current_state
            
            # Revisar los sticks analógicos (opcional)
            left_x = joystick.get_axis(0)
            left_y = joystick.get_axis(1)
            right_x = joystick.get_axis(2) if joystick.get_numaxes() > 2 else 0
            right_y = joystick.get_axis(3) if joystick.get_numaxes() > 3 else 0
            
            # Solo imprimir si hay movimiento significativo en los sticks
            threshold = 0.5
            if abs(left_x) > threshold or abs(left_y) > threshold:
                print(f"Stick izquierdo: X={left_x:.2f}, Y={left_y:.2f}")
            
            if abs(right_x) > threshold or abs(right_y) > threshold:
                print(f"Stick derecho: X={right_x:.2f}, Y={right_y:.2f}")
            
            # Revisar triggers (si están disponibles)
            if joystick.get_numaxes() > 4:
                left_trigger = joystick.get_axis(4)
                right_trigger = joystick.get_axis(5) if joystick.get_numaxes() > 5 else 0
                
                if left_trigger > 0.1:
                    print(f"Trigger izquierdo: {left_trigger:.2f}")
                if right_trigger > 0.1:
                    print(f"Trigger derecho: {right_trigger:.2f}")
            
            # Revisar D-pad
            if joystick.get_numhats() > 0:
                hat = joystick.get_hat(0)
                if hat != (0, 0):
                    directions = []
                    if hat[1] == 1:
                        directions.append("Arriba")
                    elif hat[1] == -1:
                        directions.append("Abajo")
                    if hat[0] == 1:
                        directions.append("Derecha")
                    elif hat[0] == -1:
                        directions.append("Izquierda")
                    print(f"D-pad: {' + '.join(directions)}")
            
            clock.tick(60)  # 60 FPS
            
    except KeyboardInterrupt:
        print("\nDesconectando...")
        
    finally:
        pygame.quit()

if __name__ == "__main__":
    main()