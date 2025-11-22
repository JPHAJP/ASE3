#!/usr/bin/env python3
"""
Verificar qué está usando el puerto 23 del gripper
"""

import socket
import time
import subprocess

def check_gripper_status():
    """Verificar estado del gripper"""
    print("=== VERIFICACIÓN ESTADO GRIPPER ===")
    
    # 1. Verificar conectividad básica
    print("1. Probando ping...")
    try:
        result = subprocess.run(['ping', '-c', '3', '192.168.0.100'], 
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Ping exitoso")
        else:
            print("❌ Ping falló")
            print(result.stderr)
    except Exception as e:
        print(f"❌ Error en ping: {e}")
    
    # 2. Probar conexión directa
    print("\n2. Probando conexión socket...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect(('192.168.0.100', 23))
        print("✅ Conexión socket exitosa")
        
        # Enviar comando simple
        sock.sendall(b"PING\n")
        sock.settimeout(2.0)
        try:
            response = sock.recv(256).decode('utf-8', errors='ignore')
            print(f"✅ Respuesta: {response.strip()}")
        except socket.timeout:
            print("⏰ Sin respuesta (normal)")
        
        sock.close()
        print("✅ Socket cerrado")
        
    except Exception as e:
        print(f"❌ Error socket: {e}")
    
    # 3. Verificar múltiples conexiones consecutivas
    print("\n3. Probando conexiones consecutivas...")
    for i in range(3):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect(('192.168.0.100', 23))
            print(f"  ✅ Conexión {i+1} exitosa")
            sock.close()
            time.sleep(0.5)  # Pequeño delay entre conexiones
        except Exception as e:
            print(f"  ❌ Conexión {i+1} falló: {e}")
    
    print("\n=== FIN VERIFICACIÓN ===")

if __name__ == "__main__":
    check_gripper_status()