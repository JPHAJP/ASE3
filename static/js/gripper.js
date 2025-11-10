/**
 * Controlador del Gripper uSENSEGRIP
 * Script separado para manejar todas las funciones del gripper
 */

class GripperController {
    constructor() {
        this.socket = null;
        this.commandHistory = [];
        this.historyIndex = -1;
        this.isConnected = false;
        this.init();
    }

    init() {
        // Inicializar Socket.IO
        this.socket = io();
        
        // Configurar event listeners
        this.setupEventListeners();
        this.setupSocketListeners();
        
        console.log('✅ GripperController inicializado');
    }

    setupEventListeners() {
        // Comando manual con Enter
        const manualInput = document.getElementById('manualCommand');
        if (manualInput) {
            manualInput.addEventListener('keydown', (event) => this.handleCommandKeyPress(event));
            manualInput.addEventListener('input', () => this.validateCommand());
        }

        // Botones de navegación de historial
        const upBtn = document.getElementById('historyUp');
        const downBtn = document.getElementById('historyDown');
        
        if (upBtn) {
            upBtn.addEventListener('click', () => this.navigateHistory(1));
        }
        
        if (downBtn) {
            downBtn.addEventListener('click', () => this.navigateHistory(-1));
        }

        // Cargar historial de comandos del localStorage
        const savedHistory = localStorage.getItem('gripperCommandHistory');
        if (savedHistory) {
            try {
                this.commandHistory = JSON.parse(savedHistory);
            } catch (e) {
                console.warn('Error cargando historial de comandos:', e);
                this.commandHistory = [];
            }
        }

        this.addGripperMessage('Interfaz del Gripper uSENSEGRIP lista', 'info');
    }

    setupSocketListeners() {
        // Eventos específicos del gripper
        this.socket.on('gripper_response', (data) => {
            this.addGripperMessage(data.response, 'response', true);
        });
        
        this.socket.on('gripper_live_response', (data) => {
            this.addGripperMessage(data.response, 'response', true);
        });
        
        this.socket.on('gripper_status', (data) => {
            this.updateGripperStatus(data);
        });
    }

    // Validar comando en tiempo real
    validateCommand() {
        const input = document.getElementById('manualCommand');
        if (!input) return;
        
        const command = input.value.trim().toUpperCase();
        
        // Lista de comandos válidos
        const validCommands = [
            'HELP',
            'CONFIG STALL STINFO',
            'CONFIG STALL DIAG', 
            'CONFIG HOMING ONBOOT',
            'CONFIG SET MOTORMODE',
            'CONFIG SAVE',
            'MOVE GRIP HOME',
            'MOVE GRIP STEPS',
            'MOVE GRIP DIST',
            'MOVE GRIP TFORCE',
            'GET GRIP USTEP',
            'GET GRIP STPOS',
            'GET GRIP MMPOS',
            'GET GRIP FORCENF',
            'GET GRIP FORCEGF',
            'GET GRIP DISTOBJ',
            'DO FORCE CAL',
            'DO GRIP REBOOT'
        ];
        
        let isValid = false;
        
        // Verificar si el comando es válido
        for (let validCmd of validCommands) {
            if (command === validCmd || command.startsWith(validCmd + ' ')) {
                isValid = true;
                break;
            }
        }
        
        // Aplicar estilo visual
        if (command === '') {
            input.style.borderColor = '';
            input.style.backgroundColor = '';
        } else if (isValid) {
            input.style.borderColor = '#28a745';
            input.style.backgroundColor = 'rgba(40, 167, 69, 0.1)';
        } else {
            input.style.borderColor = '#dc3545';
            input.style.backgroundColor = 'rgba(220, 53, 69, 0.1)';
        }
        
        // Habilitar/deshabilitar botón
        const sendBtn = document.getElementById('sendManualBtn');
        if (sendBtn) {
            sendBtn.disabled = !isValid && command !== '';
        }
    }

