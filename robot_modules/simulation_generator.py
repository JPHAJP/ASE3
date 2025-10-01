"""
Generador de simulaciones 3D para la aplicación web
Basado en rob.py pero adaptado para generar GIFs para la interfaz web
"""

import matplotlib
matplotlib.use('Agg')  # Backend sin GUI para uso en threads
import matplotlib.pyplot as plt
import matplotlib.animation as animation

import roboticstoolbox as rtb
from spatialmath import SE3
import numpy as np
import os
import time
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class SimulationGenerator:
    def __init__(self, log_callback=None):
        """
        Inicializar generador de simulaciones
        
        Args:
            log_callback: función para enviar logs al sistema principal
        """
        # Configurar matplotlib para threading seguro
        plt.ioff()  # Modo interactivo OFF
        
        self.robot = rtb.models.UR5()
        self.current_q = self.robot.qr.copy()  # Posición articular actual
        self.log_callback = log_callback  # Callback para logs del robot
        
        # Directorio para guardar simulaciones
        self.simulations_dir = "static/simulations"
        os.makedirs(self.simulations_dir, exist_ok=True)
        
        # Configuración adicional de matplotlib
        plt.style.use('dark_background')
        
        logger.info("SimulationGenerator inicializado con backend thread-safe")
        if self.log_callback:
            self.log_callback("🎬 Sistema de simulación iniciado", "info")

    def _send_log(self, message, log_type="info"):
        """Enviar log al sistema principal si está disponible"""
        if self.log_callback:
            self.log_callback(message, log_type)

    def validate_workspace(self, x, y, z):
        """Validar que las coordenadas están en el espacio de trabajo"""
        # Convertir de mm a metros si es necesario
        if abs(x) > 10:
            x, y, z = x/1000, y/1000, z/1000
        
        # Límites aproximados del UR5
        x_valid = -0.85 <= x <= 0.85
        y_valid = -0.85 <= y <= 0.85  
        z_valid = -0.2 <= z <= 1.0
        
        return x_valid and y_valid and z_valid, (x, y, z)

    def coordinates_to_pose(self, coordinates):
        """
        Convertir coordenadas [x, y, z, rx, ry, rz] a matriz de transformación
        Acepta coordenadas en mm y grados para facilitar interfaz web
        """
        try:
            x, y, z, rx, ry, rz = coordinates
            
            # Convertir de mm a metros y grados a radianes si es necesario
            x_m = x / 1000.0 if abs(x) > 10 else x
            y_m = y / 1000.0 if abs(y) > 10 else y
            z_m = z / 1000.0 if abs(z) > 10 else z
            
            rx_rad = np.radians(rx) if abs(rx) > 0.1 else rx
            ry_rad = np.radians(ry) if abs(ry) > 0.1 else ry
            rz_rad = np.radians(rz) if abs(rz) > 0.1 else rz
            
            # Crear matriz de transformación
            T = SE3.Trans(x_m, y_m, z_m) * SE3.Rx(rx_rad) * SE3.Ry(ry_rad) * SE3.Rz(rz_rad)
            
            return T, (x_m, y_m, z_m)
            
        except Exception as e:
            logger.error(f"Error convirtiendo coordenadas: {e}")
            return None, None

    def solve_inverse_kinematics(self, target_pose):
        """Resolver cinemática inversa"""
        try:
            sol = self.robot.ik_LM(target_pose, q0=self.current_q)
            
            if sol[1]:  # Verificar convergencia
                return sol[0], True
            else:
                warning_msg = "No se encontró solución de cinemática inversa"
                logger.warning(warning_msg)
                self._send_log(f"⚠️ {warning_msg}", "warning")
                return None, False
                
        except Exception as e:
            logger.error(f"Error en cinemática inversa: {e}")
            return None, False

    def generate_trajectory(self, q_start, q_end, steps=50):
        """Generar trayectoria suave entre dos configuraciones articulares"""
        try:
            qt = rtb.jtraj(q_start, q_end, steps)
            return qt.q
        except Exception as e:
            logger.error(f"Error generando trayectoria: {e}")
            return None

    def create_animation_plot(self, trajectory, title="Simulación Robot UR5"):
        """Crear animación matplotlib de la trayectoria"""
        try:
            fig = plt.figure(figsize=(10, 8))
            fig.patch.set_facecolor('black')
            
            ax = fig.add_subplot(111, projection='3d')
            ax.set_facecolor('black')
            
            # Configurar ejes
            ax.set_xlabel('X (m)', color='white')
            ax.set_ylabel('Y (m)', color='white')
            ax.set_zlabel('Z (m)', color='white')
            ax.tick_params(colors='white')
            
            # Límites de los ejes
            ax.set_xlim([-1, 1])
            ax.set_ylim([-1, 1])
            ax.set_zlim([0, 1.2])
            
            # Título
            ax.text2D(0.05, 0.95, title, transform=ax.transAxes, 
                     color='cyan', fontsize=14, fontweight='bold')
            
            # Función de animación
            def animate(frame):
                ax.clear()
                ax.set_facecolor('black')
                
                # Configurar ejes en cada frame
                ax.set_xlim([-1, 1])
                ax.set_ylim([-1, 1])
                ax.set_zlim([0, 1.2])
                ax.set_xlabel('X (m)', color='white')
                ax.set_ylabel('Y (m)', color='white')
                ax.set_zlabel('Z (m)', color='white')
                ax.tick_params(colors='white')
                
                # Título con número de frame
                ax.text2D(0.05, 0.95, f"{title} - Frame {frame+1}/{len(trajectory)}", 
                         transform=ax.transAxes, color='cyan', fontsize=12, fontweight='bold')
                
                # Dibujar robot en la posición actual
                q_current = trajectory[frame]
                
                # Calcular transformaciones de cada link
                T_links = []
                T = SE3()  # Transformación base
                
                for i in range(len(q_current)):
                    T = T * self.robot.links[i].A(q_current[i])
                    T_links.append(T.t)  # Solo la posición
                
                # Dibujar links del robot
                positions = np.array([[0, 0, 0]] + T_links)  # Incluir base
                
                # Líneas del robot
                ax.plot(positions[:, 0], positions[:, 1], positions[:, 2], 
                       'o-', color='cyan', linewidth=3, markersize=8)
                
                # Resaltar TCP (Tool Center Point)
                tcp_pos = T_links[-1]
                ax.scatter(tcp_pos[0], tcp_pos[1], tcp_pos[2], 
                          color='red', s=100, marker='*', label='TCP')
                
                # Base del robot
                ax.scatter(0, 0, 0, color='green', s=150, marker='s', label='Base')
                
                # Trayectoria del TCP hasta el frame actual
                tcp_trajectory = [self.robot.fkine(trajectory[i]).t for i in range(frame+1)]
                if len(tcp_trajectory) > 1:
                    tcp_traj = np.array(tcp_trajectory)
                    ax.plot(tcp_traj[:, 0], tcp_traj[:, 1], tcp_traj[:, 2], 
                           '--', color='yellow', linewidth=2, alpha=0.7, label='Trayectoria TCP')
                
                # Información en pantalla
                tcp_current = self.robot.fkine(q_current).t
                info_text = f"TCP: X={tcp_current[0]:.3f} Y={tcp_current[1]:.3f} Z={tcp_current[2]:.3f}"
                ax.text2D(0.05, 0.05, info_text, transform=ax.transAxes, 
                         color='white', fontsize=10)
                
                ax.legend(loc='upper right')
                
            return fig, animate
            
        except Exception as e:
            logger.error(f"Error creando animación: {e}")
            return None, None

    def generate_movement_gif(self, target_coordinates, steps=30, duration=3.0):
        """
        Generar GIF de simulación de movimiento
        
        Args:
            target_coordinates: [x, y, z, rx, ry, rz] en mm y grados
            steps: número de frames en la animación
            duration: duración en segundos
            
        Returns:
            str: ruta del archivo GIF generado
        """
        try:
            # Validar coordenadas
            valid, (x_m, y_m, z_m) = self.validate_workspace(*target_coordinates[:3])
            if not valid:
                warning_msg = f"Coordenadas fuera del workspace: {target_coordinates}"
                logger.warning(warning_msg)
                self._send_log(f"⚠️ {warning_msg}", "warning")
            
            # Convertir coordenadas a pose objetivo
            target_pose, _ = self.coordinates_to_pose(target_coordinates)
            if target_pose is None:
                raise ValueError("No se pudo convertir coordenadas a pose")
            
            # Resolver cinemática inversa
            q_target, success = self.solve_inverse_kinematics(target_pose)
            if not success:
                raise ValueError("No se encontró solución de cinemática inversa")
            
            # Generar trayectoria
            trajectory = self.generate_trajectory(self.current_q, q_target, steps)
            if trajectory is None:
                raise ValueError("No se pudo generar trayectoria")
            
            # Crear animación
            title = f"Movimiento a ({target_coordinates[0]:.1f}, {target_coordinates[1]:.1f}, {target_coordinates[2]:.1f})"
            fig, animate_func = self.create_animation_plot(trajectory, title)
            if fig is None:
                raise ValueError("No se pudo crear animación")
            
            # Generar nombre de archivo único
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"movement_{timestamp}.gif"
            filepath = os.path.join(self.simulations_dir, filename)
            
            # Crear animación
            anim = animation.FuncAnimation(
                fig, animate_func, frames=len(trajectory),
                interval=int(duration * 1000 / len(trajectory)),
                blit=False, repeat=True
            )
            
            # Guardar GIF con manejo robusto de recursos
            logger.info(f"Generando GIF: {filepath}")
            try:
                anim.save(filepath, writer='pillow', fps=len(trajectory)/duration)
            finally:
                # Limpiar recursos de matplotlib
                plt.close(fig)
                plt.clf()  # Limpiar figura actual
                plt.cla()  # Limpiar axes actuales
                del anim  # Eliminar referencia a animación
            
            # Actualizar posición actual
            self.current_q = q_target.copy()
            
            logger.info(f"✅ GIF generado exitosamente: {filename}")
            return f"simulations/{filename}"
            
        except Exception as e:
            error_msg = f"❌ Error generando GIF: {e}"
            logger.error(error_msg)
            self._send_log(error_msg, "error")
            
            # Generar GIF de error placeholder
            try:
                return self.generate_error_gif(str(e))
            except:
                return None

    def generate_error_gif(self, error_message):
        """Generar GIF placeholder para errores"""
        try:
            fig, ax = plt.subplots(figsize=(8, 6))
            fig.patch.set_facecolor('black')
            ax.set_facecolor('black')
            
            ax.text(0.5, 0.6, '⚠️ Error en Simulación', 
                   ha='center', va='center', fontsize=20, color='red', fontweight='bold')
            ax.text(0.5, 0.4, error_message[:50] + ('...' if len(error_message) > 50 else ''), 
                   ha='center', va='center', fontsize=12, color='white', wrap=True)
            ax.text(0.5, 0.2, 'Verifica las coordenadas e intenta nuevamente', 
                   ha='center', va='center', fontsize=10, color='yellow')
            
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"error_{timestamp}.gif"
            filepath = os.path.join(self.simulations_dir, filename)
            
            # Crear animación simple (frame estático repetido)
            def animate(frame):
                pass  # No hay cambios entre frames
            
            anim = animation.FuncAnimation(fig, animate, frames=10, interval=500, repeat=True)
            try:
                anim.save(filepath, writer='pillow', fps=2)
            finally:
                plt.close(fig)
                plt.clf()
                plt.cla()
                del anim
            
            return f"simulations/{filename}"
            
        except Exception as e:
            logger.error(f"Error generando GIF de error: {e}")
            return None

    def generate_home_gif(self):
        """Generar GIF de movimiento a posición home"""
        try:
            home_coordinates = [300, -200, 500, 0, 0, 0]  # Posición home aproximada
            return self.generate_movement_gif(home_coordinates, steps=40, duration=4.0)
        except Exception as e:
            logger.error(f"Error generando GIF home: {e}")
            return self.generate_error_gif("Error yendo a posición home")

    def generate_calibration_gif(self):
        """Generar GIF de rutina de calibración"""
        try:
            # Secuencia de posiciones para calibración
            calibration_positions = [
                [400, 0, 600, 0, 0, 0],      # Posición 1
                [0, 400, 600, 0, 0, 0],      # Posición 2  
                [-400, 0, 600, 0, 0, 0],     # Posición 3
                [0, -400, 600, 0, 0, 0],     # Posición 4
                [300, -200, 500, 0, 0, 0]    # Volver a home
            ]
            
            # Por simplicidad, generar GIF solo de la primera posición
            # En una implementación completa, se combinarían todas las posiciones
            return self.generate_movement_gif(calibration_positions[0], steps=50, duration=5.0)
            
        except Exception as e:
            logger.error(f"Error generando GIF calibración: {e}")
            return self.generate_error_gif("Error en rutina de calibración")

    def clean_old_simulations(self, max_age_hours=24):
        """Limpiar archivos de simulación antiguos"""
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            deleted_count = 0
            for filename in os.listdir(self.simulations_dir):
                filepath = os.path.join(self.simulations_dir, filename)
                
                if os.path.isfile(filepath) and filename.endswith('.gif'):
                    file_age = current_time - os.path.getctime(filepath)
                    
                    if file_age > max_age_seconds:
                        os.remove(filepath)
                        deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"✅ Limpiados {deleted_count} archivos de simulación antiguos")
                
        except Exception as e:
            logger.error(f"Error limpiando simulaciones: {e}")

    def get_current_position(self):
        """Obtener posición actual del robot en la simulación"""
        try:
            T_current = self.robot.fkine(self.current_q)
            position = T_current.t
            rotation_rad = T_current.rpy()
            rotation_deg = np.degrees(rotation_rad)
            
            return [
                round(position[0] * 1000, 2),  # X en mm
                round(position[1] * 1000, 2),  # Y en mm
                round(position[2] * 1000, 2),  # Z en mm
                round(rotation_deg[0], 2),     # RX en grados
                round(rotation_deg[1], 2),     # RY en grados
                round(rotation_deg[2], 2),     # RZ en grados
            ]
        except Exception as e:
            logger.error(f"Error obteniendo posición actual: {e}")
            return [300.0, -200.0, 500.0, 0.0, 0.0, 0.0]

    def update_current_position(self, coordinates):
        """Actualizar posición actual del robot en la simulación"""
        try:
            target_pose, _ = self.coordinates_to_pose(coordinates)
            if target_pose is not None:
                q_target, success = self.solve_inverse_kinematics(target_pose)
                if success:
                    self.current_q = q_target.copy()
                    logger.info(f"Posición actualizada en simulación: {coordinates}")
        except Exception as e:
            logger.error(f"Error actualizando posición: {e}")

    def get_simulation_info(self):
        """Obtener información del estado de la simulación"""
        return {
            'current_position': self.get_current_position(),
            'simulations_directory': self.simulations_dir,
            'robot_model': 'UR5',
            'workspace_limits': {
                'x_range': [-850, 850],  # mm
                'y_range': [-850, 850],  # mm  
                'z_range': [-200, 1000]  # mm
            }
        }