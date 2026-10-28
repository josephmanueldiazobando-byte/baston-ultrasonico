# 🦯 Bastón Ultrasónico Inteligente

Bastón que detecta obstáculos con dos sensores ultrasónicos HC-SR04 (frontal e inferior) y avisa a la persona con discapacidad visual mediante vibraciones que se intensifican al acercarse. Incluye botón SOS y registro de pruebas en la nube.

**PROGRAMA SENATIC 2026 - IEM ARTEMIO MENDOZA**
Técnico en Implementación y Mantenimiento de Sistemas de Internet de las Cosas · Grupo 3147177

Slogan: *"Un paso seguro, una vida más independiente."*

## Flujo de datos
Wokwi (ESP32) → ThingSpeak (8 campos) → GitHub (este repositorio) → Streamlit (dashboard)
Aviso SOS opcional: ESP32 → bot de Telegram

## Archivos
- `app.py` – dashboard de pruebas y monitoreo en Streamlit
- `requirements.txt` – librerías de Python
- `wokwi/sketch.ino`, `wokwi/diagram.json` – simulación del ESP32

## Equipo
Josseph Díaz (líder), Alejandro Minayo, Marlon Erazo, Andres Baron.
Instructor: James Betancourt.
