#!/usr/bin/env python3
"""
Test script para probar múltiples comandos consecutivos al gripper
y verificar la funcionalidad de auto-reconexión
"""

import requests
import time
import json

def test_multiple_commands():
    """Envía múltiples comandos al gripper para probar la auto-reconexión"""
    base_url = "http://localhost:5000"
    
    # Lista de comandos a probar
    commands = [
        "GET GRIP MMpos",     # Obtener posición actual
        "DO LIGHT TOGGLE",    # Encender/apagar luz
        "GET GRIP ForceNf",   # Obtener fuerza actual  
        "CONFIG SHOW",        # Mostrar configuración
        "GET GRIP STpos",     # Obtener posición en steps
    ]
    
    print("🧪 Iniciando test de múltiples comandos...")
    print(f"📝 Comandos a ejecutar: {len(commands)}")
    
    for i, command in enumerate(commands, 1):
        print(f"\n🔄 [{i}/{len(commands)}] Enviando comando: {command}")
        
        try:
            # Enviar comando via API REST
            response = requests.post(
                f"{base_url}/api/gripper/command", 
                json={"command": command},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Respuesta: {result.get('message', 'Sin mensaje')}")
                if result.get('response'):
                    print(f"📥 Datos: {result['response']}")
            else:
                print(f"❌ Error HTTP {response.status_code}: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error de conexión: {e}")
            
        # Esperar un momento entre comandos
        print("⏳ Esperando 2 segundos...")
        time.sleep(2)
    
    print("\n✅ Test completado!")

if __name__ == "__main__":
    test_multiple_commands()