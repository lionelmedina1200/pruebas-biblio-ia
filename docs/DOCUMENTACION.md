# 🛠️ Documentación Técnica - Biblioteca IA

## 1. Descripción General
Biblioteca IA es una aplicación web de gestión bibliotecaria que utiliza **Flask** para el backend y **Groq API (Llama-3.1)** para procesar el lenguaje natural. La aplicación está diseñada para desplegarse en **Render** utilizando una base de datos local **SQLite**.

## 2. Tecnologías Utilizadas
*   **Backend:** Python 3.11+, Flask.
*   **Frontend:** HTML5, CSS3, JavaScript (Vanilla).
*   **Base de Datos:** SQLite (persistencia local).
*   **IA/ML:** Groq API (Modelo `llama-3.1-8b-instant`).
*   **Despliegue:** Render (Web Service).
*   **Control de Versiones:** Git / GitHub.

## 3. Estructura del Proyecto

```text
├── app.py                  # Aplicación principal Flask y rutas
├── ai_engine.py            # Lógica de integración con Groq y búsqueda
├── database.py             # Conexión a base de datos SQLite
├── cargar_mis_libros.py    # Script para importar libros desde Excel
├── requirements.txt        # Dependencias del proyecto
├── Procfile                # Configuración para Gunicorn en Render
├── libros.xlsx             # Archivo fuente de datos
├── static/                 # Archivos estáticos (CSS, JS, imágenes)
└── templates/              # Plantillas HTML (Jinja2)