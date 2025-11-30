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
- **visita_vet**: Información sobre visitas veterinarias  
- **gasto**: Registro de gastos relacionados a los animales
- **consulta**: Preguntas generales o información
