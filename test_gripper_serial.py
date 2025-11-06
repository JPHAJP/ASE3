#!/usr/bin/env python3
"""
Script de prueba combinado para el controlador del gripper
Usa conexión directa al puerto serie (sin trabarse)
"""

import os
import sys
import time
import serial

# Agregar el directorio actual al path para importar los módulos
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

class DirectGripperController:
    """Controlador directo del gripper usando pyserial"""
    
    def __init__(self, port=None, baudrate=115200, debug=False):
        self.port = port
        self.baudrate = baudrate
        self.debug = debug
        self.ser = None
        self.connected = False
        
        # Auto-detectar puerto si no se especifica
        if not self.port:
            self.port = self.detect_gripper_port()
    
    def detect_gripper_port(self):
        """Detectar automáticamente el puerto del gripper"""
        common_ports = [
            "/dev/ttyACM0",
            "/dev/ttyACM1", 
            "/dev/ttyUSB0",
            "/dev/ttyUSB1",
            "/dev/ttyS0"
        ]
        
        if self.debug:
            print("🔍 Detectando puerto del gripper...")
        
        for port in common_ports:
            if os.path.exists(port):
                if self.debug:
                    print(f"📍 Probando {port}...")
                
                if self.test_port_for_gripper(port):
                    if self.debug:
                        print(f"✅ Gripper detectado en {port}")
                    return port
                    
        if self.debug:
            print("⚠️ No se detectó gripper automáticamente")
        return "/dev/ttyACM0"  # Puerto por defecto
    
    def test_port_for_gripper(self, port):
        """Probar si un puerto tiene el gripper conectado"""
        try:
            # Conexión temporal para prueba
            test_ser = serial.Serial(
                port=port,
                baudrate=self.baudrate,
                timeout=1.0,
                write_timeout=1.0
            )
            
            # Esperar estabilización
            time.sleep(0.5)
            
            # Limpiar buffers
            test_ser.flushInput()
            test_ser.flushOutput()
            
            # Enviar comando de prueba
            test_ser.write(b"HELP\n")
            test_ser.flush()
            
            # Esperar respuesta breve
            time.sleep(0.5)
            
            has_response = test_ser.in_waiting > 0
            
            test_ser.close()
            return has_response
            
        except Exception as e:
            if self.debug:
                print(f"❌ Error probando {port}: {e}")
            return False
    
    def connect(self):
        """Conectar al gripper"""
        if self.connected:
            return True
            
        if not self.port:
            if self.debug:
                print("❌ No hay puerto configurado")
            return False
        
        try:
            if self.debug:
                print(f"🔌 Conectando a {self.port} ({self.baudrate} bps)")
            
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=2.0,
                write_timeout=2.0,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            # Esperar estabilización
            time.sleep(1.0)
            
            # Limpiar buffers
            self.ser.flushInput()
            self.ser.flushOutput()
            
            self.connected = True
            
            if self.debug:
                print("✅ Conexión establecida")
            
            return True
            
        except serial.SerialException as e:
            if self.debug:
                print(f"❌ Error de puerto serie: {e}")
            return False
        except PermissionError as e:
            if self.debug:
                print(f"❌ Error de permisos: {e}")
                print("💡 Solución: sudo chmod 666 /dev/ttyACM0")
                print("💡 O añadir usuario al grupo dialout: sudo usermod -a -G dialout $USER")
            return False
        except Exception as e:
            if self.debug:
                print(f"❌ Error inesperado: {e}")
            return False
    
    def disconnect(self):
        """Desconectar del gripper"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.connected = False
            if self.debug:
                print("🔒 Desconectado")
    
    def send_command(self, command):
        """Enviar comando al gripper"""
        if not self.connected or not self.ser:
            if self.debug:
                print("❌ No hay conexión")
            return False
        
        try:
            cmd_str = f"{command}\n"
            if self.debug:
                print(f"📤 Enviando: {command}")
            
            self.ser.write(cmd_str.encode('utf-8'))
            self.ser.flush()
            return True
            
        except Exception as e:
            if self.debug:
                print(f"❌ Error enviando comando: {e}")
            return False
    
    def read_response(self, timeout=5.0):
        """Leer respuesta del gripper (sin trabarse)"""
        if not self.connected or not self.ser:
            return []
        
        response_lines = []
        start_time = time.time()
        
        try:
            while (time.time() - start_time) < timeout:
                if self.ser.in_waiting > 0:
                    try:
                        line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            response_lines.append(line)
                            if self.debug:
                                print(f"📨 Recibido: {line}")
                    except Exception as e:
                        if self.debug:
                            print(f"⚠️ Error leyendo línea: {e}")
                        break
                
                # Pequeña pausa para evitar uso excesivo de CPU
                time.sleep(0.01)
            
        except KeyboardInterrupt:
            if self.debug:
                print("\n⚠️ Lectura interrumpida por usuario")
        except Exception as e:
            if self.debug:
                print(f"❌ Error en lectura: {e}")
        
        return response_lines
    
    def send_and_receive(self, command, timeout=5.0):
        """Enviar comando y recibir respuesta"""
        if not self.send_command(command):
            return []
        
        return self.read_response(timeout)
    
    def get_gripper_status(self):
        """Obtener estado del gripper"""
        return {
            'port': self.port,
            'baudrate': self.baudrate,
            'connected': self.connected,
            'available_commands': ['HELP', 'OPEN', 'CLOSE', 'STATUS']
        }


def test_port_detection():
    """Probar detección de puertos serie"""
    print("🔍 Probando detección de puertos serie...")
    
    try:
        gripper = DirectGripperController(debug=True)
        print(f"✅ DirectGripperController creado")
        print(f"📍 Puerto detectado: {gripper.port}")
        return gripper
        
    except Exception as e:
        print(f"❌ Error creando controlador: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_port_connection(gripper, specific_port=None):
    """Probar conexión a un puerto específico"""
    if specific_port:
        gripper.port = specific_port
        print(f"\n🔌 Probando conexión a puerto específico: {specific_port}")
    else:
        print(f"\n🔌 Probando conexión al puerto auto-detectado: {gripper.port}")
    
    try:
        # Intentar conectar
        connected = gripper.connect()
        
        if connected:
            print("✅ Conexión establecida exitosamente")
            
            # Probar comando HELP
            print("\n📋 Enviando comando HELP...")
            response = gripper.send_and_receive("HELP", timeout=3.0)
            
            if response:
                print(f"✅ Se recibieron {len(response)} líneas de respuesta")
                print("📋 Respuesta completa:")
                for i, line in enumerate(response, 1):
                    print(f"  {i}: {line}")
            else:
                print("⚠️ No se recibió respuesta al comando HELP")
                
                # Probar comandos alternativos
                alt_commands = ["?", "help", "status", "info"]
                for alt_cmd in alt_commands:
                    print(f"\n🔄 Probando comando alternativo: {alt_cmd}")
                    alt_response = gripper.send_and_receive(alt_cmd, timeout=2.0)
                    if alt_response:
                        print(f"📨 Respuesta a '{alt_cmd}': {alt_response}")
                        break
            
            # Desconectar
            gripper.disconnect()
            
        else:
            print("❌ No se pudo establecer conexión")
            
        return connected
        
    except Exception as e:
        print(f"❌ Error en conexión: {e}")
        return False


def test_available_ports(gripper):
    """Probar puertos comunes donde podría estar el gripper"""
    print("\n🔍 Probando puertos comunes...")
    
    # Puertos típicos en Linux para dispositivos USB/Arduino
    common_ports = [
        "/dev/ttyACM0",
        "/dev/ttyACM1", 
        "/dev/ttyUSB0",
        "/dev/ttyUSB1",
        "/dev/ttyS0"
    ]
    
    for port in common_ports:
        if os.path.exists(port):
            print(f"\n📍 Probando {port}...")
            try:
                test_result = gripper.test_port_for_gripper(port)
                if test_result:
                    print(f"✅ Gripper detectado en {port}")
                    return port
                else:
                    print(f"❌ No hay gripper en {port}")
            except Exception as e:
                print(f"❌ Error probando {port}: {e}")
        else:
            print(f"⚠️ Puerto {port} no existe")
    
    print("❌ No se encontró gripper en puertos comunes")
    return None


def check_device_info():
    """Verificar información del dispositivo"""
    port = "/dev/ttyACM0"
    
    print(f"\n🔍 Información del dispositivo {port}:")
    
    try:
        import subprocess
        
        # Información del sistema
        result = subprocess.run(['ls', '-la', port], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"📁 Permisos: {result.stdout.strip()}")
        
        # Información USB si está disponible
        try:
            result = subprocess.run(['lsusb'], capture_output=True, text=True)
            if result.returncode == 0:
                print("🔌 Dispositivos USB conectados:")
                for line in result.stdout.split('\n'):
                    if any(keyword in line for keyword in ['Arduino', 'CH340', 'CP210', 'FTDI']):
                        print(f"  {line.strip()}")
        except:
            pass
            
    except Exception as e:
        print(f"⚠️ No se pudo obtener información del dispositivo: {e}")


def simulate_gripper_commands(gripper):
    """Simular comandos típicos del gripper si no hay conexión física"""
    print("\n🎮 Simulando comandos de gripper...")
    
    commands = ["HELP", "OPEN", "CLOSE", "STATUS"]
    
    print(f"📡 Simulando comandos en {gripper.port}...")
    
    for cmd in commands:
        print(f"→ Comando simulado: {cmd}")
        time.sleep(0.5)
    
    print("✅ Simulación completada")


def main():
    """Función principal de prueba"""
    print("🚀 Script de Prueba Combinado - Gripper Serie")
    print("=" * 50)
    
    # Cambiar al directorio del proyecto
    os.chdir(current_dir)
    print(f"📍 Directorio de trabajo: {os.getcwd()}")
    
    # Verificar información del dispositivo
    check_device_info()
    
    # Probar detección de puertos
    gripper = test_port_detection()
    if not gripper:
        print("\n❌ No se pudo crear el controlador")
        return False
    
    # Probar puertos disponibles
    detected_port = test_available_ports(gripper)
    
    if detected_port:
        # Si encontramos un puerto, intentar conexión real
        connection_success = test_port_connection(gripper, detected_port)
        if not connection_success:
            print("\n⚠️ Conexión falló, mostrando simulación...")
            simulate_gripper_commands(gripper)
    else:
        # Si no hay gripper físico, mostrar simulación
        print("\n💡 No se detectó gripper físico. Mostrando simulación...")
        simulate_gripper_commands(gripper)
    
    print("\n📋 Información del sistema:")
    status = gripper.get_gripper_status()
    print(f"   Puerto configurado: {status['port']}")
    print(f"   Baudrate: {status['baudrate']}")
    print(f"   Estado: {'Conectado' if status['connected'] else 'Desconectado'}")
    print(f"   Comandos disponibles: {len(status['available_commands'])}")
    for cmd in status['available_commands']:
        print(f"     - {cmd}")
    
    print("\n🎉 Prueba completada")
    print("\n💡 Para conectar un gripper real:")
    print("   1. Conecta el dispositivo por USB")
    print("   2. Verifica que aparezca en /dev/ttyACM* o /dev/ttyUSB*") 
    print("   3. Asegúrate que tenga permisos de lectura/escritura")
    print("   4. Ejecuta este script nuevamente")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Script interrumpido por usuario")
        sys.exit(130)