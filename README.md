# 🤖 Aplicación Web de Control para Robot UR5e

Una aplicación web completa desarrollada con Flask para controlar un robot UR5e, incluyendo control Xbox, simulación 3D, y control Bluetooth del gripper.

## 🚀 Características

- **Control Web Intuitivo**: Interfaz web moderna con Bootstrap y WebSocket en tiempo real
- **Control Xbox**: Integración completa con controlador Xbox para control manual
- **Simulación 3D**: Generación de GIFs de simulación usando Robotics Toolbox
- **Control Bluetooth**: Control del gripper via ESP32 y Bluetooth
- **API REST Completa**: Endpoints para todos los aspectos del control del robot
- **Monitoreo en Tiempo Real**: Estado del robot, posición actual, y logs del sistema
- **Gestión de Posiciones**: Guardar y cargar posiciones predefinidas
- **Rutinas Preestablecidas**: Calibración, ciclos de prueba, y rutinas de seguridad

## 📋 Requisitos del Sistema

### Hardware
- Robot UR5e conectado a la red
- Controlador Xbox (opcional)
- ESP32 con Bluetooth para control del gripper (opcional)
- Cámara web para vista POV (opcional)

### Software
- Python 3.8+
- Sistema Linux (Ubuntu 20.04+ recomendado)
- Bluetooth stack habilitado (para gripper)

## 🛠️ Instalación

### 1. Clonar el repositorio
```bash
cd /home/jpha/Documents/ASE3
```

### 2. Instalar dependencias Python
```bash
pip install -r requirements.txt
```

### 3. Configurar el robot UR5e
Edita `app.py` y cambia la IP del robot:
```python
self.robot_ip = "192.168.1.100"  # Cambia por la IP real de tu robot
```

### 4. Configurar ESP32 (opcional)
Si usas control Bluetooth del gripper, configura la MAC del ESP32 en `app.py`:
```python
self.esp32_mac = "AA:BB:CC:DD:EE:FF"  # MAC de tu ESP32
```

### 5. Instalar dependencias del sistema (Ubuntu)
```bash
# Para Bluetooth
sudo apt-get install bluetooth bluez libbluetooth-dev

# Para matplotlib (si hay problemas de display)
sudo apt-get install python3-tk

# Para pygame (Xbox controller)
sudo apt-get install python3-pygame
```

## 🏃 Ejecución

### Iniciar la aplicación
```bash
python app.py
```

La aplicación estará disponible en: http://localhost:5000

### Logs de la aplicación
Los logs se guardan en `robot_app.log` y también se muestran en la consola web.

## 🎮 Uso de la Aplicación

### Panel de Control Web

1. **Control de Coordenadas**:
   - Ingresa coordenadas en mm y grados
   - Presiona "Mover Robot" para ejecutar el movimiento
   - Se genera automáticamente una simulación 3D

2. **Gestión de Posiciones**:
   - Guarda posiciones actuales con un nombre
   - Carga posiciones guardadas previamente
   - Lista todas las posiciones disponibles

3. **Control del Gripper**:
   - Ajusta fuerza (0-10N) y posición (0-100%)
   - Botones rápidos para abrir/cerrar
   - Comunicación Bluetooth con ESP32

4. **Rutinas Preestablecidas**:
   - Rutina de Calibración
   - Ciclo de Prueba
   - Posición Inicial
   - Rutina de Seguridad

### Control Xbox (Opcional)

Activa el "Modo Xbox Controller" desde el toggle en la interfaz.

**Controles:**
- **Stick Izquierdo**: Movimiento X, Y (modo lineal) o Joints 0, 1 (modo articular)
- **Stick Derecho**: Movimiento Z, RX (modo lineal) o Joints 2, 3 (modo articular)  
- **Triggers LT/RT**: Control RY (modo lineal) o Joint 4 (modo articular)
- **D-pad**: Control RZ (modo lineal) o Joint 5 (modo articular)

**Botones:**
- **A**: Cambiar entre modo lineal/articular
- **B**: Parada de emergencia
- **X**: Ir a posición Home
- **LB/RB**: Reducir/Aumentar velocidad
- **Start**: Mostrar estado del sistema

### API REST

La aplicación expone los siguientes endpoints:

```bash
# Estado del sistema
GET /api/status

# Mover robot
POST /api/robot/move
Content-Type: application/json
{
  "x": 300, "y": -200, "z": 500,
  "rx": 0, "ry": 0, "rz": 0
}

# Ir a Home
POST /api/robot/home

# Gestionar posiciones
GET /api/positions
POST /api/positions
{"name": "mi_posicion"}

# Control del gripper
POST /api/gripper/control
{"force": 5.0, "position": 50.0}

# Ejecutar rutinas
POST /api/routines/1  # 1-4 para diferentes rutinas

# Cambiar modo de control
POST /api/control-mode
{"mode": "xbox"}  # o "coordinates"
```

## 📁 Estructura del Proyecto

