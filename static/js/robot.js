/**
 * Controlador Principal del Robot UR5
 * Script separado para manejar el control del robot, posiciones y rutinas
 */

class RobotController {
    constructor() {
        this.socket = null;
        this.currentPosition = { x: 300, y: -200, z: 500, rx: 0, ry: 0, rz: 0 };
        this.savedPositions = {};
        this.isXboxMode = false;
        this.isDarkTheme = true;
        this.init();
    }

    init() {
        // Inicializar Socket.IO
        this.socket = io();
        
        // Configurar event listeners
        this.setupEventListeners();
        this.setupSocketListeners();
        
        console.log('✅ RobotController inicializado');
    }

    setupEventListeners() {
        // Sliders para valores de gripper
        this.updateSliderValues();
    }

    setupSocketListeners() {
        this.socket.on('connect', () => {
            this.updateConnectionStatus(true);
            this.addLogMessage('Conectado al servidor', 'info');
        });
        
        this.socket.on('disconnect', () => {
            this.updateConnectionStatus(false);
            this.addLogMessage('Desconectado del servidor', 'warning');
        });
        
        this.socket.on('status_update', (data) => {
            this.updateSystemStatus(data);
        });
        
        this.socket.on('robot_status_update', (data) => {
            this.updateRobotStatus(data);
        });
        
        this.socket.on('new_log', (logEntry) => {
            this.displayLogEntry(logEntry);
        });
    }

    // Actualizar valores de sliders
    updateSliderValues() {
        const forceSlider = document.getElementById('gripperForce');
        const distanceSlider = document.getElementById('gripperDistance');
        
        if (forceSlider) {
            forceSlider.addEventListener('input', function() {
                document.getElementById('forceValue').textContent = this.value;
            });
        }

        if (distanceSlider) {
            distanceSlider.addEventListener('input', function() {
                document.getElementById('distanceValue').textContent = this.value;
            });
        }
    }

    // Actualizar estado de conexión
    updateConnectionStatus(connected) {
        const icon = document.getElementById('connectionIcon');
        const status = document.getElementById('connectionStatus');
        
        if (icon && status) {
            if (connected) {
                icon.className = 'bi bi-wifi';
                status.textContent = 'Conectado';
            } else {
                icon.className = 'bi bi-wifi-off';
                status.textContent = 'Desconectado';
            }
        }
    }

    // Actualizar estado del sistema
    updateSystemStatus(data) {
        // Actualizar estado del robot
        const robotStatus = document.getElementById('robotStatus');
        if (robotStatus) {
            if (data.robot_connected) {
                robotStatus.className = 'badge bg-success';
                robotStatus.textContent = 'Conectado';
            } else {
                robotStatus.className = 'badge bg-danger';
                robotStatus.textContent = 'Desconectado';
            }
        }
        
        // Actualizar estado Xbox
        const xboxStatus = document.getElementById('xboxStatus');
        if (xboxStatus) {
            if (data.xbox_connected) {
                xboxStatus.className = 'badge bg-success';
                xboxStatus.textContent = 'Conectado';
            } else {
                xboxStatus.className = 'badge bg-secondary';
                xboxStatus.textContent = 'Desconectado';
            }
        }
        
        // Actualizar estado Serie
        const serialStatus = document.getElementById('serialStatus');
        const gripperBadge = document.getElementById('gripperConnectionBadge');
        
        if (serialStatus) {
            if (data.serial_connected) {
                serialStatus.className = 'badge bg-success';
                serialStatus.textContent = `Puerto ${data.serial_port || 'COM'}`;
                if (gripperBadge) {
                    gripperBadge.className = 'badge bg-success';
                    gripperBadge.textContent = 'Conectado (192.168.1.100:502)';
                }
            } else {
                serialStatus.className = 'badge bg-warning';
                serialStatus.textContent = 'Sin puerto serie';
                if (gripperBadge) {
                    gripperBadge.className = 'badge bg-danger';
                    gripperBadge.textContent = 'Desconectado';
                }
            }
        }
        
        // Actualizar puerto serie si está disponible
        if (data.serial_port) {
            const serialPortElement = document.getElementById('serialPort');
            if (serialPortElement) {
                serialPortElement.textContent = data.serial_port;
            }
        }
        
        // Actualizar posición actual
        if (data.current_position) {
            this.currentPosition.x = data.current_position[0];
            this.currentPosition.y = data.current_position[1];
            this.currentPosition.z = data.current_position[2];
            this.currentPosition.rx = data.current_position[3];
            this.currentPosition.ry = data.current_position[4];
            this.currentPosition.rz = data.current_position[5];
            this.updateCurrentPositionDisplay();
        }
        
        // Actualizar posiciones guardadas
        if (data.saved_positions) {
            this.savedPositions = data.saved_positions;
        }
    }

    // Actualizar estado del robot
    updateRobotStatus(data) {
        if (data.position) {
            this.currentPosition.x = data.position[0];
            this.currentPosition.y = data.position[1];
            this.currentPosition.z = data.position[2];
            this.currentPosition.rx = data.position[3];
            this.currentPosition.ry = data.position[4];
            this.currentPosition.rz = data.position[5];
            this.updateCurrentPositionDisplay();
        }
    }

