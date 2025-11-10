
        // Variables globales
        let socket;
        let isXboxMode = false;
        let savedPositions = {};
        let currentPosition = { x: 300, y: -200, z: 500, rx: 0, ry: 0, rz: 0 };
        
        // Inicialización
        document.addEventListener('DOMContentLoaded', function() {
            initializeWebSocket();
            updateSliderValues();
            updateCurrentPositionDisplay();
            initializeGripperInterface();
            
            // Intentar conectar gripper automáticamente después de un breve delay
            setTimeout(function() {
                tryAutoConnectGripper();
            }, 2000);
            
            addLogMessage('Sistema web inicializado', 'info');
        });

        // Intentar conexión automática del gripper
        function tryAutoConnectGripper() {
            addGripperMessage('Intentando conexión automática...', 'info');
            
            fetch('/api/gripper/connect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    addGripperMessage('✅ Gripper conectado automáticamente', 'info');
                    updateGripperStatus({ connected: true, port: data.port });
                } else {
                    addGripperMessage(`⚠️ No se pudo conectar automáticamente: ${data.message}`, 'warning');
                    updateGripperStatus({ connected: false });
                }
            })
            .catch(error => {
                addGripperMessage(`❌ Error en conexión automática: ${error}`, 'error');
                updateGripperStatus({ connected: false });
            });
        }

        // Inicializar interfaz del gripper
        function initializeGripperInterface() {
            // Cargar historial de comandos del localStorage
            const savedHistory = localStorage.getItem('gripperCommandHistory');
            if (savedHistory) {
                try {
                    commandHistory = JSON.parse(savedHistory);
                    updateCommandHistory();
                } catch (e) {
                    console.warn('Error cargando historial de comandos:', e);
                }
            }
            
            // Validación en tiempo real del input manual
            const manualInput = document.getElementById('manualCommand');
            manualInput.addEventListener('input', validateCommand);
            
            addGripperMessage('Interfaz del Gripper uSENSEGRIP lista', 'info');
        }

        // Validar comando en tiempo real
        function validateCommand() {
            const input = document.getElementById('manualCommand');
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
                input.style.backgroundColor = '#f8fff8';
            } else {
                input.style.borderColor = '#dc3545';
                input.style.backgroundColor = '#fff8f8';
            }
            
            // Habilitar/deshabilitar botón
            const sendBtn = document.getElementById('sendManualBtn');
            sendBtn.disabled = !isValid && command !== '';
        }

        // Inicializar WebSocket
        function initializeWebSocket() {
            socket = io();
            
            socket.on('connect', function() {
                addLogMessage('Conexión WebSocket establecida', 'info');
                updateConnectionStatus(true);
                socket.emit('request_status');
            });
            
            socket.on('disconnect', function() {
                addLogMessage('Conexión WebSocket perdida', 'warning');
                updateConnectionStatus(false);
            });
            
            socket.on('status_update', function(data) {
                updateSystemStatus(data);
            });
            
            socket.on('robot_status_update', function(data) {
                updateRobotStatus(data);
            });
            
            socket.on('new_log', function(logEntry) {
                displayLogEntry(logEntry);
            });
            
            // Eventos específicos del gripper
            socket.on('gripper_response', function(data) {
                let messageType = 'response';
                if (data.is_error) {
                    messageType = 'error';
                } else if (data.is_raw) {
                    messageType = 'raw_response';
                }
                addGripperMessage(data.response, messageType, true);
            });
            
            // Nuevo evento para respuestas en tiempo real del gripper
            socket.on('gripper_live_response', function(data) {
                addGripperMessage(data.response, 'raw_response', true);
            });
            
            socket.on('gripper_status', function(data) {
                updateGripperStatus(data);
            });
        }

        // Actualizar estado de conexión
        function updateConnectionStatus(connected) {
            const icon = document.getElementById('connectionIcon');
            const status = document.getElementById('connectionStatus');
            
            if (connected) {
                icon.className = 'bi bi-wifi';
                status.textContent = 'Conectado';
            } else {
                icon.className = 'bi bi-wifi-off';
                status.textContent = 'Desconectado';
            }
        }

        // Actualizar estado del sistema
        function updateSystemStatus(data) {
            // Actualizar estado del robot
            const robotStatus = document.getElementById('robotStatus');
            if (data.robot_connected) {
                robotStatus.textContent = 'Conectado';
                robotStatus.className = 'status-connected';
            } else {
                robotStatus.textContent = 'Desconectado';
                robotStatus.className = 'status-disconnected';
            }
            
            // Actualizar estado Xbox
            const xboxStatus = document.getElementById('xboxStatus');
            if (data.xbox_connected) {
                xboxStatus.textContent = 'Conectado';
                xboxStatus.className = 'status-connected';
            } else {
                xboxStatus.textContent = 'Desconectado';
                xboxStatus.className = 'status-disconnected';
            }
            
            // Actualizar estado Serie
            const serialStatus = document.getElementById('serialStatus');
            const gripperBadge = document.getElementById('gripperConnectionBadge');
            
            if (data.serial_connected) {
                serialStatus.textContent = 'Conectado';
                serialStatus.className = 'status-connected';
                gripperBadge.textContent = 'Conectado';
                gripperBadge.className = 'badge bg-success me-2';
            } else {
                serialStatus.textContent = 'Desconectado';
                serialStatus.className = 'status-disconnected';
                gripperBadge.textContent = 'Desconectado';
                gripperBadge.className = 'badge bg-danger me-2';
            }
            
            // Actualizar puerto serie si está disponible
            if (data.serial_port) {
                document.getElementById('serialPort').textContent = data.serial_port;
            }
            
            // Actualizar posición actual
            if (data.current_position) {
                currentPosition = {
                    x: data.current_position[0] || 300,
                    y: data.current_position[1] || -200,
                    z: data.current_position[2] || 500,
                    rx: data.current_position[3] || 0,
                    ry: data.current_position[4] || 0,
                    rz: data.current_position[5] || 0
                };
                updateCurrentPositionDisplay();
            }
            
            // Actualizar posiciones guardadas
            if (data.saved_positions) {
                savedPositions = data.saved_positions;
            }
        }

        // Actualizar estado del robot
        function updateRobotStatus(data) {
            if (data.position) {
                currentPosition = {
                    x: data.position[0] || 300,
                    y: data.position[1] || -200,
                    z: data.position[2] || 500,
                    rx: data.position[3] || 0,
                    ry: data.position[4] || 0,
                    rz: data.position[5] || 0
                };
                updateCurrentPositionDisplay();
            }
        }

        // Actualizar display de posición actual
        function updateCurrentPositionDisplay() {
            document.getElementById('currentX').textContent = currentPosition.x.toFixed(1);
            document.getElementById('currentY').textContent = currentPosition.y.toFixed(1);
            document.getElementById('currentZ').textContent = currentPosition.z.toFixed(1);
            document.getElementById('currentRX').textContent = currentPosition.rx.toFixed(1);
            document.getElementById('currentRY').textContent = currentPosition.ry.toFixed(1);
            document.getElementById('currentRZ').textContent = currentPosition.rz.toFixed(1);
        }

        // Agregar mensaje al log
        function addLogMessage(message, type = 'info') {
            const timestamp = new Date().toLocaleTimeString();
            displayLogEntry({
                timestamp: timestamp,
                message: message,
                type: type
            });
        }

        // Mostrar entrada de log
        function displayLogEntry(logEntry) {
            const console = document.getElementById('consoleLog');
            const logDiv = document.createElement('div');
            logDiv.className = 'log-entry';
            
            let className = 'log-info';
            switch(logEntry.type) {
                case 'action': className = 'log-action'; break;
                case 'warning': className = 'log-warning'; break;
                case 'error': className = 'log-error'; break;
            }
            
            logDiv.innerHTML = `<span class="log-timestamp">[${logEntry.timestamp}]</span> <span class="${className}">${logEntry.message}</span>`;
            console.appendChild(logDiv);
            console.scrollTop = console.scrollHeight;
        }

        // Limpiar log
        function clearLog() {
            fetch('/api/logs/clear', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('consoleLog').innerHTML = '';
                }
            });
        }

        // Variables globales para gripper
        let commandHistory = [];
        let historyIndex = -1;

        // Actualizar valores de sliders
        function updateSliderValues() {
            const forceSlider = document.getElementById('gripperForce');
            const distanceSlider = document.getElementById('gripperDistance');
            
            forceSlider.addEventListener('input', function() {
                document.getElementById('forceValue').textContent = parseFloat(this.value).toFixed(1);
            });

            distanceSlider.addEventListener('input', function() {
                document.getElementById('distanceValue').textContent = parseFloat(this.value).toFixed(1);
            });
        }

        // Mover robot a coordenadas
        function moveToCoordinates() {
            const coords = {
                x: parseFloat(document.getElementById('coordX').value) || 0,
                y: parseFloat(document.getElementById('coordY').value) || 0,
                z: parseFloat(document.getElementById('coordZ').value) || 0,
                rx: parseFloat(document.getElementById('coordRX').value) || 0,
                ry: parseFloat(document.getElementById('coordRY').value) || 0,
                rz: parseFloat(document.getElementById('coordRZ').value) || 0
            };

            const button = document.getElementById('moveBtn');
            button.disabled = true;
            button.innerHTML = '<span class="loading-spinner"></span>Moviendo...';

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
                    addLogMessage('Comando de movimiento registrado', 'action');
                } else {
                    addLogMessage(`Error en movimiento: ${data.message}`, 'error');
                }
            })
            .catch(error => {
                addLogMessage(`Error de conexión: ${error}`, 'error');
            })
            .finally(() => {
                button.disabled = false;
                button.innerHTML = '<i class="bi bi-arrow-right-circle"></i> Mover Robot';
            });
        }



        // Ir a Home
        function goHome() {
            fetch('/api/robot/home', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    addLogMessage('Robot movido a posición home', 'action');
                } else {
                    addLogMessage(`Error yendo a home: ${data.message}`, 'error');
                }
            })
            .catch(error => {
                addLogMessage(`Error: ${error}`, 'error');
            });
        }

        // Guardar posición
        function savePosition() {
            const name = document.getElementById('positionName').value;
            if (!name) {
                addLogMessage('Error: Nombre de posición requerido', 'error');
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
                    addLogMessage(`Posición "${name}" guardada`, 'action');
                    document.getElementById('positionName').value = '';
                } else {
                    addLogMessage(`Error: ${data.message}`, 'error');
                }
            });
        }

        // Cargar posición
        function loadPosition() {
            const name = document.getElementById('positionName').value;
            if (!name) {
                addLogMessage('Error: Especifica un nombre de posición', 'error');
                return;
            }

            if (savedPositions[name]) {
                const pos = savedPositions[name].coordinates;
                document.getElementById('coordX').value = pos[0];
                document.getElementById('coordY').value = pos[1];
                document.getElementById('coordZ').value = pos[2];
                document.getElementById('coordRX').value = pos[3];
                document.getElementById('coordRY').value = pos[4];
                document.getElementById('coordRZ').value = pos[5];
                addLogMessage(`Posición "${name}" cargada`, 'action');
            } else {
                addLogMessage(`Posición "${name}" no encontrada`, 'error');
            }
        }

        // Listar posiciones
        function listPositions() {
            fetch('/api/positions')
            .then(response => response.json())
            .then(positions => {
                const names = Object.keys(positions);
                if (names.length > 0) {
                    addLogMessage(`Posiciones guardadas: ${names.join(', ')}`, 'info');
                    alert('Posiciones guardadas:\\n' + names.map(name => 
                        `${name}: (${positions[name].coordinates.slice(0,3).join(', ')})`
                    ).join('\\n'));
                } else {
                    addLogMessage('No hay posiciones guardadas', 'info');
                    alert('No hay posiciones guardadas');
                }
                savedPositions = positions;
            });
        }

        // ==================== FUNCIONES DEL GRIPPER uSENSE ====================

        // Agregar mensaje a la consola del gripper
        function addGripperMessage(message, type = 'info', isResponse = false) {
            const console = document.getElementById('gripperConsole');
            const timestamp = new Date().toLocaleTimeString();
            const messageDiv = document.createElement('div');
            messageDiv.className = 'gripper-log-entry';
            
            let className = 'text-info';
            let prefix = '→';
            
            if (isResponse) {
                prefix = '←';
                className = 'text-success';
            }
            
            switch(type) {
                case 'command': className = 'text-primary'; break;
                case 'response': className = 'text-success'; break;
                case 'error': className = 'text-danger'; break;
                case 'warning': className = 'text-warning'; break;
                case 'raw': 
                    className = 'text-warning fw-bold'; 
                    prefix = '⚡'; 
                    break;
                case 'raw_response': 
                    className = 'text-success fw-bold'; 
                    prefix = '⚡←'; 
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
        function clearGripperConsole() {
            document.getElementById('gripperConsole').innerHTML = 
                '<span class="text-info">🔍 Monitor limpiado - Todas las respuestas del gripper aparecerán aquí en tiempo real</span>';
        }

        // Enviar comando específico del gripper
        function sendGripperCmd(command) {
            addGripperMessage(command, 'command');
            
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
                    if (data.response && data.response !== 'Sin respuesta') {
                        addGripperMessage(data.response, 'response', true);
                    } else {
                        addGripperMessage('Comando enviado exitosamente', 'response', true);
                    }
                } else {
                    addGripperMessage(`Error: ${data.message}`, 'error', true);
                }
                
                addLogMessage(`Comando gripper: ${command}`, 'action');
            })
            .catch(error => {
                addGripperMessage(`Error de conexión: ${error}`, 'error', true);
                addLogMessage(`Error comando gripper: ${error}`, 'error');
            });
        }

        // Control básico del gripper
        function sendGripperBasic() {
            const force = parseFloat(document.getElementById('gripperForce').value);
            const distance = parseFloat(document.getElementById('gripperDistance').value);

            fetch('/api/gripper/control', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    force: force,
                    distance: distance
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    addGripperMessage(`Control: Fuerza=${force}N, Distancia=${distance}mm`, 'command');
                    addLogMessage(`Gripper: Fuerza=${force}N, Distancia=${distance}mm`, 'action');
                } else {
                    addGripperMessage(`Error: ${data.message}`, 'error', true);
                    addLogMessage(`Error gripper: ${data.message}`, 'error');
                }
            });
        }

        function homeGripper() {
            sendGripperCmd('MOVE GRIP HOME');
        }

        function openGripper() {
            document.getElementById('gripperDistance').value = 100;
            document.getElementById('distanceValue').textContent = '100.0';
            sendGripperCmd('MOVE GRIP DIST 100.0');
        }

        function closeGripper() {
            document.getElementById('gripperDistance').value = 0;
            document.getElementById('distanceValue').textContent = '0.0';
            sendGripperCmd('MOVE GRIP DIST 0.0');
        }

        // Funciones para comandos específicos con parámetros
        function moveSteps() {
            const steps = document.getElementById('stepInput').value;
            if (!steps) {
                addGripperMessage('Error: Especifica número de pasos', 'error', true);
                return;
            }
            sendGripperCmd(`MOVE GRIP STEPS ${steps}`);
        }

        function moveDist() {
            const dist = document.getElementById('distInput').value;
            if (!dist) {
                addGripperMessage('Error: Especifica distancia en mm', 'error', true);
                return;
            }
            sendGripperCmd(`MOVE GRIP DIST ${dist}`);
        }

        function setTargetForce() {
            const force = document.getElementById('forceInput').value;
            if (!force) {
                addGripperMessage('Error: Especifica fuerza en N', 'error', true);
                return;
            }
            sendGripperCmd(`MOVE GRIP TFORCE ${force}`);
        }

        function setMotorMode() {
            const mode = document.getElementById('motorModeSelect').value;
            if (mode === '') return;
            
            const modeNames = {'0': 'Normal', '1': 'High Speed', '2': 'Precision'};
            sendGripperCmd(`CONFIG SET MOTORMODE ${mode}`);
            addGripperMessage(`Configurando modo: ${modeNames[mode]}`, 'info');
        }

        // Comando manual con historial
        function sendManualCommand() {
            const commandInput = document.getElementById('manualCommand');
            const command = commandInput.value.trim();
            
            if (!command) {
                addGripperMessage('Error: Comando vacío', 'error', true);
                return;
            }

            // Agregar al historial
            if (commandHistory.length === 0 || commandHistory[commandHistory.length - 1] !== command) {
                commandHistory.push(command);
                // Mantener solo los últimos 20 comandos
                if (commandHistory.length > 20) {
                    commandHistory.shift();
                }
                updateCommandHistory();
            }

            // Limpiar input
            commandInput.value = '';
            historyIndex = -1;

            // Enviar comando
            sendGripperCmd(command);
        }

        // Nueva función para enviar comando completamente RAW
        function sendRawCommand() {
            const commandInput = document.getElementById('manualCommand');
            const command = commandInput.value.trim();
            
            if (!command) {
                addGripperMessage('Error: Comando vacío', 'error', true);
                return;
            }

            // Agregar al historial
            if (commandHistory.length === 0 || commandHistory[commandHistory.length - 1] !== command) {
                commandHistory.push(command);
                // Mantener solo los últimos 20 comandos
                if (commandHistory.length > 20) {
                    commandHistory.shift();
                }
                updateCommandHistory();
            }

            // Limpiar input
            commandInput.value = '';
            historyIndex = -1;

            // Mostrar en consola que es comando RAW
            addGripperMessage(`RAW SOCKET: ${command}`, 'raw');
            
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
                    if (data.all_responses && data.all_responses.length > 0) {
                        // Mostrar todas las respuestas si las hay
                        data.all_responses.forEach(resp => {
                            addGripperMessage(resp, 'raw_response', true);
                        });
                    } else if (data.response && data.response !== 'Sin respuesta') {
                        addGripperMessage(data.response, 'raw_response', true);
                    } else {
                        addGripperMessage('Comando RAW enviado por socket', 'raw_response', true);
                    }
                } else {
                    addGripperMessage(`Error RAW: ${data.message}`, 'error', true);
                }
                
                addLogMessage(`Comando RAW: ${command}`, 'action');
            })
            .catch(error => {
                addGripperMessage(`Error conexión RAW: ${error}`, 'error', true);
                addLogMessage(`Error comando RAW: ${error}`, 'error');
            });
        }

        function handleCommandKeyPress(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                if (event.ctrlKey) {
                    // Ctrl+Enter = Comando RAW
                    sendRawCommand();
                } else {
                    // Enter normal = Comando normal
                    sendManualCommand();
                }
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                navigateHistory(-1);
            } else if (event.key === 'ArrowDown') {
                event.preventDefault();
                navigateHistory(1);
            }
        }

        function navigateHistory(direction) {
            if (commandHistory.length === 0) return;
            
            historyIndex += direction;
            
            if (historyIndex < -1) {
                historyIndex = -1;
            } else if (historyIndex >= commandHistory.length) {
                historyIndex = commandHistory.length - 1;
            }
            
            const commandInput = document.getElementById('manualCommand');
            
            if (historyIndex === -1) {
                commandInput.value = '';
            } else {
                commandInput.value = commandHistory[historyIndex];
            }
        }

        function updateCommandHistory() {
            const historyDiv = document.getElementById('commandHistory');
            historyDiv.innerHTML = '';
            
            // Mostrar últimos 3 comandos
            const recentCommands = commandHistory.slice(-3).reverse();
            
            recentCommands.forEach((cmd, index) => {
                const cmdSpan = document.createElement('span');
                cmdSpan.className = 'badge bg-secondary me-1 mb-1 cursor-pointer';
                cmdSpan.style.cursor = 'pointer';
                cmdSpan.textContent = cmd.length > 20 ? cmd.substring(0, 20) + '...' : cmd;
                cmdSpan.title = cmd;
                
                cmdSpan.onclick = function() {
                    const input = document.getElementById('manualCommand');
                    input.value = cmd;
                    validateCommand(); // Validar al cargar comando
                };
                
                historyDiv.appendChild(cmdSpan);
            });
            
            // Guardar historial en localStorage
            try {
                localStorage.setItem('gripperCommandHistory', JSON.stringify(commandHistory));
            } catch (e) {
                console.warn('Error guardando historial de comandos:', e);
            }
        }

        // Eventos WebSocket específicos del gripper
        function initializeGripperWebSocket() {
            // Escuchar respuestas del gripper en tiempo real
            socket.on('gripper_response', function(data) {
                addGripperMessage(data.response, 'response', true);
            });
            
            socket.on('gripper_status', function(data) {
                updateGripperStatus(data);
            });
        }

        function updateGripperStatus(data) {
            // Actualizar badge de conexión
            const badge = document.getElementById('gripperConnectionBadge');
            if (data.connected) {
                badge.textContent = `Conectado (${data.port || 'N/A'})`;
                badge.className = 'badge bg-success me-2';
            } else {
                badge.textContent = 'Desconectado';
                badge.className = 'badge bg-danger me-2';
            }
        }

        // Función auxiliar para mostrar ayuda de comandos
        function showCommandHelp() {
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
            
            addGripperMessage(helpText, 'info');
        }

        // Toggle modo de control
        function toggleControlMode() {
            const toggle = document.getElementById('controlToggle');
            const modeText = document.getElementById('controlMode');
            
            isXboxMode = !isXboxMode;
            
            const mode = isXboxMode ? 'xbox' : 'coordinates';
            
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
                    if (isXboxMode) {
                        toggle.classList.add('active');
                        modeText.textContent = 'Xbox Controller';
                    } else {
                        toggle.classList.remove('active');
                        modeText.textContent = 'Coordenadas';
                    }
                    addLogMessage(`Modo cambiado a: ${mode}`, 'action');
                }
            });
        }

        // Ejecutar rutina
        function runProgram(programNumber) {
            const programs = {
                1: 'Rutina de Calibración',
                2: 'Ciclo de Prueba',
                3: 'Posición Inicial',
                4: 'Rutina de Seguridad'
            };

            const routineName = programs[programNumber];
            
            fetch(`/api/routines/${programNumber}`, {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    addLogMessage(`Iniciando: ${routineName}`, 'action');
                } else {
                    addLogMessage(`Error en rutina: ${data.message}`, 'error');
                }
            });
        }

        // ==================== FUNCIONES WEBCAM ====================
        
        let webcamActive = false;
        
        function startWebcam() {
            fetch('/api/webcam/start', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    webcamActive = true;
                    document.getElementById('webcamStream').src = '/video_feed';
                    document.getElementById('webcamStream').style.display = 'block';
                    document.getElementById('webcamPlaceholder').style.display = 'none';
                    document.getElementById('webcamStatus').textContent = 'Conectada';
                    document.getElementById('webcamStatus').className = 'badge bg-success';
                    // Eliminado el mensaje de log de inicio
                } else {
                    addLogMessage(`Error iniciando cámara: ${data.message}`, 'error');
                }
            })
            .catch(error => {
                addLogMessage(`Error: ${error}`, 'error');
            });
        }
        
        function stopWebcam() {
            fetch('/api/webcam/stop', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                webcamActive = false;
                document.getElementById('webcamStream').style.display = 'none';
                document.getElementById('webcamPlaceholder').style.display = 'block';
                document.getElementById('webcamStatus').textContent = 'Desconectada';
                document.getElementById('webcamStatus').className = 'badge bg-secondary';
                // Eliminado el mensaje de log de parada
            })
            .catch(error => {
                addLogMessage(`Error: ${error}`, 'error');
            });
        }
        
        function capturePhoto() {
            if (!webcamActive) {
                addLogMessage('La cámara debe estar activa para capturar fotos', 'warning');
                return;
            }
            
            fetch('/api/webcam/capture', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    addLogMessage(`Foto capturada: ${data.photo_url}`, 'success');
                    // Opcional: mostrar la foto en un modal
                } else {
                    addLogMessage(`Error capturando foto: ${data.message}`, 'error');
                }
            })
            .catch(error => {
                addLogMessage(`Error: ${error}`, 'error');
            });
        }
        
        // Verificar estado de webcam periódicamente
        function updateWebcamStatus() {
            fetch('/api/webcam/status')
            .then(response => response.json())
            .then(data => {
                const isActive = data.active && data.streaming;
                if (isActive !== webcamActive) {
                    webcamActive = isActive;
                    if (isActive) {
                        document.getElementById('webcamStream').src = '/video_feed';
                        document.getElementById('webcamStream').style.display = 'block';
                        document.getElementById('webcamPlaceholder').style.display = 'none';
                        document.getElementById('webcamStatus').textContent = 'Conectada';
                        document.getElementById('webcamStatus').className = 'badge bg-success';
                    } else {
                        document.getElementById('webcamStream').style.display = 'none';
                        document.getElementById('webcamPlaceholder').style.display = 'block';
                        document.getElementById('webcamStatus').textContent = 'Desconectada';
                        document.getElementById('webcamStatus').className = 'badge bg-secondary';
                    }
                }
            })
            .catch(error => {
                // Silenciar errores de verificación de estado
            });
        }

        // Actualizar estado periódicamente
        setInterval(() => {
            if (socket && socket.connected) {
                socket.emit('request_status');
            }
            updateWebcamStatus();
        }, 5000); // Cada 5 segundos
    