#!/usr/bin/env python3
"""
Script de prueba para la funcionalidad de webcam
"""

import sys
import os
sys.path.append('/home/jpha/Documents/ASE3')

from robot_modules.webcam_controller import WebcamController
import time

def test_webcam():
    print("🎥 Script de Prueba - Webcam Controller")
    print("=" * 50)
    
    # Crear controlador
    webcam = WebcamController()
    
    try:
        # Probar inicializar cámara
        print("📷 Probando inicialización de cámara...")
        success = webcam.start_camera()
        
        if success:
            print("✅ Cámara iniciada exitosamente")
            
            # Probar streaming
            print("📹 Iniciando streaming...")
            webcam.start_streaming()
            
            # Esperar un momento para capturar frames
            time.sleep(2)
            
            # Probar captura de foto
            print("📸 Capturando foto de prueba...")
            photo_path = webcam.capture_photo()
            
            if photo_path:
                print(f"✅ Foto capturada: {photo_path}")
            else:
                print("❌ Error capturando foto")
            
            # Mostrar estado
            status = webcam.get_camera_status()
            print(f"📊 Estado de cámara: {status}")
            
            # Detener
            print("🛑 Deteniendo cámara...")
            webcam.stop_camera()
            print("✅ Cámara detenida")
            
        else:
            print("❌ No se pudo inicializar la cámara")
            print("💡 Verifica que tengas una webcam conectada")
            
    except Exception as e:
        print(f"❌ Error en test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Limpiar recursos
        webcam.stop_camera()

if __name__ == "__main__":
    test_webcam()