    // Agregar mensaje a la consola del gripper
    addGripperMessage(message, type = 'info', isResponse = false) {
        const console = document.getElementById('gripperConsole');
        if (!console) return;
        
        const timestamp = new Date().toLocaleTimeString();
        const messageDiv = document.createElement('div');
        messageDiv.className = 'gripper-log-entry';
        
        let className = 'text-info';
        let prefix = '→';
        
        if (isResponse) {
            prefix = '←';
        }
        
        switch(type) {
            case 'command':
                className = 'text-warning';
                prefix = '→';
                break;
            case 'response':
                className = 'text-success';
                prefix = '←';
                break;
            case 'error':
                className = 'text-danger';
                prefix = '✗';
                break;
            case 'raw':
                className = 'text-primary';
                prefix = '⚡';
                break;
        }
        
        messageDiv.innerHTML = `<span class="text-muted">[${timestamp}]</span> <span class="text-secondary">${prefix}</span> <span class="${className}">${message}</span>`;
        console.appendChild(messageDiv);
        console.scrollTop = console.scrollHeight;
        
        // Mantener solo los últimos 50 mensajes
        while (console.children.length > 50) {
            console.removeChild(console.firstChild);
        }
    }

    // Limpiar consola del gripper
    clearGripperConsole() {
        const console = document.getElementById('gripperConsole');
        if (console) {
            console.innerHTML = '<span class="text-info">🔍 Monitor limpiado - Todas las respuestas del gripper aparecerán aquí en tiempo real</span>';
        }
    }

