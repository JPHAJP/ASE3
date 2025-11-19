#!/bin/bash
#
# Script de inicio actualizado para UR5e con RTDE
# Configurado para la IP 192.168.0.101
#

echo "============================================================"
echo "🚀 INICIANDO APLICACIÓN ROBOT UR5e CON RTDE ACTIVADO"
echo "============================================================"

echo ""
echo "🌐 Información de red ethernet:"
ip addr show enx68da73a62e01 | grep "inet " | awk '{print "   📍 PC: " $2}' 2>/dev/null || echo "   📍 PC: Verificar interfaz de red"

echo ""
echo "🔗 Configuración de dispositivos:"
echo "   📍 PC (este equipo):    192.168.0.104"
echo "   🤖 Robot UR5e (RTDE):   192.168.0.101"
echo "   🤖 Gripper uSENSE:      192.168.0.102"

echo ""
echo "🧪 Verificando conexiones..."

# Verificar conectividad básica
ping -c 1 -W 1 192.168.0.101 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Robot UR5e responde"
else
    echo "   ❌ Robot UR5e no responde"
fi

ping -c 1 -W 1 192.168.0.102 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Gripper uSENSE responde"
else
    echo "   ❌ Gripper uSENSE no responde"
fi

echo ""
echo "🔧 Verificando RTDE..."
# Test rápido de RTDE
if /home/jpha/Documents/O-25/ASE3/venv/bin/python -c "
import sys
sys.path.append('/home/jpha/Documents/O-25/ASE3')
from robot_modules.ur5_controller import UR5WebController
controller = UR5WebController('192.168.0.101')
print('✅ RTDE operacional' if controller.is_connected() else '⚠️ RTDE en modo desconectado')
print('🎮 Control disponible' if controller.can_control() else '📖 Solo modo lectura')
" 2>/dev/null; then
    echo "   🎯 Test RTDE completado"
else
    echo "   ⚠️ Error en test RTDE"
fi

echo ""
echo "🚀 Iniciando aplicación web..."
echo "   📂 Directorio: $(pwd)"
echo "   🐍 Python: $(/home/jpha/Documents/O-25/ASE3/venv/bin/python --version)"
echo ""

# Activar entorno virtual e iniciar aplicación
export FLASK_APP=app.py
export FLASK_ENV=development
export FLASK_DEBUG=1

echo "🌐 La aplicación estará disponible en:"
echo "   http://localhost:5000"
echo "   http://192.168.0.104:5000 (desde otros dispositivos en la red)"
echo ""
echo "📋 Para detener la aplicación: Ctrl+C"
echo "💡 RTDE está configurado para IP: 192.168.0.101"
echo ""

# Iniciar la aplicación
/home/jpha/Documents/O-25/ASE3/venv/bin/python app.py