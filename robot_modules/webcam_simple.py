"""
Controlador simple de webcam - versión simplificada
"""

import cv2
import os
from datetime import datetime

class WebcamController:
    def __init__(self):
        self.cap = None
        self.is_active = False
        self.camera_index = 0
        
        # Directorio para capturas
        self.captures_dir = "static/captures"
        os.makedirs(self.captures_dir, exist_ok=True)
    
    def start_camera(self):
        """Iniciar la cámara"""
        if self.is_active:
            return True
            
        self.cap = cv2.VideoCapture(self.camera_index)
        
        if not self.cap.isOpened():
            print(f"Error: No se pudo abrir la cámara {self.camera_index}")
            return False
            
        # Configurar resolución
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.is_active = True
        print("✅ Cámara iniciada exitosamente")
        return True
    
    def stop_camera(self):
        """Detener la cámara"""
        if not self.is_active:
            return True
            
        if self.cap:
            self.cap.release()
            self.cap = None
            
        self.is_active = False
        print("✅ Cámara detenida")
        return True
    
    def get_frame(self):
        """Obtener un frame de la cámara"""
        if not self.is_active or not self.cap:
            return None
            
        ret, frame = self.cap.read()
        if ret:
            return frame
        return None
    
    def get_frame_as_jpeg(self):
        """Obtener frame como JPEG para streaming"""
        frame = self.get_frame()
        if frame is not None:
            ret, jpeg = cv2.imencode('.jpg', frame)
            if ret:
                return jpeg.tobytes()
        return None
    
    def capture_image(self):
        """Capturar una imagen y guardarla"""
        frame = self.get_frame()
        if frame is not None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"capture_{timestamp}.jpg"
            filepath = os.path.join(self.captures_dir, filename)
            
            success = cv2.imwrite(filepath, frame)
            if success:
                print(f"✅ Imagen guardada: {filename}")
                return filename
            else:
                print("❌ Error guardando imagen")
                return None
        else:
            print("❌ No hay frame disponible para capturar")
            return None
    
    def switch_camera(self):
        """Cambiar entre cámaras disponibles"""
        was_active = self.is_active
        
        if was_active:
            self.stop_camera()
        
        # Intentar siguiente cámara
        self.camera_index = (self.camera_index + 1) % 3  # Intentar cámaras 0, 1, 2
        
        if was_active:
            success = self.start_camera()
            if success:
                print(f"✅ Cambiado a cámara {self.camera_index}")
            else:
                # Si falla, volver a la cámara 0
                self.camera_index = 0
                self.start_camera()
                print("⚠️ Volviendo a cámara 0")