```
ASE3/
├── app.py                          # Aplicación Flask principal
├── requirements.txt                # Dependencias Python
├── robot_modules/                  # Módulos del robot
│   ├── ur5_controller.py          # Controlador UR5e
│   ├── xbox_controller_web.py     # Controlador Xbox
│   ├── simulation_generator.py    # Generador de simulaciones 3D
│   └── bluetooth_gripper.py       # Control Bluetooth gripper
├── templates/
│   └── index.html                 # Interfaz web principal
├── static/
│   └── simulations/               # GIFs de simulación generados
├── examples/                      # Código original de referencia
│   ├── xbox_controler/
│   │   └── move_controler.py     # Controlador Xbox original
│   ├── robot_plot/
│   │   └── rob.py                # Simulación 3D original
│   └── bluetooth/
│       └── test_bt.py            # Control Bluetooth original
└── robot_app.log                 # Logs de la aplicación
```

## 🔧 Configuración Avanzada

### Configurar IP del Robot
```python
# En app.py, línea ~45
self.robot_ip = "192.168.1.100"  # IP de tu robot UR5e
```

### Configurar Bluetooth del Gripper
```python
# En app.py, línea ~46  
self.esp32_mac = "AA:BB:CC:DD:EE:FF"  # MAC de tu ESP32
```

### Personalizar Rutinas
Edita las rutinas en `app.py` en la función `run_routine()` (línea ~220):

```python
def run_routine(routine_id):
    routines = {
        1: "Mi Rutina Personalizada",
        # ... agregar más rutinas
    }
```

### Ajustar Parámetros del Robot
En `robot_modules/ur5_controller.py`:

```python
# Velocidades de movimiento
self.joint_speed = 2.0      # rad/s
self.linear_speed = 0.5     # m/s

# Tolerancias de posición
self.position_tolerance_joint = 0.005  # rad
self.position_tolerance_tcp = 0.001    # m
```

## 🐛 Solución de Problemas

### Robot no conecta
1. Verifica que el robot esté encendido y en la red
2. Confirma la IP en `app.py`
3. Revisa que el puerto 30004 (RTDE) esté abierto
4. Comprueba los logs en `robot_app.log`

### Xbox Controller no funciona
1. Conecta el controlador via USB o Bluetooth
2. Instala pygame: `pip install pygame`
3. Verifica permisos de dispositivos USB/Bluetooth
4. Activa el modo Xbox en la interfaz web

### Simulaciones no se generan
1. Instala matplotlib: `pip install matplotlib`
2. Configura backend de matplotlib: `export MPLBACKEND=Agg`
3. Verifica permisos en `static/simulations/`
4. Revisa logs para errores de cinemática inversa

### Bluetooth del gripper no conecta
1. Empareja el ESP32 con el sistema
2. Verifica la MAC en `app.py`
3. Instala dependencias Bluetooth: `sudo apt-get install bluetooth bluez`
4. Ejecuta como usuario con permisos Bluetooth

### Errores de importación
```bash
# Instalar dependencias faltantes
pip install flask flask-socketio
pip install roboticstoolbox-python
pip install ur_rtde
pip install pygame
pip install matplotlib numpy
```

## 📊 Monitoreo y Logs

### Logs del Sistema
- **Archivo**: `robot_app.log`
- **Consola Web**: Panel inferior de la interfaz
- **WebSocket**: Actualizaciones en tiempo real

### Métricas Monitoreadas
- Estado de conexión del robot
- Posición actual (X, Y, Z, RX, RY, RZ)
- Estado del controlador Xbox
- Estado Bluetooth del gripper
- Tiempos de ejecución de movimientos
- Errores y warnings del sistema

## 🔒 Seguridad

### Paradas de Emergencia
- **Botón B del Xbox**: Parada inmediata
- **WebSocket**: Detección de desconexión
- **Timeouts**: Movimientos con timeout automático

### Validaciones
- Límites del workspace del robot
- Validación de coordenadas de entrada
- Cinemática inversa con verificación de solución
- Cooldown entre comandos de movimiento

## 🤝 Contribución

Para contribuir al proyecto:

1. Haz fork del repositorio
2. Crea una rama para tu feature: `git checkout -b feature/nueva-funcionalidad`
3. Commit tus cambios: `git commit -m 'Agregar nueva funcionalidad'`
4. Push a la rama: `git push origin feature/nueva-funcionalidad`
5. Abre un Pull Request

## 📝 Licencia

Este proyecto está bajo la Licencia MIT. Ver archivo `LICENSE` para detalles.

## 🆘 Soporte

Para soporte técnico:

1. Revisa la sección "Solución de Problemas"
2. Consulta los logs en `robot_app.log`
3. Abre un issue en el repositorio
4. Proporciona logs completos y pasos para reproducir el problema

## 🎯 Roadmap

### Próximas características:
- [ ] Integración de cámara web en tiempo real
- [ ] Control de múltiples robots
- [ ] Grabación y reproducción de trayectorias
- [ ] Dashboard de analytics y métricas
- [ ] Control por voz
- [ ] Integración con sistemas de visión artificial
- [ ] API para integración con sistemas externos
- [ ] Soporte para otros modelos de robots UR

---

**Desarrollado con ❤️ para el control industrial de robots UR5e**