    // Enviar comando específico del gripper - MONITOR CONTINUO SIN ESPERAR RESPUESTA
    sendGripperCmd(command) {
        this.addGripperMessage(command, 'command');
        
        fetch('/api/gripper/command', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ command: command })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // No hacer nada aquí - las respuestas llegarán por WebSocket
                console.log('Comando enviado exitosamente');
            } else {
                this.addGripperMessage(`Error: ${data.message}`, 'error');
            }
        })
        .catch(error => {
            this.addGripperMessage(`Error de comunicación: ${error.message}`, 'error');
        });
    }

    // Función para establecer modo de motor
    setMotorMode() {
        const modeSelect = document.getElementById('motorModeSelect');
        if (!modeSelect) return;
        
        const mode = modeSelect.value;
        if (mode === '') return;
        
        const modeNames = {'0': 'Normal', '1': 'High Speed', '2': 'Precision'};
        this.sendGripperCmd(`CONFIG SET MOTORMODE ${mode}`);
        this.addGripperMessage(`Configurando modo: ${modeNames[mode]}`, 'info');
    }

    homeGripper() {
        this.sendGripperCmd('MOVE GRIP HOME');
    }

    openGripper() {
        const distanceSlider = document.getElementById('gripperDistance');
        const distanceValue = document.getElementById('distanceValue');
        
        if (distanceSlider) distanceSlider.value = 100;
        if (distanceValue) distanceValue.textContent = '100.0';
        
        this.sendGripperCmd('MOVE GRIP DIST 100.0');
    }

    closeGripper() {
        const distanceSlider = document.getElementById('gripperDistance');
        const distanceValue = document.getElementById('distanceValue');
        
        if (distanceSlider) distanceSlider.value = 0;
        if (distanceValue) distanceValue.textContent = '0.0';
        
        this.sendGripperCmd('MOVE GRIP DIST 0.0');
    }

    // Funciones para comandos específicos con parámetros
    moveSteps() {
        const stepInput = document.getElementById('stepInput');
        if (!stepInput) return;
        
        const steps = stepInput.value;
        if (!steps) {
            this.addGripperMessage('Error: Especifique número de pasos', 'error');
            return;
        }
        this.sendGripperCmd(`MOVE GRIP STEPS ${steps}`);
    }

    moveDist() {
        const distInput = document.getElementById('distInput');
        if (!distInput) return;
        
        const dist = distInput.value;
        if (!dist) {
            this.addGripperMessage('Error: Especifique distancia en mm', 'error');
            return;
        }
        this.sendGripperCmd(`MOVE GRIP DIST ${dist}`);
    }

    setTargetForce() {
        const forceInput = document.getElementById('forceInput');
        if (!forceInput) return;
        
        const force = forceInput.value;
        if (!force) {
            this.addGripperMessage('Error: Especifique fuerza objetivo en N', 'error');
            return;
        }
        this.sendGripperCmd(`MOVE GRIP TFORCE ${force}`);
    }

    // Comando manual con historial
    sendManualCommand() {
        const commandInput = document.getElementById('manualCommand');
        if (!commandInput) return;
        
        const command = commandInput.value.trim();
        
        if (!command) {
            this.addGripperMessage('Error: Comando vacío', 'error');
            return;
        }

        // Agregar al historial
        if (this.commandHistory.length === 0 || this.commandHistory[this.commandHistory.length - 1] !== command) {
            this.commandHistory.push(command);
            // Mantener solo los últimos 10 comandos
            if (this.commandHistory.length > 10) {
                this.commandHistory.shift();
            }
            this.updateCommandHistory();
        }

        // Limpiar input
        commandInput.value = '';
        this.historyIndex = -1;

        // Enviar comando
        this.sendGripperCmd(command);
    }

    // Nueva función para enviar comando completamente RAW
    sendRawCommand() {
        const commandInput = document.getElementById('manualCommand');
        if (!commandInput) return;
        
        const command = commandInput.value.trim();
        
        if (!command) {
            this.addGripperMessage('Error: Comando vacío', 'error');
            return;
        }

        // Agregar al historial
        if (this.commandHistory.length === 0 || this.commandHistory[this.commandHistory.length - 1] !== command) {
            this.commandHistory.push(command);
            if (this.commandHistory.length > 10) {
                this.commandHistory.shift();
            }
            this.updateCommandHistory();
        }

        // Limpiar input
        commandInput.value = '';
        this.historyIndex = -1;

        // Mostrar en consola que es comando RAW
        this.addGripperMessage(`RAW SOCKET: ${command}`, 'raw');
        
        // Enviar comando RAW usando el nuevo endpoint
        fetch('/api/gripper/command/raw', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ command: command })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Comando RAW enviado exitosamente');
                // Las respuestas llegarán por WebSocket
            } else {
                this.addGripperMessage(`Error RAW: ${data.message}`, 'error');
            }
        })
        .catch(error => {
            this.addGripperMessage(`Error RAW: ${error.message}`, 'error');
        });
    }

    handleCommandKeyPress(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            this.sendManualCommand();
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            this.navigateHistory(1);
        } else if (event.key === 'ArrowDown') {
            event.preventDefault();
            this.navigateHistory(-1);
        }
    }

    navigateHistory(direction) {
        if (this.commandHistory.length === 0) return;
        
        this.historyIndex += direction;
        
        if (this.historyIndex < -1) {
            this.historyIndex = -1;
        } else if (this.historyIndex >= this.commandHistory.length) {
            this.historyIndex = this.commandHistory.length - 1;
        }
        
        const commandInput = document.getElementById('manualCommand');
        if (!commandInput) return;
        
        if (this.historyIndex === -1) {
            commandInput.value = '';
        } else {
            commandInput.value = this.commandHistory[this.historyIndex];
        }
    }

    updateCommandHistory() {
        const historyDiv = document.getElementById('commandHistory');
        if (!historyDiv) return;
        
        historyDiv.innerHTML = '';
        
        // Mostrar últimos 3 comandos
        const recentCommands = this.commandHistory.slice(-3).reverse();
        
        recentCommands.forEach((cmd, index) => {
            const cmdDiv = document.createElement('div');
            cmdDiv.className = 'text-muted small';
            cmdDiv.style.cursor = 'pointer';
            cmdDiv.textContent = `${recentCommands.length - index}. ${cmd}`;
            cmdDiv.addEventListener('click', () => {
                const commandInput = document.getElementById('manualCommand');
                if (commandInput) {
                    commandInput.value = cmd;
                }
            });
            historyDiv.appendChild(cmdDiv);
        });
        
        // Guardar historial en localStorage
        try {
            localStorage.setItem('gripperCommandHistory', JSON.stringify(this.commandHistory));
        } catch (e) {
            console.warn('Error guardando historial:', e);
        }
    }

    updateGripperStatus(data) {
        // Actualizar badge de conexión
        const badge = document.getElementById('gripperConnectionBadge');
        if (!badge) return;
        
        if (data.connected) {
            badge.className = 'badge bg-success';
            badge.textContent = 'Conectado (192.168.1.100:502)';
        } else {
            badge.className = 'badge bg-danger';
            badge.textContent = 'Desconectado';
        }
        
        this.isConnected = data.connected;
    }

    // Función auxiliar para mostrar ayuda de comandos
    showCommandHelp() {
        const helpText = `
Comandos disponibles para uSENSEGRIP:

HELP - Mostrar ayuda del dispositivo
CONFIG STALL STINFO - Toggle telemetría StallGuard
CONFIG HOMING ONBOOT - Toggle homing automático
CONFIG SET MOTORMODE <0|1|2> - Modo motor (Normal/HS/Precision)
CONFIG SAVE - Guardar configuración

MOVE GRIP HOME - Ejecutar homing completo
MOVE GRIP STEPS <int> - Mover pasos relativos
MOVE GRIP DIST <float> - Mover a distancia absoluta (mm)
MOVE GRIP TFORCE <float> - Establecer fuerza objetivo (N)

GET GRIP uSTEP - Configuración micropasos
GET GRIP STpos - Posición stepper (pasos)
GET GRIP MMpos - Posición en mm
GET GRIP ForceNf - Fuerza actual (Newtons)
GET GRIP ForceGf - Fuerza actual (gramos-fuerza)
GET GRIP DISTobj - Distancia ToF al objeto (mm)

DO FORCE CAL - Calibración interactiva de fuerza
DO GRIP REBOOT - Reiniciar microcontrolador

Ejemplos:
MOVE GRIP DIST 25.5
MOVE GRIP STEPS 100
CONFIG SET MOTORMODE 1
        `;
        
        this.addGripperMessage(helpText, 'info');
    }

    // Función para forzar estado conectado del gripper
    forceGripperConnectedState() {
        const badge = document.getElementById('gripperConnectionBadge');
        if (badge) {
            badge.className = 'badge bg-success';
            badge.textContent = 'Conectado (192.168.1.100:502)';
        }
        this.isConnected = true;
    }

    // Intentar conexión automática del gripper
    tryAutoConnectGripper() {
        this.addGripperMessage('Intentando conexión automática...', 'info');
        
        fetch('/api/gripper/connect', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.addGripperMessage(data.message, 'info');
                this.updateGripperStatus({ connected: true });
            } else {
                this.addGripperMessage(`Error de conexión: ${data.message}`, 'error');
                this.updateGripperStatus({ connected: false });
            }
        })
        .catch(error => {
            this.addGripperMessage(`Error conectando: ${error.message}`, 'error');
        });
    }
}

