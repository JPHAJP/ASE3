"""
Controlador de webcam para la aplicación web UR5
Maneja streaming de video y captura de imágenes
"""

import cv2
import threading
import time
import logging
from datetime import datetime
import os
import base64
import numpy as np

logger = logging.getLogger(__name__)

class WebcamController:
    def __init__(self, camera_index=0):
        """
        Inicializar controlador de webcam
        
        Args:
            camera_index: índice de la cámara (0 por defecto)
        """
        self.camera_index = camera_index
        self.cap = None
        self.is_active = False
        self.is_streaming = False
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.stream_thread = None
        
        # Configuración de la cámara
        self.width = 640
        self.height = 480
        self.fps = 30
        
        # Directorio para capturas
        self.captures_dir = "static/captures"
        os.makedirs(self.captures_dir, exist_ok=True)
        
        logger.info(f"WebcamController inicializado para cámara {camera_index}")
    
    def start_camera(self):
        """Iniciar la cámara"""
        try:
            if self.is_active:
                logger.info("La cámara ya está activa")
                return True
            
            logger.info(f"Iniciando cámara {self.camera_index}...")
            self.cap = cv2.VideoCapture(self.camera_index)
            
            if not self.cap.isOpened():
                logger.error(f"No se pudo abrir la cámara {self.camera_index}")
                return False
            
            # Configurar propiedades de la cámara
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            
            # Verificar que la cámara funciona
            ret, frame = self.cap.read()
            if not ret:
                logger.error("No se pudo leer frame de la cámara")
                self.cap.release()
                return False
            
            self.is_active = True
            logger.info("✅ Cámara iniciada exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"Error iniciando cámara: {e}")
            return False
    
    def stop_camera(self):
        """Detener la cámara"""
        try:
            if not self.is_active:
                logger.info("La cámara ya está inactiva")
                return
            
            logger.info("Deteniendo cámara...")
            
            # Detener streaming si está activo
            self.stop_streaming()
            
            # Liberar recursos
            if self.cap:
                self.cap.release()
                self.cap = None
            
            self.is_active = False
            self.current_frame = None
            
            logger.info("✅ Cámara detenida")
            
        except Exception as e:
            logger.error(f"Error deteniendo cámara: {e}")
    
    def start_streaming(self):
        """Iniciar streaming de video"""
        try:
            if not self.is_active:
                if not self.start_camera():
                    return False
            
            if self.is_streaming:
                logger.info("El streaming ya está activo")
                return True
            
            logger.info("Iniciando streaming de video...")
            self.is_streaming = True
            
            # Crear hilo para captura continua
            self.stream_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.stream_thread.start()
            
            logger.info("✅ Streaming iniciado")
            return True
            
        except Exception as e:
            logger.error(f"Error iniciando streaming: {e}")
            return False
    
    def stop_streaming(self):
        """Detener streaming de video"""
        try:
            if not self.is_streaming:
                return
            
            logger.info("Deteniendo streaming...")
            self.is_streaming = False
            
            # Esperar a que termine el hilo
            if self.stream_thread and self.stream_thread.is_alive():
                self.stream_thread.join(timeout=2)
            
            logger.info("✅ Streaming detenido")
            
        except Exception as e:
            logger.error(f"Error deteniendo streaming: {e}")
    
    def _capture_loop(self):
        """Loop de captura de frames en hilo separado"""
        while self.is_streaming and self.is_active:
            try:
                ret, frame = self.cap.read()
                if ret:
                    # Agregar timestamp al frame
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cv2.putText(frame, timestamp, (10, 30), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    # Agregar información del robot (si está disponible)
                    status_text = "UR5 Web Control - Cámara Activa"
                    cv2.putText(frame, status_text, (10, frame.shape[0] - 10), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    with self.frame_lock:
                        self.current_frame = frame.copy()
                else:
                    logger.warning("No se pudo capturar frame")
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error en captura de frame: {e}")
                time.sleep(0.1)
        
        logger.info("Loop de captura terminado")
    
    def get_frame(self):
        """Obtener el frame actual"""
        with self.frame_lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
            return None
    
    def get_frame_as_jpeg(self):
        """Obtener frame actual como JPEG bytes"""
        frame = self.get_frame()
        if frame is not None:
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ret:
                return buffer.tobytes()
        return None
    
    def capture_photo(self):
        """Capturar una foto y guardarla"""
        try:
            frame = self.get_frame()
            if frame is None:
                logger.error("No hay frame disponible para captura")
                return None
            
            # Generar nombre único
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"capture_{timestamp}.jpg"
            filepath = os.path.join(self.captures_dir, filename)
            
            # Guardar imagen
            cv2.imwrite(filepath, frame)
            
            logger.info(f"✅ Foto capturada: {filename}")
            return f"captures/{filename}"
            
        except Exception as e:
            logger.error(f"Error capturando foto: {e}")
            return None
    
    def get_camera_status(self):
        """Obtener estado actual de la cámara"""
        return {
            "active": self.is_active,
            "streaming": self.is_streaming,
            "camera_index": self.camera_index,
            "resolution": f"{self.width}x{self.height}",
            "fps": self.fps,
            "has_frame": self.current_frame is not None
        }
    
    def set_resolution(self, width, height):
        """Cambiar resolución de la cámara"""
        try:
            if self.is_active:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                
                # Verificar resolución actual
                actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                self.width = actual_width
                self.height = actual_height
                
                logger.info(f"Resolución cambiada a {actual_width}x{actual_height}")
                return True
            else:
                self.width = width
                self.height = height
                return True
                
        except Exception as e:
            logger.error(f"Error cambiando resolución: {e}")
            return False
    
    def __del__(self):
        """Destructor - limpiar recursos"""
        self.stop_camera()

# Instancia global del controlador
webcam_controller = WebcamController()