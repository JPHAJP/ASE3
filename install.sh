#!/bin/bash

# Script de instalación para la aplicación web de control del robot UR5e
# Autor: Sistema de Control Industrial
# Versión: 1.0

set -e  # Salir si hay algún error

echo "🤖 Instalador de la Aplicación Web UR5e Robot Controller"
echo "========================================================"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funciones auxiliares
print_step() {
    echo -e "${BLUE}[PASO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Verificar sistema operativo
check_system() {
    print_step "Verificando sistema operativo..."
    
    if [[ "$OSTYPE" != "linux-gnu"* ]]; then
        print_error "Este script está diseñado para sistemas Linux"
        print_warning "Si usas macOS o Windows, instala manualmente las dependencias"
        exit 1
    fi
    
    # Verificar distribución
    if command -v apt-get &> /dev/null; then
        PACKAGE_MANAGER="apt-get"
    elif command -v yum &> /dev/null; then
        PACKAGE_MANAGER="yum"
    elif command -v pacman &> /dev/null; then
        PACKAGE_MANAGER="pacman"
    else
        print_error "No se detectó un gestor de paquetes compatible (apt, yum, pacman)"
        exit 1
    fi
    
    print_success "Sistema Linux detectado con $PACKAGE_MANAGER"
}

# Verificar Python
check_python() {
    print_step "Verificando instalación de Python..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 no está instalado"
        print_step "Instalando Python 3..."
        
        if [ "$PACKAGE_MANAGER" = "apt-get" ]; then
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv
        elif [ "$PACKAGE_MANAGER" = "yum" ]; then
            sudo yum install -y python3 python3-pip
        fi
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d " " -f 2 | cut -d "." -f 1,2)
    print_success "Python $PYTHON_VERSION detectado"
    
    # Verificar versión mínima
    if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"; then
        print_success "Versión de Python compatible (>= 3.8)"
    else
        print_error "Se requiere Python 3.8 o superior"
        exit 1
    fi
}

# Instalar dependencias del sistema
install_system_dependencies() {
    print_step "Instalando dependencias del sistema..."
    
    if [ "$PACKAGE_MANAGER" = "apt-get" ]; then
        sudo apt-get update
        
        # Dependencias básicas
        sudo apt-get install -y \
            python3-dev \
            python3-pip \
            python3-venv \
            build-essential \
            git \
            wget \
            curl
        
        # Dependencias para Bluetooth
        sudo apt-get install -y \
            bluetooth \
            bluez \
            libbluetooth-dev \
            bluez-tools
        
        # Dependencias para matplotlib y GUI
        sudo apt-get install -y \
            python3-tk \
            python3-matplotlib \
            libfreetype6-dev \
            libpng-dev
        
        # Dependencias para pygame (Xbox controller)
        sudo apt-get install -y \
            libsdl2-dev \
            libsdl2-mixer-dev \
            libsdl2-ttf-dev \
            libsdl2-image-dev
        
        print_success "Dependencias del sistema instaladas (Ubuntu/Debian)"
        
    elif [ "$PACKAGE_MANAGER" = "yum" ]; then
        # Para CentOS/RHEL/Fedora
        sudo yum groupinstall -y "Development Tools"
        sudo yum install -y \
            python3-devel \
            bluez \
            bluez-libs-devel \
            tkinter \
            SDL2-devel \
            freetype-devel \
            libpng-devel
            
        print_success "Dependencias del sistema instaladas (CentOS/RHEL/Fedora)"
    fi
}

# Configurar entorno virtual Python
setup_python_environment() {
    print_step "Configurando entorno virtual de Python..."
    
    # Crear entorno virtual si no existe
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_success "Entorno virtual creado"
    else
        print_warning "Entorno virtual ya existe"
    fi
    
    # Activar entorno virtual
    source venv/bin/activate
    
    # Actualizar pip
    pip install --upgrade pip setuptools wheel
    
    print_success "Entorno virtual configurado y activado"
}

# Instalar dependencias Python
install_python_dependencies() {
    print_step "Instalando dependencias de Python..."
    
    # Asegurarse de estar en el entorno virtual
    source venv/bin/activate
    
    # Instalar desde requirements.txt
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        print_success "Dependencias instaladas desde requirements.txt"
    else
        print_warning "Archivo requirements.txt no encontrado, instalando manualmente..."
        
        # Instalar dependencias manualmente
        pip install \
            flask==3.0.0 \
            flask-socketio==5.3.6 \
            roboticstoolbox-python==1.1.1 \
            spatialmath-python==1.1.14 \
            ur_rtde==1.6.2 \
            pygame==2.6.1 \
            matplotlib==3.5.3 \
            numpy==1.26.4 \
            scipy==1.16.2 \
            pillow==11.3.0
        
        print_success "Dependencias Python instaladas manualmente"
    fi
}

# Configurar Bluetooth
setup_bluetooth() {
    print_step "Configurando Bluetooth..."
    
    # Verificar si el servicio Bluetooth está disponible
    if systemctl is-available bluetooth &> /dev/null; then
        # Iniciar servicio Bluetooth
        sudo systemctl start bluetooth
        sudo systemctl enable bluetooth
        
        # Verificar estado
        if systemctl is-active bluetooth &> /dev/null; then
            print_success "Servicio Bluetooth iniciado"
        else
            print_warning "No se pudo iniciar el servicio Bluetooth"
        fi
    else
        print_warning "Servicio Bluetooth no disponible"
    fi
    
    # Agregar usuario al grupo bluetooth
    sudo usermod -a -G bluetooth $USER
    print_success "Usuario agregado al grupo bluetooth"
    print_warning "Necesitarás reiniciar sesión para que los cambios tengan efecto"
}

