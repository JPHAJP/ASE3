# 🎮 INTEGRACIÓN CONTROL XBOX - UR5 WEB CONTROLLER

## Descripción

Esta integración permite usar el control Xbox junto con la interfaz web del UR5, compartiendo la misma conexión RTDE. El control Xbox puede habilitarse y deshabilitarse dinámicamente sin afectar la funcionalidad de la interfaz web.

## Características

✅ **Control compartido**: Xbox y interfaz web usan la misma conexión RTDE  
✅ **Toggle dinámico**: Habilitar/deshabilitar Xbox sin reiniciar la aplicación  
✅ **Sin conflictos**: Solo se permite una conexión RTDE activa  
✅ **Interfaz intacta**: La interfaz web no cambia, solo se agrega el toggle  
✅ **Thread seguro**: Control Xbox ejecuta en hilo separado  

## Nuevas Funciones en UR5WebController

### Métodos de Control Xbox

```python
# Habilitar control Xbox
controller.enable_xbox_control()

# Deshabilitar control Xbox  
controller.disable_xbox_control()

# Alternar estado
controller.toggle_xbox_control()

# Verificar estado
controller.is_xbox_enabled()

# Obtener información completa
status = controller.get_xbox_status()
```

### Estado del Xbox

El método `get_xbox_status()` retorna:
```python
{
    'xbox_enabled': bool,      # Si está habilitado
    'xbox_connected': bool,    # Si el control está conectado
    'control_mode': str,       # "joint" o "linear"
    'debug_mode': bool         # Modo debug activo
}
```

## Nuevas Rutas de API

### `/api/xbox/toggle` (POST)
Alterna el estado del control Xbox.

**Respuesta:**
```json
{
    "success": true,
    "message": "Control Xbox habilitado exitosamente",
    "status": { /* estado del xbox */ }
}
```

### `/api/xbox/enable` (POST)
Habilita el control Xbox.

### `/api/xbox/disable` (POST)
Deshabilita el control Xbox.

### `/api/xbox/direct-status` (GET)
Obtiene el estado completo del control Xbox desde UR5Controller.

**Respuesta:**
```json
{
    "success": true,
    "status": {
        "xbox_enabled": true,
        "xbox_connected": true,
        "control_mode": "joint",
        "debug_mode": false,
        "robot_connected": true,
        "can_control_robot": true,
        "emergency_stop": false,
        "movement_active": false,
        "current_position": [300, -200, 500, 0, 0, 0],
        "speed_level": 2,
        "speed_percentage": 30
    }
}
```

## Controles Xbox

Una vez habilitado, el control Xbox funciona exactamente igual que `move_controler.py`:

### Botones:
- **🅰️ A**: Cambiar modo (articular/lineal)  
- **🅱️ B**: Parada de emergencia / Desactivar parada  
- **❌ X**: Ir a posición Home  
- **🟡 Y**: Sin función  
- **🔽 LB**: Reducir velocidad  
- **🔼 RB**: Aumentar velocidad  
- **📋 Menu**: Toggle modo debug  
- **▶️ Start**: Mostrar estado en logs  

### Controles Analógicos:

**Modo Articular:**
- **🕹️ Stick izq**: Joints 0 (base) y 1 (shoulder)  
- **🕹️ Stick der**: Joints 2 (elbow) y 3 (wrist1)  
- **🎯 Triggers**: Joint 4 (wrist2) - ⚠️ LT/RT intercambiados  
- **➡️ D-pad**: Joint 5 (wrist3)  

**Modo Lineal:**
- **🕹️ Stick izq**: X e Y  
- **🕹️ Stick der Y**: Z  
- **🕹️ Stick der X**: Rotación RX  
- **🎯 Triggers**: Rotación RY - ⚠️ LT/RT intercambiados  
- **➡️ D-pad**: Rotación RZ  

## Implementación en la Interfaz Web

Para agregar un toggle en la interfaz web, usar las nuevas rutas de API:

