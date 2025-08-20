# Imagen Python básica
FROM python:3.11-slim

# Variables útiles
ENV PYTHONUNBUFFERED=1 \
    PORT=8080

# Directorio trabajo
WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copiar aplicación
COPY . .

# Puerto para Cloud Run
EXPOSE $PORT

# Ejecutar aplicación
CMD uvicorn main:app --host 0.0.0.0 --port $PORT