// Instancia global del controlador del gripper
let gripperController;

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    gripperController = new GripperController();
    
    // Intentar conectar gripper automáticamente después de un breve delay
    setTimeout(() => {
        gripperController.tryAutoConnectGripper();
    }, 2000);
    
    // Forzar estado del gripper como conectado
    setTimeout(() => {
        gripperController.forceGripperConnectedState();
    }, 500);
});

// Exponer funciones al ámbito global para compatibilidad con onclick en HTML
window.sendGripperCmd = function(command) {
    if (gripperController) {
        gripperController.sendGripperCmd(command);
    }
};

window.sendManualCommand = function() {
    if (gripperController) {
        gripperController.sendManualCommand();
    }
};

window.clearGripperConsole = function() {
    if (gripperController) {
        gripperController.clearGripperConsole();
    }
};

window.homeGripper = function() {
    if (gripperController) {
        gripperController.homeGripper();
    }
};

window.openGripper = function() {
    if (gripperController) {
        gripperController.openGripper();
    }
};

window.closeGripper = function() {
    if (gripperController) {
        gripperController.closeGripper();
    }
};

window.moveSteps = function() {
    if (gripperController) {
        gripperController.moveSteps();
    }
};

window.moveDist = function() {
    if (gripperController) {
        gripperController.moveDist();
    }
};

window.setTargetForce = function() {
    if (gripperController) {
        gripperController.setTargetForce();
    }
};

window.setMotorMode = function() {
    if (gripperController) {
        gripperController.setMotorMode();
    }
};

window.showCommandHelp = function() {
    if (gripperController) {
        gripperController.showCommandHelp();
    }
};

window.forceGripperConnectedState = function() {
    if (gripperController) {
        gripperController.forceGripperConnectedState();
    }
};

window.tryAutoConnectGripper = function() {
    if (gripperController) {
        gripperController.tryAutoConnectGripper();
    }
};

window.validateCommand = function() {
    if (gripperController) {
        gripperController.validateCommand();
    }
};

window.addGripperMessage = function(message, type, isResponse) {
    if (gripperController) {
        gripperController.addGripperMessage(message, type, isResponse);
    }
};

window.initializeGripperInterface = function() {
    // Esta función ya se llama automáticamente en DOMContentLoaded
    console.log('Gripper interface already initialized');
};

window.sendRawCommand = function() {
    if (gripperController) {
        gripperController.sendRawCommand();
    }
};

window.navigateHistory = function(direction) {
    if (gripperController) {
        gripperController.navigateHistory(direction);
    }
};

window.updateCommandHistory = function() {
    if (gripperController) {
        gripperController.updateCommandHistory();
    }
};

window.handleCommandKeyPress = function(event) {
    if (gripperController) {
        gripperController.handleCommandKeyPress(event);
    }
};

window.updateGripperStatus = function(data) {
    if (gripperController) {
        gripperController.updateGripperStatus(data);
    }
};