    // Actualizar display de posición actual
    updateCurrentPositionDisplay() {
        const elements = {
            'currentX': this.currentPosition.x.toFixed(1),
            'currentY': this.currentPosition.y.toFixed(1),
            'currentZ': this.currentPosition.z.toFixed(1),
            'currentRX': this.currentPosition.rx.toFixed(1),
            'currentRY': this.currentPosition.ry.toFixed(1),
            'currentRZ': this.currentPosition.rz.toFixed(1)
        };
        
        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            }
        });
    }

    // Agregar mensaje al log
    addLogMessage(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        this.displayLogEntry({
            timestamp: timestamp,
            message: message,
            type: type
        });
    }

    // Mostrar entrada de log
    displayLogEntry(logEntry) {
        const console = document.getElementById('consoleLog');
        if (!console) return;
        
        const logDiv = document.createElement('div');
        logDiv.className = 'log-entry';
        
        let className = 'log-info';
        switch(logEntry.type) {
            case 'warning': className = 'log-warning'; break;
            case 'error': className = 'log-error'; break;
            case 'action': className = 'log-action'; break;
        }
        
        logDiv.innerHTML = `<span class="log-timestamp">[${logEntry.timestamp}]</span> <span class="${className}">${logEntry.message}</span>`;
        console.appendChild(logDiv);
        console.scrollTop = console.scrollHeight;
    }

    // Mover robot a coordenadas
    moveToCoordinates() {
        const coords = {
            x: parseFloat(document.getElementById('coordX')?.value) || 0,
            y: parseFloat(document.getElementById('coordY')?.value) || 0,
            z: parseFloat(document.getElementById('coordZ')?.value) || 0,
            rx: parseFloat(document.getElementById('coordRX')?.value) || 0,
            ry: parseFloat(document.getElementById('coordRY')?.value) || 0,
            rz: parseFloat(document.getElementById('coordRZ')?.value) || 0
        };

        const button = document.getElementById('moveBtn');
        if (button) {
            button.disabled = true;
            button.innerHTML = '<span class="loading-spinner"></span>Moviendo...';
        }

        fetch('/api/robot/move', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(coords)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.addLogMessage(data.message, 'action');
            } else {
                this.addLogMessage(`Error: ${data.message}`, 'error');
            }
        })
        .catch(error => {
            this.addLogMessage(`Error de comunicación: ${error.message}`, 'error');
        })
        .finally(() => {
            if (button) {
                button.disabled = false;
                button.innerHTML = '<i class="bi bi-cursor-fill"></i> Mover';
            }
        });
    }

    // Ir a Home
    goHome() {
        fetch('/api/robot/home', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.addLogMessage(data.message, 'action');
            } else {
                this.addLogMessage(`Error: ${data.message}`, 'error');
            }
        })
        .catch(error => {
            this.addLogMessage(`Error yendo a home: ${error.message}`, 'error');
        });
    }

    // Guardar posición
    savePosition() {
        const nameInput = document.getElementById('positionName');
        if (!nameInput) return;
        
        const name = nameInput.value;
        if (!name) {
            this.addLogMessage('Error: Ingrese un nombre para la posición', 'error');
            return;
        }

        fetch('/api/positions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name: name })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.addLogMessage(data.message, 'action');
                nameInput.value = '';
                this.listPositions();
            } else {
                this.addLogMessage(`Error: ${data.message}`, 'error');
            }
        });
    }

    // Cargar posición
    loadPosition() {
        const nameInput = document.getElementById('positionName');
        if (!nameInput) return;
        
        const name = nameInput.value;
        if (!name) {
            this.addLogMessage('Error: Ingrese el nombre de la posición a cargar', 'error');
            return;
        }

        if (this.savedPositions[name]) {
            const pos = this.savedPositions[name];
            const elements = ['coordX', 'coordY', 'coordZ', 'coordRX', 'coordRY', 'coordRZ'];
            elements.forEach((id, index) => {
                const element = document.getElementById(id);
                if (element) {
                    element.value = pos[index];
                }
            });
            this.addLogMessage(`Posición '${name}' cargada en campos`, 'action');
        } else {
            this.addLogMessage(`Error: Posición '${name}' no existe`, 'error');
        }
    }

    // Listar posiciones
    listPositions() {
        fetch('/api/positions')
        .then(response => response.json())
        .then(positions => {
            this.savedPositions = positions;
            let message = 'Posiciones guardadas: ';
            const positionNames = Object.keys(positions);
            if (positionNames.length > 0) {
                message += positionNames.join(', ');
            } else {
                message += 'Ninguna';
            }
            this.addLogMessage(message, 'info');
        });
    }

    // Limpiar log
    clearLog() {
        fetch('/api/logs/clear', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            const console = document.getElementById('consoleLog');
            if (console) {
                console.innerHTML = '';
            }
            this.addLogMessage('Log limpiado', 'info');
        });
    }

    // Toggle modo de control
    toggleControlMode() {
        const toggle = document.getElementById('controlToggle');
        const modeText = document.getElementById('controlMode');
        
        this.isXboxMode = !this.isXboxMode;
        
        const mode = this.isXboxMode ? 'xbox' : 'coordinates';
        
        fetch('/api/control-mode', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ mode: mode })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (toggle) {
                    toggle.classList.toggle('active', this.isXboxMode);
                }
                if (modeText) {
                    modeText.textContent = this.isXboxMode ? 'Xbox Controller' : 'Coordenadas';
                }
                this.addLogMessage(`Modo cambiado a: ${this.isXboxMode ? 'Xbox Controller' : 'Coordenadas'}`, 'action');
            }
        });
    }

    // Ejecutar rutina
    runProgram(programNumber) {
        const programs = {
            1: 'Rutina de Calibración',
            2: 'Ciclo de Prueba',
            3: 'Posición Inicial',
            4: 'Rutina de Seguridad'
        };
        
        const programName = programs[programNumber] || `Programa ${programNumber}`;
        
        fetch(`/api/routines/${programNumber}`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.addLogMessage(`${programName} iniciado`, 'action');
            } else {
                this.addLogMessage(`Error ejecutando ${programName}: ${data.message}`, 'error');
            }
        });
    }

    // Función para cambiar tema
    toggleTheme() {
        this.isDarkTheme = !this.isDarkTheme;
        const body = document.body;
        const themeBtn = document.getElementById('themeToggleBtn');
        
        if (this.isDarkTheme) {
            body.setAttribute('data-theme', 'dark');
            if (themeBtn) {
                themeBtn.innerHTML = '<i class="bi bi-sun"></i>';
                themeBtn.title = 'Cambiar a modo claro';
            }
            localStorage.setItem('theme', 'dark');
            this.addLogMessage('Cambiado a modo oscuro', 'info');
        } else {
            body.setAttribute('data-theme', 'light');
            if (themeBtn) {
                themeBtn.innerHTML = '<i class="bi bi-moon"></i>';
                themeBtn.title = 'Cambiar a modo oscuro';
            }
            localStorage.setItem('theme', 'light');
            this.addLogMessage('Cambiado a modo claro', 'info');
        }
    }

    // Inicializar tema guardado
    initializeTheme() {
        const savedTheme = localStorage.getItem('theme');
        this.isDarkTheme = savedTheme !== 'light'; // Por defecto oscuro
        
        const body = document.body;
        const themeBtn = document.getElementById('themeToggleBtn');
        
        if (this.isDarkTheme) {
            body.setAttribute('data-theme', 'dark');
            if (themeBtn) {
                themeBtn.innerHTML = '<i class="bi bi-sun"></i>';
                themeBtn.title = 'Cambiar a modo claro';
            }
        } else {
            body.setAttribute('data-theme', 'light');
            if (themeBtn) {
                themeBtn.innerHTML = '<i class="bi bi-moon"></i>';
                themeBtn.title = 'Cambiar a modo oscuro';
            }
        }
    }
}

