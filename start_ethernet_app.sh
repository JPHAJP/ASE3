#!/bin/bash
#
# Script de inicio para la aplicación del robot con conexiones ethernet
#

echo "============================================================"
echo "🚀 INICIANDO APLICACIÓN ROBOT UR5 CON CONEXIONES ETHERNET"
echo "============================================================"

echo ""
echo "🌐 Información de red ethernet:"
ip addr show enx68da73a62e01 | grep "inet " | awk '{print "   📍 PC: " $2}'

echo ""
echo "🔗 Configuración de dispositivos:"
echo "   📍 PC (este equipo):    192.168.0.104"
echo "   🦾 Robot UR5:           192.168.0.101"
echo "   🤖 Gripper uSENSE:      192.168.0.102"

echo ""
echo "🧪 Verificando conexiones..."

# Verificar conectividad básica
ping -c 1 -W 1 192.168.0.101 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Robot UR5 responde"
else
    echo "   ❌ Robot UR5 no responde"
fi

ping -c 1 -W 1 192.168.0.102 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Gripper uSENSE responde"
else
    echo "   ❌ Gripper uSENSE no responde"
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
echo ""

# Iniciar la aplicación
/home/jpha/Documents/O-25/ASE3/venv/bin/python app.py