#!/usr/bin/env python3
"""
Script de prueba para verificar la funcionalidad de simulaciones
"""

import os
import sys

# Agregar el directorio actual al path para importar los módulos
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def test_simulation_generation():
    """Probar la generación de simulaciones"""
    print("🧪 Probando generación de simulaciones...")
    
    try:
        from robot_modules.simulation_generator import SimulationGenerator
        
        # Crear instancia del generador
        generator = SimulationGenerator()
        print(f"✅ SimulationGenerator creado")
        print(f"📁 Directorio de simulaciones: {generator.simulations_dir}")
        
        # Verificar que el directorio existe
        if os.path.exists(generator.simulations_dir):
            print(f"✅ Directorio de simulaciones existe")
        else:
            print(f"❌ Directorio de simulaciones no existe")
            return False
        
        # Probar generación de GIF simple
        print("🎬 Generando GIF de prueba...")
        test_coordinates = [400, -100, 600, 0, 0, 0]  # mm y grados
        
        gif_path = generator.generate_movement_gif(test_coordinates, duration=2.0)
        
        if gif_path:
            print(f"✅ GIF generado: {gif_path}")
            
            # Verificar que el archivo existe
            full_path = os.path.join(generator.simulations_dir, os.path.basename(gif_path))
            if os.path.exists(full_path):
                print(f"✅ Archivo GIF existe en disco: {full_path}")
                file_size = os.path.getsize(full_path)
                print(f"📊 Tamaño del archivo: {file_size} bytes")
                return True
            else:
                print(f"❌ Archivo GIF no encontrado en disco: {full_path}")
                return False
        else:
            print("❌ Error generando GIF")
            return False
            
    except Exception as e:
        print(f"❌ Error en test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_static_files():
    """Probar la estructura de archivos estáticos"""
    print("\n📁 Verificando estructura de archivos...")
    
    required_dirs = [
        "static",
        "static/simulations", 
        "templates",
        "robot_modules"
    ]
    
    all_good = True
    
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"✅ {dir_path}")
        else:
            print(f"❌ {dir_path} - FALTA")
            all_good = False
    
    # Listar archivos en simulaciones
    sim_dir = "static/simulations"
    if os.path.exists(sim_dir):
        files = os.listdir(sim_dir)
        print(f"📂 Archivos en {sim_dir}: {len(files)} archivos")
        for f in files:
            file_path = os.path.join(sim_dir, f)
            size = os.path.getsize(file_path)
            print(f"   📄 {f} ({size} bytes)")
    
    return all_good

def main():
    """Función principal de prueba"""
    print("🚀 Script de Prueba - Simulaciones UR5e")
    print("=" * 50)
    
    # Cambiar al directorio del proyecto
    os.chdir(current_dir)
    print(f"📍 Directorio de trabajo: {os.getcwd()}")
    
    # Verificar archivos
    if not test_static_files():
        print("\n❌ Problemas con la estructura de archivos")
        return False
    
    # Probar simulaciones
    if not test_simulation_generation():
        print("\n❌ Problemas con la generación de simulaciones")
        return False
    
    print("\n🎉 ¡Todas las pruebas pasaron exitosamente!")
    print("\n💡 Sugerencias:")
    print("   - Inicia la aplicación con: python app.py")
    print("   - Ve a http://localhost:5000")
    print("   - Prueba mover el robot para generar simulaciones")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)