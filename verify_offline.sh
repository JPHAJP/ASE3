#!/bin/bash

# Script de verificación para red aislada
# Verifica que todas las dependencias locales estén disponibles

echo "=== Verificación de configuración offline ==="
echo ""

# Función para verificar existencia de archivos
check_file() {
    if [ -f "$1" ]; then
        size=$(ls -lh "$1" | awk '{print $5}')
        echo "✓ $1 (${size})"
        return 0
    else
        echo "✗ FALTA: $1"
        return 1
    fi
}

# Verificar dependencias
echo "Verificando dependencias descargadas:"
all_good=true

check_file "static/vendor/bootstrap/bootstrap.min.css" || all_good=false
check_file "static/vendor/bootstrap/bootstrap.bundle.min.js" || all_good=false
check_file "static/vendor/bootstrap-icons/bootstrap-icons.css" || all_good=false
check_file "static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff2" || all_good=false
check_file "static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff" || all_good=false
check_file "static/vendor/socket.io/socket.io.min.js" || all_good=false

echo ""

# Verificar que los archivos HTML usen rutas locales
echo "Verificando configuración de archivos HTML:"

if grep -q 'url_for("static", filename="vendor/' templates/index.html; then
    echo "✓ index.html configurado para usar dependencias locales"
else
    echo "✗ index.html aún usa dependencias remotas"
    all_good=false
fi

if grep -q 'url_for("static", filename="vendor/' templates/index_backup.html; then
    echo "✓ index_backup.html configurado para usar dependencias locales"
else
    echo "✗ index_backup.html aún usa dependencias remotas"
    all_good=false
fi

# Verificar que no queden referencias a CDN
echo ""
echo "Verificando que no queden referencias externas:"

if grep -q "https://cdn" templates/index.html; then
    cdn_count=$(grep -c "https://cdn" templates/index.html)
    echo "✗ index.html aún tiene $cdn_count referencias a CDN"
    all_good=false
else
    echo "✓ index.html sin referencias a CDN"
fi

if grep -q "https://cdn" templates/index_backup.html; then
    cdn_count_backup=$(grep -c "https://cdn" templates/index_backup.html)
    echo "✗ index_backup.html aún tiene $cdn_count_backup referencias a CDN"
    all_good=false
else
    echo "✓ index_backup.html sin referencias a CDN"
fi

echo ""

# Resultado final
if [ "$all_good" = true ]; then
    echo "🎉 ¡CONFIGURACIÓN COMPLETA!"
    echo "La aplicación está lista para funcionar en red aislada."
    echo ""
    echo "Archivos de respaldo creados:"
    echo "- templates/index.html.backup"
    echo "- templates/index_backup.html.backup"
else
    echo "❌ Hay problemas en la configuración."
    echo "Por favor, revisa los errores arriba."
fi

echo ""
echo "Estructura de dependencias locales:"
find static/vendor -type f | sort