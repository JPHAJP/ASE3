#!/usr/bin/env python3
"""
Test simple de conexión socket TCP al gripper
"""

import socket
import time

def test_single_connection():
    """Test con una sola conexión"""
    print("=== TEST CONEXIÓN SIMPLE ===")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        print("Intentando conectar a 192.168.0.100:23...")
        sock.connect(('192.168.0.100', 23))
        print("✅ Conexión exitosa!")
        
        # Enviar comando simple
        sock.sendall(b"HELP\n")
        print("✅ Comando HELP enviado")
        
        # Recibir respuesta (con timeout)
        sock.settimeout(2.0)
        try:
            response = sock.recv(1024).decode('utf-8', errors='ignore')
            print(f"✅ Respuesta: {response[:100]}...")
        except socket.timeout:
            print("⏰ Timeout recibiendo respuesta (normal)")
        
        sock.close()
        print("✅ Conexión cerrada correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_multiple_connections():
    """Test con múltiples conexiones consecutivas"""
    print("\n=== TEST MÚLTIPLES CONEXIONES ===")
    for i in range(3):
        print(f"\nIntento {i+1}/3:")
        if test_single_connection():
            print(f"  ✅ Intento {i+1} exitoso")
        else:
            print(f"  ❌ Intento {i+1} falló")
        time.sleep(1)

def test_concurrent_connections():
    """Test de conexiones concurrentes"""
    print("\n=== TEST CONEXIONES CONCURRENTES ===")
    try:
        sock1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock1.settimeout(5.0)
        sock1.connect(('192.168.0.100', 23))
        print("✅ Primera conexión exitosa")
        
        try:
            sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock2.settimeout(5.0)
            sock2.connect(('192.168.0.100', 23))
            print("✅ Segunda conexión exitosa")
            sock2.close()
        except Exception as e:
            print(f"❌ Segunda conexión falló: {e}")
        
        sock1.close()
        print("✅ Primera conexión cerrada")
        
    except Exception as e:
        print(f"❌ Primera conexión falló: {e}")

if __name__ == "__main__":
    test_single_connection()
    test_multiple_connections()
    test_concurrent_connections()