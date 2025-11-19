#!/bin/bash

# Script para descargar dependencias externas y hacer la aplicación completamente offline
# Autor: Asistente de GitHub Copilot
# Fecha: $(date)

echo "=== Descargando dependencias para red aislada ==="

# Crear directorios si no existen
mkdir -p static/vendor/bootstrap
mkdir -p static/vendor/bootstrap-icons
mkdir -p static/vendor/socket.io

# Descargar Bootstrap CSS 5.3.0
echo "Descargando Bootstrap CSS 5.3.0..."
wget -O static/vendor/bootstrap/bootstrap.min.css \
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"

# Descargar Bootstrap JS 5.3.0
echo "Descargando Bootstrap JS 5.3.0..."
wget -O static/vendor/bootstrap/bootstrap.bundle.min.js \
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"

# Descargar Bootstrap Icons 1.7.2
echo "Descargando Bootstrap Icons 1.7.2..."
wget -O static/vendor/bootstrap-icons/bootstrap-icons.css \
    "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css"

# Descargar las fuentes de Bootstrap Icons
echo "Descargando fuentes de Bootstrap Icons..."
mkdir -p static/vendor/bootstrap-icons/fonts

# Extraer las URLs de las fuentes del archivo CSS
wget -q -O - "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css" | \
grep -o 'https://[^)]*\.woff2\?' | while read url; do
    filename=$(basename "$url")
    echo "Descargando fuente: $filename"
    wget -O "static/vendor/bootstrap-icons/fonts/$filename" "$url"
done

# Actualizar las rutas en el CSS de Bootstrap Icons
sed -i 's|https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/fonts/|./fonts/|g' \
    static/vendor/bootstrap-icons/bootstrap-icons.css

# Descargar Socket.IO 4.0.0
echo "Descargando Socket.IO 4.0.0..."
wget -O static/vendor/socket.io/socket.io.min.js \
    "https://cdn.socket.io/4.0.0/socket.io.min.js"

echo ""
echo "=== Descarga completada ==="
echo "Las siguientes dependencias han sido descargadas:"
echo "- Bootstrap CSS: static/vendor/bootstrap/bootstrap.min.css"
echo "- Bootstrap JS: static/vendor/bootstrap/bootstrap.bundle.min.js"
echo "- Bootstrap Icons CSS: static/vendor/bootstrap-icons/bootstrap-icons.css"
echo "- Bootstrap Icons Fonts: static/vendor/bootstrap-icons/fonts/"
echo "- Socket.IO: static/vendor/socket.io/socket.io.min.js"
echo ""
echo "Ahora actualizando los archivos HTML para usar las dependencias locales..."

# Crear copias de respaldo
cp templates/index.html templates/index.html.backup
cp templates/index_backup.html templates/index_backup.html.backup

# Actualizar index.html
sed -i 's|https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css|{{ url_for("static", filename="vendor/bootstrap/bootstrap.min.css") }}|g' templates/index.html
sed -i 's|https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css|{{ url_for("static", filename="vendor/bootstrap-icons/bootstrap-icons.css") }}|g' templates/index.html
sed -i 's|https://cdn.socket.io/4.0.0/socket.io.min.js|{{ url_for("static", filename="vendor/socket.io/socket.io.min.js") }}|g' templates/index.html
sed -i 's|https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js|{{ url_for("static", filename="vendor/bootstrap/bootstrap.bundle.min.js") }}|g' templates/index.html

# Actualizar index_backup.html
sed -i 's|https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css|{{ url_for("static", filename="vendor/bootstrap/bootstrap.min.css") }}|g' templates/index_backup.html
sed -i 's|https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css|{{ url_for("static", filename="vendor/bootstrap-icons/bootstrap-icons.css") }}|g' templates/index_backup.html
sed -i 's|https://cdn.socket.io/4.0.0/socket.io.min.js|{{ url_for("static", filename="vendor/socket.io/socket.io.min.js") }}|g' templates/index_backup.html
sed -i 's|https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js|{{ url_for("static", filename="vendor/bootstrap/bootstrap.bundle.min.js") }}|g' templates/index_backup.html

echo "Archivos HTML actualizados para usar dependencias locales."
echo "Se han creado copias de respaldo con extensión .backup"
echo ""
echo "=== Configuración completa ==="
echo "La aplicación ahora funcionará completamente en red aislada."