# Crear directorios necesarios
create_directories() {
    print_step "Creando estructura de directorios..."
    
    mkdir -p static/simulations
    mkdir -p templates
    mkdir -p robot_modules
    mkdir -p logs
    
    print_success "Directorios creados"
}

# Configurar permisos
setup_permissions() {
    print_step "Configurando permisos..."
    
    # Permisos para directorios de datos
    chmod 755 static/
    chmod 755 static/simulations/
    chmod 755 logs/
    
    # Permisos para archivos ejecutables
    if [ -f "app.py" ]; then
        chmod +x app.py
    fi
    
    print_success "Permisos configurados"
}

# Verificar instalación
verify_installation() {
    print_step "Verificando instalación..."
    
    # Activar entorno virtual
    source venv/bin/activate
    
    # Verificar imports principales
    python3 -c "
import flask
import flask_socketio
import matplotlib
import pygame
import numpy
print('✓ Todas las dependencias principales se importan correctamente')
"
    
    if [ $? -eq 0 ]; then
        print_success "Verificación de dependencias completada"
    else
        print_error "Error en la verificación de dependencias"
        return 1
    fi
    
    # Verificar archivos principales
    required_files=("app.py" "robot_modules/" "templates/")
    
    for file in "${required_files[@]}"; do
        if [ -e "$file" ]; then
            print_success "✓ $file encontrado"
        else
            print_error "✗ $file no encontrado"
            return 1
        fi
    done
    
    return 0
}

# Crear script de inicio
create_startup_script() {
    print_step "Creando script de inicio..."
    
    cat > start_robot_app.sh << 'EOF'
#!/bin/bash

# Script de inicio para la aplicación web UR5e Robot Controller

echo "🤖 Iniciando aplicación web UR5e Robot Controller..."

# Cambiar al directorio de la aplicación
cd "$(dirname "$0")"

# Activar entorno virtual
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✓ Entorno virtual activado"
else
    echo "⚠ Entorno virtual no encontrado, usando Python del sistema"
fi

# Verificar que la aplicación existe
if [ ! -f "app.py" ]; then
    echo "✗ Error: app.py no encontrado"
    exit 1
fi

# Exportar variables de entorno
export FLASK_APP=app.py
export FLASK_ENV=production
export MPLBACKEND=Agg  # Para matplotlib sin display

echo "🚀 Iniciando servidor Flask..."
echo "📱 La aplicación estará disponible en: http://localhost:5000"
echo "🛑 Presiona Ctrl+C para detener"

# Iniciar aplicación
python3 app.py
EOF

    chmod +x start_robot_app.sh
    print_success "Script de inicio creado: start_robot_app.sh"
}

# Mostrar información post-instalación
show_post_install_info() {
    echo
    echo "🎉 ¡Instalación completada exitosamente!"
    echo "======================================"
    echo
    echo "📁 Archivos instalados en: $(pwd)"
    echo
    echo "🚀 Para iniciar la aplicación:"
    echo "   ./start_robot_app.sh"
    echo
    echo "🔧 O manualmente:"
    echo "   source venv/bin/activate"
    echo "   python3 app.py"
    echo
    echo "🌐 La aplicación estará disponible en:"
    echo "   http://localhost:5000"
    echo
    echo "⚙️  Configuración necesaria:"
    echo "   1. Edita app.py para configurar la IP del robot UR5e"
    echo "   2. Configura la MAC del ESP32 para el gripper Bluetooth"
    echo "   3. Empareja el ESP32 con el sistema si usas control Bluetooth"
    echo
    echo "📚 Documentación completa en README.md"
    echo
    echo "🐛 Para soporte:"
    echo "   - Revisa los logs en robot_app.log"
    echo "   - Consulta la documentación en README.md"
    echo
}

# Función principal
main() {
    echo
    print_step "Iniciando instalación automática..."
    echo
    
    # Verificar si estamos en el directorio correcto
    if [ ! -f "app.py" ] && [ ! -f "requirements.txt" ]; then
        print_error "Ejecuta este script desde el directorio raíz del proyecto"
        print_warning "Debe contener app.py y requirements.txt"
        exit 1
    fi
    
    # Ejecutar pasos de instalación
    check_system
    check_python
    install_system_dependencies
    setup_python_environment
    install_python_dependencies
    setup_bluetooth
    create_directories
    setup_permissions
    create_startup_script
    
    if verify_installation; then
        show_post_install_info
    else
        print_error "La instalación se completó pero hay errores en la verificación"
        print_warning "Revisa los mensajes anteriores y consulta README.md"
        exit 1
    fi
}

# Manejo de señales para cleanup
cleanup() {
    print_warning "Instalación interrumpida por el usuario"
    exit 1
}

trap cleanup SIGINT SIGTERM

# Verificar si se ejecuta como root (no recomendado)
if [ "$EUID" -eq 0 ]; then
    print_warning "No ejecutes este script como root (sudo)"
    print_warning "El script solicitará permisos sudo cuando sea necesario"
    exit 1
fi

# Ejecutar instalación
main "$@"