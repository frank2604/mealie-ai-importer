# Mealie AI Importer

Frontend + Backend, um Rezepte per LLM aufzubereiten und in Mealie zu importieren.

## Inhalte
- **Backend**: FastAPI (importer/server.py), ruft LLMs an, schreibt Pipeline-/Review-Dateien und überträgt nach Mealie.
- **Frontend**: Vite/React (src/), Vier-Schritte-Wizard + Einstellungen.
- **Prompts**: `config/prompts.json` (mehrsprachig, mit LLM-Parametern pro Modul).
- **Konfig**: `config/settings.yaml` (lokal, nicht commiten – nutze Vorlage `config/settings.template.yaml`).

## Lokale Entwicklung
- Voraussetzungen: Node 20, Python 3.11.
- Frontend dev: `npm install && npm run dev` (http://localhost:5173)
- Backend dev: `python3 -m uvicorn importer.server:app --reload` (http://127.0.0.1:8000)

## Docker
- Compose (API + UI):
  ```bash
  docker-compose build
  docker-compose up -d
  ```
  - API: Port 8000
  - UI: Port 8080
- Wichtige Mounts/Volumes:
  - `config/settings.yaml` (eigene Kopie aus `config/settings.template.yaml`)
  - `config/prompts.json` (Prompt-Konfiguration)
  - `data/` (Cache, Pipeline, Archive, Uploads)
- Images aus GHCR: Workflow `.github/workflows/docker.yml` baut/pusht `ghcr.io/<repo>`.

## Dateien & Ignore
- `.gitignore`: schließt `config/settings.yaml`, `data/`, `node_modules/`, Build-/Cache-Dateien aus.
- `.dockerignore`: schließt lokale Artefakte beim Image-Build aus.

## Start-Hinweise
- Settings befüllen: `cp config/settings.template.yaml config/settings.yaml` und eigene Werte setzen.
- Prompts anpassen: `config/prompts.json` (UI erlaubt Bearbeitung).
- Persistenz: `data/` als Volume mounten, wenn Laufdaten/Archive erhalten bleiben sollen.

## Lizenz
MIT (falls nicht anders vereinbart)
