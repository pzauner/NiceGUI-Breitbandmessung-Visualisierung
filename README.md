# Breitbandmessung Visualisierung

Eine moderne Web-Anwendung zur Visualisierung und Analyse von Breitbandmessungsdaten mit NiceGUI.

## Installation (lokal)

```bash
# Abhängigkeiten installieren
uv sync

# Anwendung starten (lokal)
uv run main.py
```

## Verwendung

Die Anwendung ist unter `http://localhost:9191` erreichbar (konfigurierbar via `config.yaml`).

### Konfiguration

Die Datei `config.yaml` enthält zentrale Einstellungen:

```yaml
data:
  # Pfad zu den Messprotokollen (z. B. gemountetes Verzeichnis im Container)
  measurements_path: "/storage/data/messprotokolle"

ui:
  title: "Breitbandmessung Visualisierung"
  port: 9191
  host: "0.0.0.0"

plot:
  limit: 100
  figsize: [12, 5]
  update_every: 1
```

### CSV-Format

Messdateien müssen dem Pattern `Breitbandmessung_DD_MM_YYYY_HH_MM_SS.csv` entsprechen und folgendes Format haben:

```csv
"Messzeitpunkt";"Download (Mbit/s)";"Upload (Mbit/s)";"Laufzeit (ms)";"Test-ID";"Version";"Betriebssystem";"Internet-Browser";"Uhrzeit"
"13.05.2025";"94,73";"90,59";"8";"test-id";"4.49";"Linux";"Chrome";"01:00:46"
```

## Features

- 📊 Line Plots für Download, Upload und Ping
- 🔍 AGGrid mit Filtern und Multi-Select
- 📈 Statistiken (Gesamt & Auswahl)
- 💾 Export (PDF mit Markdown-Formatierung oder CSV)
- 🔄 Neuladen von CSV-Dateien
- 🎨 Responsive UI
- 🛡️ BNetzA-Check inkl. PDF-Export

## Deployment mit Docker Compose

### 1) Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Systemabhängigkeiten für matplotlib/reportlab
RUN apt-get update && apt-get install -y \
    build-essential \
    libfreetype6-dev \
    libpng-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# Projektdateien
COPY pyproject.toml /app/
COPY README.md /app/
COPY main.py /app/
COPY config.yaml /app/

# Python-Dependencies installieren
RUN pip install --no-cache-dir uv && \
    uv pip install --system .

# Exponierter Port (entsprechend config.yaml ui.port)
EXPOSE 9191

# Startkommando
CMD ["python", "main.py"]
```

Hinweis: Falls du zusätzliche Dateien/Ordner (z. B. `sample/`) nutzt, ergänze entsprechende COPY-Zeilen.

### 2) docker-compose.yml

```yaml
version: "3.9"
services:
  app:
    build: .
    container_name: breitband-app
    restart: unless-stopped
    ports:
      - "9191:9191"  # host:container, muss mit config.yaml ui.port übereinstimmen
    environment:
      - PYTHONUNBUFFERED=1
      - MPLBACKEND=Agg
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - /storage/data/messprotokolle:/storage/data/messprotokolle:ro  # Pfad mit Mess-CSV (anpassen)
```

### 3) Start

```bash
docker compose build
docker compose up -d
```

Danach ist die App unter `http://localhost:9191` erreichbar.

### 4) Quickstart

Variante A (empfohlen): Repository klonen und starten

```bash
git clone https://github.com/pzauner/NiceGUI-Breitbandmessung-Visualisierung.git
cd NiceGUI-Breitbandmessung-Visualisierung
# Optional: config.yaml anpassen
docker compose up -d --build
```

Variante B: Einzelne Dateien per curl/wget laden und starten (benötigt Dockerfile & Quellcode)

```bash
# Projektverzeichnis anlegen
mkdir -p NiceGUI-Breitbandmessung-Visualisierung && cd $_

# docker-compose & Dockerfile & Konfiguration laden
curl -fsSL -o docker-compose.yml \
  https://raw.githubusercontent.com/pzauner/NiceGUI-Breitbandmessung-Visualisierung/main/docker-compose.yml
curl -fsSL -o Dockerfile \
  https://raw.githubusercontent.com/pzauner/NiceGUI-Breitbandmessung-Visualisierung/main/Dockerfile
curl -fsSL -o config.yaml \
  https://raw.githubusercontent.com/pzauner/NiceGUI-Breitbandmessung-Visualisierung/main/config.yaml

# Quellcode (main.py, pyproject.toml) laden
curl -fsSL -o main.py \
  https://raw.githubusercontent.com/pzauner/NiceGUI-Breitbandmessung-Visualisierung/main/main.py
curl -fsSL -o pyproject.toml \
  https://raw.githubusercontent.com/pzauner/NiceGUI-Breitbandmessung-Visualisierung/main/pyproject.toml

# Optional: README für Referenz
curl -fsSL -o README.md \
  https://raw.githubusercontent.com/pzauner/NiceGUI-Breitbandmessung-Visualisierung/main/README.md

# Starten
docker compose up -d --build
```

Quell-Repository dieser App: [`pzauner/NiceGUI-Breitbandmessung-Visualisierung`](https://github.com/pzauner/NiceGUI-Breitbandmessung-Visualisierung)

### CSV-Quelle / Messdaten

Diese Visualisierung arbeitet mit CSV-Dateien aus diesem Projekt: [`fabianbees/breitbandmessung-docker`](https://github.com/fabianbees/breitbandmessung-docker).

- Stelle sicher, dass die erzeugten CSVs im Host-Dateisystem liegen und per Volume in den Container gemountet werden (Standard in dieser App: `/storage/data/messprotokolle`).
- Dateinamensmuster laut Vorgabe: `Breitbandmessung_DD_MM_YYYY_HH_MM_SS.csv`.

Beispiel (Volume-Mount in `docker-compose.yml` dieser App):

```yaml
services:
  app:
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - /pfad/zu/deinen/csvs:/storage/data/messprotokolle:ro
```

## Projekt mit uv & pyproject.toml

Das Projekt nutzt:
- **uv**: Moderner Python Package Manager
- **pyproject.toml**: Projekt-Konfiguration (PEP 621)

```bash
# Neue Abhängigkeit hinzufügen
uv add <paketname>

# Direkt starten
uv run main.py
```

Dokumentation: https://docs.astral.sh/uv/

## Hinweise zu URLs

Die verfügbaren URLs der NiceGUI-App sind zur Laufzeit über `from nicegui import app` per `app.urls` abrufbar. Beispiel:

```python
from nicegui import app, ui

@ui.page('/')
def index():
    for url in app.urls:
        ui.link(url, target=url)

ui.run(host='0.0.0.0', port=9191, title='Breitbandmessung Visualisierung')
```
