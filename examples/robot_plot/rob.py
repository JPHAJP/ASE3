import roboticstoolbox as rtb
from spatialmath import SE3
import numpy as np
import sys
import json
import os
from datetime import datetime
import matplotlib.pyplot as plt

class UR5Controller:
    def __init__(self):
        """Inicializa el controlador del robot UR5"""
        self.robot = rtb.models.UR5()
        self.current_q = self.robot.qr.copy()  # Posición articular actual
        self.saved_positions_file = "ur5_saved_positions.json"
        self.load_saved_positions()
        
    def load_saved_positions(self):
        """Carga posiciones guardadas desde archivo"""
        if os.path.exists(self.saved_positions_file):
            try:
                with open(self.saved_positions_file, 'r') as f:
                    self.saved_positions = json.load(f)
                print(f"Cargadas {len(self.saved_positions)} posiciones guardadas")
            except:
                self.saved_positions = {}
        else:
            self.saved_positions = {}
    
    def save_position(self, name, coords, q_joints):
        """Guarda una posición con un nombre"""
        self.saved_positions[name] = {
            'coordinates': coords,
            'joint_config': q_joints.tolist(),
            'timestamp': datetime.now().isoformat()
        }
        with open(self.saved_positions_file, 'w') as f:
            json.dump(self.saved_positions, f, indent=2)
        print(f"Posición '{name}' guardada exitosamente")
    
    def list_saved_positions(self):
        """Lista las posiciones guardadas"""
        if not self.saved_positions:
            print("No hay posiciones guardadas")
            return
        
        print("\n=== POSICIONES GUARDADAS ===")
        for name, data in self.saved_positions.items():
            coords = data['coordinates']
            print(f"{name}: x={coords[0]:.3f}, y={coords[1]:.3f}, z={coords[2]:.3f}, "
                  f"rx={coords[3]:.1f}°, ry={coords[4]:.1f}°, rz={coords[5]:.1f}°")
    
    def get_current_pose(self):
        """Obtiene la pose actual del robot"""
        T_current = self.robot.fkine(self.current_q)
        
        # Extraer posición
        position = T_current.t
        
        # Extraer rotación como ángulos de Euler (en grados)
        rotation_rad = T_current.rpy()
        rotation_deg = np.degrees(rotation_rad)
        
        return position, rotation_deg, T_current
    
    def print_current_status(self):
        """Imprime el estado actual del robot"""
        position, rotation_deg, T_current = self.get_current_pose()
        
        print("\n" + "="*50)
        print("ESTADO ACTUAL DEL ROBOT UR5")
        print("="*50)
        print(f"Posición (mm):")
        print(f"  X: {position[0]*1000:.2f} mm")
        print(f"  Y: {position[1]*1000:.2f} mm") 
        print(f"  Z: {position[2]*1000:.2f} mm")
        print(f"\nOrientación (grados):")
        print(f"  Roll (RX):  {rotation_deg[0]:.2f}°")
        print(f"  Pitch (RY): {rotation_deg[1]:.2f}°")
        print(f"  Yaw (RZ):   {rotation_deg[2]:.2f}°")
        print(f"\nConfiguración articular (grados):")
        joint_degrees = np.degrees(self.current_q)
        for i, angle in enumerate(joint_degrees):
            print(f"  Joint {i+1}: {angle:.2f}°")
        print("="*50)
    
    def validate_joint_limits(self, q_target):
        """Valida que la configuración esté dentro de los límites articulares"""
        exceeded_joints = []
        for i, (q, qmin, qmax) in enumerate(zip(q_target, self.robot.qlim[:, 0], self.robot.qlim[:, 1])):
            if q < qmin or q > qmax:
                exceeded_joints.append(i+1)
        
        if exceeded_joints:
            print(f"⚠️  ADVERTENCIA: Las articulaciones {exceeded_joints} exceden los límites")
            return False
        return True
    
    def validate_workspace(self, x, y, z):
        """Valida que las coordenadas están en el espacio de trabajo aproximado"""
        # Límites aproximados del UR5 (en metros)
        x_valid = -0.85 <= x <= 0.85
        y_valid = -0.85 <= y <= 0.85  
        z_valid = -0.2 <= z <= 1.0
        
        if not (x_valid and y_valid and z_valid):
            print("⚠️  ADVERTENCIA: Las coordenadas pueden estar fuera del espacio de trabajo del UR5")
            print(f"   Rangos recomendados: X[-0.85, 0.85], Y[-0.85, 0.85], Z[-0.2, 1.0]")
            return False
        return True
    
    def get_coordinates_from_input(self):
        """Obtiene las coordenadas desde la entrada del usuario"""
        print("\n" + "-"*50)
        print("OPCIONES DE ENTRADA:")
        print("1. Coordenadas: x y z rx ry rz")
        print("2. 'list' - Ver posiciones guardadas")
        print("3. 'load [nombre]' - Cargar posición guardada")
        print("4. 'save [nombre]' - Guardar posición actual")
        print("5. 'status' - Ver estado actual")
        print("6. 'quit' - Salir")
        print("-"*50)
        
        try:
            user_input = input("Entrada: ").strip()
            
            if user_input.lower() == 'quit':
                return 'quit', None
            elif user_input.lower() == 'list':
                self.list_saved_positions()
                return 'continue', None
            elif user_input.lower() == 'status':
                self.print_current_status()
                return 'continue', None
            elif user_input.lower().startswith('save '):
                name = user_input[5:].strip()
                if name:
                    pos, rot, _ = self.get_current_pose()
                    coords = [pos[0], pos[1], pos[2], rot[0], rot[1], rot[2]]
                    self.save_position(name, coords, self.current_q)
                else:
                    print("Error: Especifica un nombre para guardar")
                return 'continue', None
            elif user_input.lower().startswith('load '):
                name = user_input[5:].strip()
                if name in self.saved_positions:
                    coords = self.saved_positions[name]['coordinates']
                    print(f"Cargando posición '{name}'...")
                    return 'move', coords
                else:
                    print(f"Error: Posición '{name}' no encontrada")
                    return 'continue', None
            else:
                # Interpretar como coordenadas
                coords = [float(x) for x in user_input.split()]
                if len(coords) != 6:
                    raise ValueError("Se requieren exactamente 6 valores")
                return 'move', coords
                
        except (ValueError, IndexError) as e:
            print(f"❌ Error en la entrada: {e}")
            print("Ejemplo: 0.5 -0.2 0.3 0 0 0")
            return 'continue', None
    
    def move_robot_to_position(self, x, y, z, rx, ry, rz):
        """Mueve el robot a la posición especificada"""
        
        print(f"\n🎯 Moviendo a: ({x:.3f}, {y:.3f}, {z:.3f}) con rotación ({rx:.1f}°, {ry:.1f}°, {rz:.1f}°)")
        
        # Validar espacio de trabajo
        self.validate_workspace(x, y, z)
        
        # Convertir ángulos de grados a radianes
        rx_rad = np.radians(rx)
        ry_rad = np.radians(ry)
        rz_rad = np.radians(rz)
        
        # Crear la matriz de transformación objetivo
        Tep = SE3.Trans(x, y, z) * SE3.Rx(rx_rad) * SE3.Ry(ry_rad) * SE3.Rz(rz_rad)
        
        try:
            # Resolver cinemática inversa
            sol = self.robot.ik_LM(Tep, q0=self.current_q)  # Usar posición actual como semilla
            
            if sol[1]:  # Verificar convergencia
                q_target = sol[0]
                
                # Validar límites articulares
                self.validate_joint_limits(q_target)
                
                print(f"✅ Solución encontrada")
                
                # Crear trayectoria suave desde posición actual hasta objetivo
                qt = rtb.jtraj(self.current_q, q_target, 100)
                
                # Visualizar con matplotlib
                print("� Mostrando visualización con matplotlib...")
                self.robot.plot(qt.q, backend='pyplot', block=False)
                plt.show(block=False)
                plt.pause(0.1)  # Pausa para que se actualice la visualización
                
                # Actualizar posición actual
                self.current_q = q_target.copy()
                
                print("✅ Movimiento completado")
                self.print_current_status()
                
                return True
            else:
                print("❌ No se encontró solución de cinemática inversa válida")
                return False
                
        except Exception as e:
            print(f"❌ Error al calcular movimiento: {e}")
            return False
    
    def run_interactive_mode(self):
        """Ejecuta el modo interactivo continuo"""
        print("🤖 === CONTROLADOR INTERACTIVO UR5 ===")
        print("Visualización con matplotlib - cierra las ventanas para continuar")
        
        # Mostrar estado inicial
        self.print_current_status()
        
        while True:
            try:
                action, coords = self.get_coordinates_from_input()
                
                if action == 'quit':
                    print("👋 Cerrando aplicación...")
                    plt.close('all')  # Cerrar todas las ventanas de matplotlib
                    break
                elif action == 'continue':
                    continue
                elif action == 'move' and coords:
                    x, y, z, rx, ry, rz = coords
                    self.move_robot_to_position(x, y, z, rx, ry, rz)
                
            except KeyboardInterrupt:
                print("\n👋 Interrupción por teclado. Cerrando...")
                break
            except Exception as e:
                print(f"❌ Error inesperado: {e}")
                continue

def main():
    """Función principal"""
    print("🤖 Iniciando Control del Robot UR5")
    
    # Verificar si se pasaron argumentos de línea de comandos
    if len(sys.argv) == 7:
        try:
            coords = [float(arg) for arg in sys.argv[1:]]
            controller = UR5Controller()
            x, y, z, rx, ry, rz = coords
            success = controller.move_robot_to_position(x, y, z, rx, ry, rz)
            if success:
                controller.run_interactive_mode()
        except ValueError:
            print("❌ Error: Argumentos inválidos")
            print("Uso: python ur5_controller.py x y z rx ry rz")
    else:
        # Modo interactivo desde el inicio
        controller = UR5Controller()
        controller.run_interactive_mode()

if __name__ == "__main__":
    main()