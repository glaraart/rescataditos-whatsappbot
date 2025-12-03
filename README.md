# 🐾 Chatbot 101 Rescataditos WhatsApp

Sistema para registrar las actividades realizadas por las rescatistas a traves de WhatsApp usando IA.

## 🚀 Funcionalidades

- **📱 Webhook WhatsApp**: Recibe mensajes de texto, audio e imágenes
- **🤖 Análisis IA**: Clasifica automáticamente mensajes usando OpenAI
- **☁️ Google Drive**: Almacenamiento de archivos multimedia
- **📊 Postgres (psycopg2)**: Registro persistente en base de datos Postgres
- **⚡ FastAPI**: API REST asíncrona y rápida

## 🏗️ Arquitectura

```
WhatsApp → Webhook → MessageHandler → [AIService, PostgresService, DriveService] → Respuesta automática
```

## 📦 Tecnologías

- **Framework**: FastAPI + Uvicorn
- **IA**: OpenAI GPT-5.1 + Whisper
 - **Storage**: Postgres (psycopg2) + Google Drive
- **Deploy**: Google Cloud Run
- **Language**: Python 3.11


## 📋 Tipos de Mensaje Soportados

- **nuevo_rescate**: Reportes de animales rescatados
- **cambio_estado**: Actualizaciones de estado de animales
- **veterinaria**: Visitas veterinarias + gastos veterinarios (consultas, cirugías, medicamentos)
- **gasto**: Registro de gastos NO veterinarios (alimento, limpieza, transporte, donaciones, etc.)
- **tracking_movimiento**: Salidas y regresos de animales (parque, veterinaria, compras, entregas en adopción)
- **consulta**: Preguntas generales o información

### ✨ Clasificación Múltiple

El sistema puede detectar **múltiples intenciones** en un solo mensaje:
- "Volvimos del parque, recibimos $5000" → `tracking_movimiento` + `gasto`
- "Rescatamos un perro, gastamos $800 en transporte" → `nuevo_rescate` + `gasto`

Cada tipo se procesa secuencialmente con su propia confirmación.