```javascript
// Función para alternar Xbox
async function toggleXboxControl() {
    try {
        const response = await fetch('/api/xbox/toggle', {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            console.log(data.message);
            updateXboxStatus(data.status);
        } else {
            console.error(data.message);
        }
    } catch (error) {
        console.error('Error toggling Xbox:', error);
    }
}

// Actualizar estado del Xbox en la UI
function updateXboxStatus(status) {
    const toggleBtn = document.getElementById('xbox-toggle');
    const statusText = document.getElementById('xbox-status');
    
    if (status.xbox_enabled) {
        toggleBtn.textContent = 'Deshabilitar Xbox';
        toggleBtn.className = 'btn btn-warning';
        statusText.textContent = status.xbox_connected ? 
            'Xbox Conectado' : 'Xbox Habilitado (No detectado)';
    } else {
        toggleBtn.textContent = 'Habilitar Xbox';
        toggleBtn.className = 'btn btn-success';
        statusText.textContent = 'Xbox Deshabilitado';
    }
}

// Obtener estado actual
async function getXboxStatus() {
    try {
        const response = await fetch('/api/xbox/direct-status');
        const data = await response.json();
        
        if (data.success) {
            updateXboxStatus(data.status);
        }
    } catch (error) {
        console.error('Error getting Xbox status:', error);
    }
}

// HTML sugerido para agregar a la interfaz
/*
<div class="card mb-3">
    <div class="card-header">
        <h5>🎮 Control Xbox</h5>
    </div>
    <div class="card-body">
        <button id="xbox-toggle" class="btn btn-success" onclick="toggleXboxControl()">
            Habilitar Xbox
        </button>
        <p class="mt-2 mb-0">
            Estado: <span id="xbox-status">Xbox Deshabilitado</span>
        </p>
    </div>
</div>
*/
```

## Configuración y Requisitos

### Dependencias:
- `pygame` (para control Xbox)
- `rtde_control`, `rtde_receive`, `rtde_io` (para robot UR5)
- `numpy`, `threading`, `logging`

### Instalación pygame:
```bash
pip install pygame
```

### Verificar control Xbox:
```bash
# Ejecutar script de prueba
python test_xbox_integration.py
```

## Uso Típico

1. **Iniciar aplicación web**: `python app.py`
2. **Conectar control Xbox** al PC
3. **Habilitar Xbox** desde la interfaz web o API
4. **Controlar robot** con Xbox mientras la interfaz web sigue disponible
5. **Deshabilitar Xbox** cuando no sea necesario

## Ventajas de esta Implementación

✅ **Un solo archivo**: Todo integrado en `ur5_controller.py`  
✅ **Sin duplicación**: No hay dos conexiones RTDE separadas  
✅ **Interfaz limpia**: Solo se agrega un toggle simple  
✅ **Compatible**: Funciona con el código existente  
✅ **Flexible**: Puede habilitarse/deshabilitarse dinámicamente  
✅ **Seguro**: Manejo thread-safe y limpieza de recursos  

## Troubleshooting

### Control Xbox no detectado:
```python
# Verificar en logs
logger.error("No se detectaron controles Xbox conectados")
```
**Solución**: Conectar control Xbox y verificar que funciona en el sistema.

### pygame no disponible:
```python
logger.error("pygame no está disponible para control Xbox")
```
**Solución**: `pip install pygame`

### Error de conexión RTDE:
```python
logger.error("Robot no puede ser controlado")
```
**Solución**: Verificar que el robot está conectado y accesible.

### Múltiples conexiones RTDE:
Esta implementación evita este problema al usar una sola instancia compartida.

## Logs de Ejemplo

```
2024-11-18 10:30:15 - INFO - 🎮 Control Xbox HABILITADO
2024-11-18 10:30:15 - INFO - 🎮 Control Xbox conectado: Xbox Wireless Controller
2024-11-18 10:30:15 - INFO - 🎮 Iniciando bucle de control Xbox...
2024-11-18 10:30:20 - INFO - 🔄 Modo cambiado a: LINEAR
2024-11-18 10:30:25 - INFO - 🔽 Velocidad: 10%
2024-11-18 10:30:30 - INFO - 🎮 Control Xbox DESHABILITADO
2024-11-18 10:30:30 - INFO - 🎮 Bucle de control Xbox terminado
```