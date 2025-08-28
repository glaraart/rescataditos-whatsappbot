# Imagen Python básica
FROM python:3.11-slim

# Variables útiles
ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PYTHONPATH=/app

# Instalar dependencias del sistema (si las necesitas)
# Instalar dependencias del sistema (ej. gcc si alguna lib Python lo necesita, y ffmpeg para pydub)
RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*


# Directorio trabajo
WORKDIR /app

# Copiar requirements primero (para cache de Docker)
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar aplicación
COPY . .

# Puerto para Cloud Run
EXPOSE $PORT

# Ejecutar aplicación con gunicorn (más robusto para producción)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1"]