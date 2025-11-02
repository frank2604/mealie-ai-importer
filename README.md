# Mealie Importer

CLI-Prototyp zum Extrahieren von Rezept-Texten aus PDF-Dateien und zur Vorbereitung des Imports nach Mealie.

## Voraussetzungen
- Python 3.9+ (getestet mit 3.9.6)
- Virtuelle Umgebung aktiv (`source .venv/bin/activate`)
- Installierte Pakete:
  ```bash
  pip install pypdf pdfminer.six httpx pydantic quantulum3 rich python-dotenv pyyaml "pypdf[image]" openai
  ```

## Konfiguration
1. `cp config/settings.template.yaml config/settings.yaml`
2. Werte anpassen oder über `.env` setzen. Wichtige Variablen:
   - `MEALIE_BASE_URL`, `MEALIE_TOKEN`
   - `LLM_API_KEY` (OpenAI-Key)
   - optional `LLM_MODEL`, `LLM_VISION_MODEL` (falls ein anderes Modell fürs Zuschneiden genutzt werden soll), `LLM_TEMPERATURE` (manche Modelle erlauben nur den Default), `LLM_MAX_TOKENS` (wird als `max_completion_tokens` gesetzt; leer lassen = OpenAI-Default)
   - optional `LLM_TIMEOUT` (Sekunden, Standard 120)

Beispiel `.env`:
```
MEALIE_BASE_URL=http://192.168.2.33:9925
MEALIE_TOKEN=<token>
LLM_API_KEY=sk-...
```

## Nutzung
```bash
# Rohtext extrahieren
python -m importer extract PDFs/Asia-Gemuese-Suppe.pdf

# Heuristischer Parser (nur Fallback)
python -m importer parse PDFs/Asia-Gemuese-Suppe.pdf --json data/asia-simple.json

# LLM-Parser (empfohlen)
python -m importer parse-llm "PDFs/Frühlingsragout mit Hähnchen.pdf" --json data/fruehling-llm.json

# Mealie-Export (aus vorhandener JSON)
python -m importer export-mealie data/fruehling-llm.json --output data/mealie/fruehling.json

# Direkt nach Mealie hochladen (nutzt .env-Konfiguration)
python -m importer upload data/fruehling-llm.json
```

`parse-llm` benötigt eine gültige Konfiguration und einen OpenAI-Key. Beide Parser versuchen, das größte PDF-Bild als JPEG unter `data/pipeline/` abzulegen und ergänzen das JSON um ein Base64-Asset (`assets[*].data`). Wenn ein Vision-Modell (`LLM_VISION_MODEL`) konfiguriert ist, wird der Bildausschnitt automatisch auf das Gericht zugeschnitten. Beim Upload werden Einheiten, Lebensmittel und Kategorien in Mealie angelegt (inkl. 90 %-Fuzzy-Matching) und als Smart Ingredients mit Mengen hinterlegt; das Bild wird als Asset geladen und als Feature gesetzt.

## Status & nächste Schritte
- LLM-Pipeline liefert strukturierte Rezepte (Smart Ingredients, Schritte, Metadaten).
- API-Upload (`upload`) ist vorhanden; langfristig Zutaten-/Einheiten-Deduplikation und OCR als Ausbaustufe.
- Tests und Prompt-Finetuning anhand weiterer PDFs empfehlenswert.

## Ordnerstruktur
```
importer/
  cli.py             # CLI-Einstieg
  config.py          # YAML/.env-Konfiguration
  llm_parser.py      # OpenAI-Anbindung
  pdf_extractor.py   # PDF-Text + Bilder
  simple_parser.py   # Heuristischer Fallback
  models.py          # Datenmodelle
config/settings.template.yaml
```

---

## Mealie AI-Importer UI (Vite + React)

Das neue UI-Frontend liegt im Repository-Wurzelverzeichnis und kann unabhängig vom Python-Importer betrieben werden.

### Entwicklung starten
```bash
npm install
npm run dev
```
Der Dev-Server läuft standardmäßig auf `http://localhost:5173` und bietet Hot Module Reloading. Die Sprache kann oben rechts zwischen Deutsch und Englisch gewechselt werden; Themes werden per CSS-Variablen umgesetzt.

### Production-Build
```bash
npm run build
npm run preview
```
Der Build landet unter `dist/` und kann via `npm run preview` lokal geprüft werden.

### Docker
```bash
docker build -t mealie-ai-importer-ui .
docker run -p 8080:80 mealie-ai-importer-ui
```
Alternativ steht ein einfaches `docker-compose.yml` bereit:
```bash
docker compose up --build
```
Die bereitgestellte `nginx.conf` aktiviert Gzip und setzt CORS-Header ausschließlich für statische Assets (`/assets/`).

### Architektur & i18n
- React Router steuert den Vier-Schritte-Wizard (`/`, `/analyze`, `/review`, `/transfer`) sowie `/settings`.
- Tailwind nutzt ausschließlich CSS-Variablen aus `src/theme/theme.css`, womit Light/Dark Themes abgebildet werden.
- Sämtliche UI-Texte liegen in `src/i18n/locales/{de,en}/common.json` und werden via `i18next` geladen.
- Dummy-Daten (Logs, Tabellen, Platzhalter) sind internationalisiert und folgen den Mockups im Ordner `docs/`.
