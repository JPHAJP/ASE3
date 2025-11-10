/**
 * Controlador de Webcam Simple
 * Script separado para manejar todas las funciones de la webcam
 */

class WebcamController {
    constructor() {
        this.socket = null;
        this.isActive = false;
        this.currentCamera = 0;
        this.init();
    }

    init() {
        // Inicializar Socket.IO
        this.socket = io();
        
        // Configurar event listeners
        this.setupEventListeners();
        this.setupSocketListeners();
        
        console.log('✅ WebcamController inicializado');
    }

    setupEventListeners() {
        // Botones de control
        const startBtn = document.getElementById('startWebcam');
        const stopBtn = document.getElementById('stopWebcam');
        const captureBtn = document.getElementById('capturePhoto');
        const switchBtn = document.getElementById('switchCamera');

        if (startBtn) {
            startBtn.addEventListener('click', () => this.startWebcam());
        }
        
        if (stopBtn) {
            stopBtn.addEventListener('click', () => this.stopWebcam());
        }
        
        if (captureBtn) {
            captureBtn.addEventListener('click', () => this.capturePhoto());
        }
        
        if (switchBtn) {
            switchBtn.addEventListener('click', () => this.switchCamera());
        }
    }

    setupSocketListeners() {
        // Escuchar respuestas del servidor
        this.socket.on('webcam_response', (data) => {
            console.log('Respuesta webcam:', data);
            
            if (data.success) {
                // Solo mostrar mensajes de error o captura de fotos, no de inicio/parada
                if (data.message.includes('capturada') || data.message.includes('Imagen')) {
                    this.showMessage(data.message, 'success');
                }
                
                // Actualizar estado de botones
                if (data.message.includes('iniciada')) {
                    this.updateButtonStates(true);
                } else if (data.message.includes('detenida')) {
                    this.updateButtonStates(false);
                }
            } else {
                // Solo mostrar errores reales
                this.showMessage(data.error || 'Error desconocido', 'error');
            }
        });

        this.socket.on('webcam_status', (status) => {
            console.log('📡 Estado webcam recibido:', status);
            this.isActive = status.is_active;
            this.currentCamera = status.camera_index;
            this.updateButtonStates(this.isActive);
            console.log('🔄 Estado actualizado - Activo:', this.isActive, 'Cámara:', this.currentCamera);
        });
    }

    startWebcam() {
        console.log('🚀 Iniciando webcam...');
        this.socket.emit('start_webcam');
        // Eliminado: this.showMessage('Iniciando cámara...', 'info');
    }

    stopWebcam() {
        console.log('🛑 Deteniendo webcam...');
        this.socket.emit('stop_webcam');
        // Eliminado: this.showMessage('Deteniendo cámara...', 'info');
    }

    capturePhoto() {
        console.log('📸 Capturando foto...');
        this.socket.emit('capture_image');
        // Solo mostrar mensaje de captura ya que es importante
        this.showMessage('Imagen capturada', 'success');
    }

    switchCamera() {
        console.log('🔄 Cambiando cámara...');
        this.socket.emit('switch_camera', {});
        // Eliminado: this.showMessage('Cambiando cámara...', 'info');
    }

    updateButtonStates(isActive) {
        const startBtn = document.getElementById('startWebcam');
        const stopBtn = document.getElementById('stopWebcam');
        const captureBtn = document.getElementById('capturePhoto');
        const switchBtn = document.getElementById('switchCamera');
        const statusElement = document.getElementById('webcamStatus');

        if (startBtn) startBtn.disabled = isActive;
        if (stopBtn) stopBtn.disabled = !isActive;
        if (captureBtn) captureBtn.disabled = !isActive;
        if (switchBtn) switchBtn.disabled = false; // Siempre habilitado

        // Actualizar estado visual
        if (statusElement) {
            statusElement.textContent = isActive ? 
                `Activa (Cámara ${this.currentCamera})` : 'Inactiva';
            statusElement.className = `badge ${isActive ? 'bg-success' : 'bg-secondary'}`;
        }

        // Actualizar stream de video
        this.updateVideoStream(isActive);
    }

    updateVideoStream(isActive) {
        const videoElement = document.getElementById('webcamStream');
        const placeholderElement = document.getElementById('webcamPlaceholder');
        
        console.log('🎥 Actualizando stream de video, activo:', isActive);
        
        if (videoElement && placeholderElement) {
            if (isActive) {
                // Mostrar video y ocultar placeholder
                console.log('📹 Mostrando video stream');
                videoElement.src = '/video_feed?' + new Date().getTime();
                videoElement.style.display = 'block';
                videoElement.style.zIndex = '10';
                placeholderElement.style.display = 'none';
            } else {
                // Ocultar video y mostrar placeholder
                console.log('🔘 Mostrando placeholder');
                videoElement.src = '';
                videoElement.style.display = 'none';
                placeholderElement.style.display = 'flex';
                placeholderElement.style.zIndex = '10';
            }
        } else {
            console.error('❌ No se encontraron elementos de video o placeholder');
        }
    }

    showMessage(message, type = 'info') {
        // Buscar contenedor de mensajes o crear uno temporal
        let messageContainer = document.getElementById('webcamMessages');
        
        if (!messageContainer) {
            // Crear contenedor temporal si no existe
            messageContainer = document.createElement('div');
            messageContainer.id = 'webcamMessages';
            messageContainer.className = 'mt-2';
            
            // Insertarlo cerca de los controles de webcam
            const webcamContainer = document.querySelector('.webcam-container') || 
                                  document.querySelector('[data-section="webcam"]') ||
                                  document.body;
            webcamContainer.appendChild(messageContainer);
        }

        // Crear elemento de mensaje
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${this.getBootstrapClass(type)} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        // Limpiar mensajes anteriores y agregar nuevo
        messageContainer.innerHTML = '';
        messageContainer.appendChild(alertDiv);

        // Auto-remover después de 5 segundos
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }

    getBootstrapClass(type) {
        const classes = {
            'success': 'success',
            'error': 'danger',
            'warning': 'warning',
            'info': 'info'
        };
        return classes[type] || 'info';
    }

    // Método público para obtener estado
    getStatus() {
        this.socket.emit('get_webcam_status');
    }

    // Método público para forzar actualización
    forceRefresh() {
        console.log('🔄 Forzando actualización de video...');
        const videoElement = document.getElementById('webcamStream');
        if (videoElement && this.isActive) {
            videoElement.src = '/video_feed?' + new Date().getTime();
            console.log('📹 Video src actualizado:', videoElement.src);
        }
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    // Verificar que Socket.IO esté disponible
    if (typeof io !== 'undefined') {
        window.webcamController = new WebcamController();
        console.log('✅ WebcamController disponible globalmente');
    } else {
        console.error('❌ Socket.IO no está disponible');
    }
});

// Exportar para uso en otros scripts si es necesario
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebcamController;
}