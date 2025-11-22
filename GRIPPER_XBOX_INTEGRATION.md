# Control del Gripper con Xbox Controller

Este documento describe las nuevas funcionalidades agregadas al control Xbox para manejar el gripper uSENSE.

## 📋 Nuevas Funcionalidades Implementadas

### 1. Control por Gatillo Derecho (Mapeo 0-5000 pasos)

**Funcionamiento:**
- El gatillo derecho mapea linealmente de 0% a 100% → 0 a 5000 pasos del gripper
- Se calcula un promedio de los últimos 4 segundos para suavizar el movimiento
- Los valores se redondean a 1 decimal para precisión
- Solo se ejecuta movimiento si hay un cambio significativo (>50 pasos)

**Configuración:**
```python
# Variables en ur5_controller.py
self.right_trigger_buffer_duration = 4.0  # segundos para promedio
self.last_mapped_steps = 0  # Para evitar movimientos redundantes
```

### 2. Botón Y - Home del Gripper

**Función:** Ejecuta comando "MOVE GRIP HOME"
- **Botón:** Y (ID: 4)
- **Comando enviado:** `MOVE GRIP HOME`
- **Respuesta:** Se considera éxito si se envía el comando (el gripper no siempre responde)

### 3. Cierre Automático por Umbral

**Funcionamiento:**
- Cuando el gatillo derecho supera 80% (0.8): Cierra 1000 pasos
- Espera a que baje del 80% antes de permitir nuevo cierre
- Previene activaciones múltiples accidentales

**Configuración:**
```python
self.trigger_threshold = 0.8  # Umbral para activar cierre
self.close_steps = 1000      # Pasos a cerrar
self.trigger_was_above_threshold = False  # Estado del umbral
```

### 4. Toggle de Luz del Gripper

**Función:** Ejecuta comando "DO LIGHT TOGGLE"
- **Botón:** 11 (Start)
- **Comando enviado:** `DO LIGHT TOGGLE`
- **Respuesta:** Se considera éxito si se envía el comando (el gripper no siempre responde)
- **Funcionalidad adicional:** También muestra información del estado del sistema

## 🎮 Mapeo de Controles

### Nuevos Controles del Gripper:
- **Gatillo Derecho:** Control de posición (0-5000 pasos con promedio de 4s)
- **Gatillo Derecho > 80%:** Cierra 1000 pasos automáticamente
- **Botón Y:** Home del gripper (`MOVE GRIP HOME`)
- **Botón 11 (Start):** Toggle de luz del gripper (`DO LIGHT TOGGLE`)

### Controles Existentes (sin cambios):
- **Botón A:** Cambiar modo (linear/joint)
- **Botón B:** Parada de emergencia
- **Botón X:** Home del robot
- **Botón 11 (Start):** Toggle de luz del gripper + mostrar información
- **LB/RB:** Cambiar velocidad
- **Joysticks:** Control de movimiento
- **D-pad:** Control de rotación

## 🔧 Integración Técnica

### Módulos Involucrados:
1. **ur5_controller.py** - Controlador principal con nuevas funciones
2. **gripper_config.py** - Configuración del gripper
3. **socket_gripper.py** - Comunicación con gripper

### Nuevos Métodos Agregados:

```python
def process_gripper_control(self, right_trigger_value):
    """Procesa control del gripper con gatillo derecho"""

def gripper_home(self):
    """Mueve gripper a posición home"""

def gripper_close_steps(self, steps):
    """Cierra gripper un número específico de pasos"""

def gripper_move_to_steps(self, target_steps):
    """Mueve gripper a posición específica en pasos"""

def get_gripper_status(self):
    """Obtiene estado del gripper para interfaz web"""

def gripper_light_toggle(self):
    """Toggle de la luz del gripper"""
```

### Flujo de Datos:

```
Xbox Controller → process_analog_input() → process_gripper_control() → Gripper Commands
             ↓
    Button Y → handle_button_press() → gripper_home() → "MOVE GRIP HOME"
             ↓
 Button 11 → handle_button_press() → gripper_light_toggle() → "DO LIGHT TOGGLE"
```

## 🚀 Uso

### Inicialización:
```python
from robot_modules.ur5_controller import UR5WebController

# El controlador inicializa automáticamente el gripper si está disponible
controller = UR5WebController()
```

### Verificación de Estado:
```python
# Estado del gripper
gripper_status = controller.get_gripper_status()
print(f"Gripper habilitado: {gripper_status['gripper_enabled']}")
print(f"Steps actuales: {gripper_status['current_steps']}")
print(f"Promedio gatillo: {gripper_status['trigger_average']}")
```

### Control Manual:
```python
# Home del gripper
controller.gripper_home()

# Toggle de luz del gripper
controller.gripper_light_toggle()

# Cerrar pasos específicos
controller.gripper_close_steps(500)

# Estado completo incluyendo gripper
status = controller.get_robot_status()
```

## 🔍 Debugging

### Logs Informativos:
- `🦾 Gatillo promedio: 0.750 → 3750.0 pasos` - Mapeo del gatillo
- `🦾 Gatillo > 0.8: Cerrando gripper 1000 pasos` - Activación por umbral
- `🦾 Ejecutando MOVE GRIP HOME...` - Home del gripper
- `💡 Ejecutando toggle de luz del gripper...` - Toggle de luz

### Variables de Debug:
```python
self.debug_mode = True  # Habilita logs detallados
```

## ⚠️ Consideraciones

1. **Comunicación del Gripper:** El gripper uSENSE no siempre envía respuestas, esto es normal
2. **Thread Safety:** Todos los métodos son thread-safe
3. **Tolerancia:** Se evitan movimientos pequeños (<50 pasos) para prevenir spam
4. **Promediado:** El buffer de 4 segundos suaviza los movimientos del gatillo
5. **Recursos:** El gripper se desconecta automáticamente al cerrar el controlador

## 📁 Archivos Modificados

1. **`robot_modules/ur5_controller.py`**
   - Agregadas importaciones del gripper
   - Nuevas variables de inicialización
   - Modificación de `process_analog_input()`
   - Cambio de funcionalidad del botón Y
   - Nuevos métodos para control del gripper
   - Actualización de `get_robot_status()`

2. **`test_gripper_xbox.py`** (nuevo)
   - Script de prueba para validar funcionalidades del gripper

3. **`test_gripper_light.py`** (nuevo)
   - Script de prueba específico para toggle de luz

4. **`robot_modules/socket_gripper.py`**
   - Agregado soporte para comando "DO LIGHT"
   - Nuevo método `usense_light_toggle()`

## 🧪 Pruebas

Ejecutar el script de prueba:
```bash
python test_gripper_xbox.py
```

El script verifica:
- Inicialización del gripper
- Funciones básicas (home, cierre)
- Simulación de control por gatillo
- Estados y configuración

---

**Autor:** Implementación de control de gripper con Xbox Controller  
**Fecha:** Noviembre 2025  
**Versión:** 1.0