// Instancia global del controlador del robot
let robotController;

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    robotController = new RobotController();
    robotController.initializeTheme();
    robotController.updateCurrentPositionDisplay();
});

// Exponer funciones al ámbito global para compatibilidad con onclick en HTML
window.moveToCoordinates = function() {
    if (robotController) {
        robotController.moveToCoordinates();
    }
};

window.goHome = function() {
    if (robotController) {
        robotController.goHome();
    }
};

window.savePosition = function() {
    if (robotController) {
        robotController.savePosition();
    }
};

window.loadPosition = function() {
    if (robotController) {
        robotController.loadPosition();
    }
};

window.listPositions = function() {
    if (robotController) {
        robotController.listPositions();
    }
};

window.clearLog = function() {
    if (robotController) {
        robotController.clearLog();
    }
};

window.toggleControlMode = function() {
    if (robotController) {
        robotController.toggleControlMode();
    }
};

window.runProgram = function(programNumber) {
    if (robotController) {
        robotController.runProgram(programNumber);
    }
};

window.toggleTheme = function() {
    if (robotController) {
        robotController.toggleTheme();
    }
};

window.addLogMessage = function(message, type) {
    if (robotController) {
        robotController.addLogMessage(message, type);
    }
};

window.updateCurrentPositionDisplay = function() {
    if (robotController) {
        robotController.updateCurrentPositionDisplay();
    }
};

window.updateSystemStatus = function(data) {
    if (robotController) {
        robotController.updateSystemStatus(data);
    }
};

window.updateRobotStatus = function(data) {
    if (robotController) {
        robotController.updateRobotStatus(data);
    }
};

window.displayLogEntry = function(logEntry) {
    if (robotController) {
        robotController.displayLogEntry(logEntry);
    }
};

window.updateConnectionStatus = function(connected) {
    if (robotController) {
        robotController.updateConnectionStatus(connected);
    }
};