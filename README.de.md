# Mealie AI Importer

> 🇬🇧 [English version](README.md)

---

## ⚠️ Hinweis zu diesem Projekt

Dies ist ein **privates Vibe-Coding-Projekt** — ich habe keine einzige Zeile Code selbst geschrieben oder gelesen, die gesamte Implementierung entstand im Dialog mit Claude (Anthropic). Daher kann ich leider keinen Support leisten, keine Fragen zur Implementierung beantworten und keine Änderungen oder Verbesserungen vornehmen.

Das Projekt darf gerne **geforkt** werden — ihr seid herzlich eingeladen, es als Ausgangsbasis für eigene Projekte zu nutzen. Pull Requests kann ich allerdings nicht annehmen.

---

## Motivation

Ich stand vor dem Problem, eine Rezeptsammlung von rund **1.000 PDF-Dateien** in [Mealie](https://mealie.io) zu überführen. Dabei habe ich schnell erkannt: Mealie spielt seine volle Stärke nur dann aus, wenn man die vielen Felder für Stamm- und Rezeptdaten **vollständig und sorgfältig pflegt** — Einzahl und Mehrzahl bei Zutaten und Einheiten, Aliasse, Kategorien, Schlagwörter, Bilder und mehr. Das für 1.000 Rezepte von Hand zu tun war schlicht unmöglich. Daher dieser Importer.

---

## Was ist der Mealie AI Importer?

Ein selbst entwickeltes Tool, das Rezepte aus **PDF-Dateien vollautomatisch** nach Mealie importiert. Es nutzt **Künstliche Intelligenz** (Claude von Anthropic) und die offizielle **Mealie REST-API**, um Zutaten, Mengen, Einheiten und Zubereitungsschritte aus dem PDF zu erkennen und mit dem Bestand abzugleichen — und befüllt dabei **sämtliche relevanten Felder**, die Mealie für eine hochwertige Rezeptdatenbank bietet.

### Was macht das besonders?

- **Vollständiger Zutatenstamm**: Für jede neue Zutat werden Einzahl, Mehrzahl und Aliasse angelegt. Das sorgt für einen möglichst **dublettenfreien Zutatenstamm** und stellt sicher, dass die Mengen-Skalierungsfunktion von Mealie auch sprachlich korrekt funktioniert ("1 Karotte" vs. "2 Karotten").
- **Vollständige Einheitenpflege**: Einheiten werden mit Einzahl, Mehrzahl und Abkürzung angelegt (z. B. "Esslöffel / Esslöffel / EL").
- **Automatische Klassifikation**: Jedes Rezept wird automatisch einer Kategorie und passenden Schlagwörtern zugeordnet.
- **Bilder**: Automatische Erkennung von Rezeptbildern im PDF, Upload eigener Bilder mit integrierter **Zuschnitt-Funktion**.
- **Original-PDF als Anhang**: Das Quell-PDF wird automatisch als Dateianhang am Rezept in Mealie gespeichert.
- **Appetitanregender Kurztext**: Claude verfasst automatisch eine ansprechende Kurzbeschreibung des Rezepts.
- **Zutatenzuordnung je Schritt**: Die KI ordnet jedem Zubereitungsschritt die verwendeten Zutaten zu — Grundlage für die Schritt-für-Schritt-Kochansicht in Mealie.
- **Vollständige Mealie-API-Integration**: Das Tool nutzt ausschließlich die offizielle Mealie REST-API.

---

## Workflow

```
📄 PDF hochladen
      ↓
🤖 KI-Analyse (Claude extrahiert alle Rezeptdaten)
      ↓
🔍 Automatischer Abgleich mit bestehenden Mealie-Daten
   (Zutaten, Einheiten, Kategorien, Schlagwörter)
      ↓
👁️ Prüfen & Feinjustieren (interaktive Oberfläche)
      ↓
✅ Übertragung nach Mealie über die offizielle API
```

Der gesamte Prozess dauert typischerweise **2–4 Minuten** pro Rezept.

---

## Kategorien & Schlagwort-System

Das Tool arbeitet mit dem Kategorien- und Schlagwort-System, das in der jeweiligen Mealie-Instanz eingerichtet ist. Die Zuordnung geschieht vollautomatisch durch die KI auf Basis der vorhandenen Optionen — es ist keine Konfiguration erforderlich.

Eine vollständige Übersicht des in diesem Projekt verwendeten Systems (Rezeptkategorien, Lebensmittelkategorien, Schlagwortgruppen) findet sich in 📄 [CATEGORIES.md](CATEGORIES.md).

---

## Analyse-Funktionen im Detail

### 1. PDF-Extraktion

Das Tool liest den **eingebetteten Text** direkt aus der PDF-Datei (durchsuchbares PDF). Es führt aktuell kein eigenes OCR durch — das PDF muss eine eingebettete Text-Schicht enthalten. Eingescannte Rezeptbücher ohne Texterkennung werden nicht unterstützt. Mehrseitige PDFs werden vollständig verarbeitet.

### 2. KI-Rezeptanalyse

Claude analysiert den extrahierten Text und erstellt die vollständige Rezeptstruktur:

- Rezepttitel, Beschreibung (appetitanregend formuliert), Portionen
- Zubereitungszeit, Vorbereitungszeit, Gesamtzeit
- Zutaten mit Mengen und Einheiten, gruppiert in Abschnitte
- Nummerierte Zubereitungsschritte
- Zuordnung von Zutaten zu den jeweiligen Zubereitungsschritten
- Rezeptnotizen und Hinweise

### 3. Food-Matcher (Zutaten-Abgleich)

Jede erkannte Zutat wird in drei Stufen mit dem bestehenden Mealie-Zutatenstamm abgeglichen:

1. **Exakter Treffer** (normalisiert): Zeichenketten-Vergleich nach Bereinigung von Qualifizierern ("frische Petersilie" → "Petersilie"), Groß-/Kleinschreibung und Klammern
2. **Semantische Shortlist**: Ein lokales Embedding-Modell (`paraphrase-multilingual-mpnet-base-v2`, ~1 GB, läuft vollständig lokal) sucht die 8 semantisch ähnlichsten Kandidaten
3. **KI-Entscheidung**: Claude wählt aus der Shortlist den besten Treffer — oder gibt keinen zurück, wenn er unsicher ist

Für **neue Zutaten** ohne Treffer schlägt die KI automatisch Einzahl, Mehrzahl, Aliasse und eine Lebensmittelkategorie vor.

### 4. Unit-Matcher (Einheiten-Abgleich)

Einheiten werden über eine kuratierte **Normalisierungstabelle** abgeglichen ("EL", "Esslöffel", "Eßlöffel" → gleiche Einheit). EL und TL werden dabei niemals verwechselt. Bei unbekannten Einheiten entscheidet die KI.

### 5. Instruktions-Zuordnung

Die KI ordnet jedem Zubereitungsschritt die verwendeten Zutaten zu — die Basis für die Schritt-für-Schritt-Kochansicht in Mealie.

### 6. Metadata-Klassifikation

Claude wählt automatisch eine **Rezeptkategorie** und passende **Schlagwörter** aus dem vorhandenen Mealie-System.

---

## Schritt "Prüfen" — Was kann man tun?

Vor der Übertragung nach Mealie bietet eine interaktive Oberfläche die Möglichkeit, alle erkannten Daten zu prüfen und anzupassen:

### Rezeptzusammenfassung
- Titel, Beschreibung, Portionsanzahl bearbeiten
- Zeiten anpassen
- Kategorie und Schlagwörter ändern

### Zutaten, Mengen & Einheiten
- Zutat einer **vorhandenen Mealie-Zutat zuordnen** (Dropdown mit allen Optionen inkl. Suchfunktion)
- Bei neuen Zutaten: **Namen, Plural, Aliasse und Kategorie** vor dem Anlegen anpassen
- Einheit ändern oder einer vorhandenen Einheit zuordnen
- Notizen zu einzelnen Zutaten hinzufügen
- Zutaten als gelöscht markieren

### Bild
- Automatisch erkanntes **Bild aus dem PDF** übernehmen
- **Eigenes Bild hochladen** (JPG, PNG, WebP, bis 20 MB)
- Integrierte **Zuschnitt-Funktion** mit frei wählbarem Ausschnitt und Zoom

### Zubereitungsschritte
- Texte der einzelnen Schritte bearbeiten
- Zutatenzuordnungen pro Schritt anpassen

---

## KI-Modelle, API & Kosten

Das Tool nutzt ausschließlich die **Anthropic Claude API** (kein OpenAI, keine anderen Anbieter).

| Verwendungszweck | Modell |
|---|---|
| Rezeptanalyse | claude-sonnet-4-6 |
| Zutaten-Matching | claude-sonnet-4-6 |
| Metadata-Klassifikation | claude-sonnet-4-6 |
| Einheiten & Wortformen | claude-haiku-4-5 |

**Kosten pro Rezept**: ca. **0,12 USD** (Stand: Juni 2026, abhängig von Rezeptlänge und Anzahl neuer Zutaten)

Das Embedding-Modell für den semantischen Zutaten-Abgleich läuft **vollständig lokal** auf dem Server — dort fallen keine laufenden Kosten an. Das Modell (~1 GB) wird beim ersten Start automatisch heruntergeladen und gecacht.

---

## Eigene Instanz betreiben

### Voraussetzungen

- Laufende **Mealie-Instanz** mit aktiviertem API-Zugang
- **Docker** und Docker Compose
- **Anthropic API Key** ([console.anthropic.com](https://console.anthropic.com))
- Server mit **x86/amd64-Architektur** (für das lokale Embedding-Modell)
- Mindestens **2 GB freier RAM** für das Embedding-Modell
- Mindestens **2 GB freier Speicherplatz** für den Modell-Cache

### Installation

**1. Repository klonen**
```bash
git clone https://github.com/frank2604/mealie-ai-importer.git
cd mealie-ai-importer
```

**2. Konfigurationsdatei anlegen**
```bash
cp config/settings.template.yaml config/settings.yaml
```

**3. Konfiguration anpassen** (`config/settings.yaml`)
```yaml
mealie:
  base_url: http://deine-mealie-instanz:9925
  token: DEIN_MEALIE_API_TOKEN

llm:
  provider: anthropic
  api_key: sk-ant-...
  model: claude-sonnet-4-6
```

Den Mealie API Token findest du in Mealie unter: *Einstellungen → Sicherheit → API-Tokens*

**4. Container starten**
```bash
docker compose up -d
```

**5. Aufrufen**

Die Oberfläche ist unter `http://localhost:8001` erreichbar.

### Wichtige Hinweise

- `config/settings.yaml` enthält sensitive Daten (API-Keys, Mealie-Token) und darf **niemals** in ein öffentliches Git-Repository eingecheckt werden. Die Datei ist bereits im `.gitignore` eingetragen.
- Beim ersten Start lädt das Tool das Embedding-Modell herunter (~1 GB). Das kann einige Minuten dauern.
- Das Tool ist für **einen gleichzeitigen Import** ausgelegt — parallele Nutzung durch mehrere Personen ist nicht vorgesehen.

### Optionaler Fernzugang (Cloudflare Tunnel + Authelia)

Für den Zugang aus dem Internet ohne Port-Freigabe am Router empfehlen sich **Cloudflare Tunnel** (kostenlos) in Kombination mit **Authelia** als Login-Schutz. Die Einrichtung ist nicht Teil dieses Projekts:

- [Cloudflare Tunnel Dokumentation](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [Authelia](https://www.authelia.com/)

---

## Sprache

Die Benutzeroberfläche ist standardmäßig auf **Deutsch** eingestellt und kann auf **Englisch** umgestellt werden. Der Import-Prozess selbst wurde jedoch ausschließlich mit deutschsprachigen Rezepten getestet.

---

## Technischer Stack

| Komponente | Technologie |
|---|---|
| Backend | Python / FastAPI |
| Frontend | TypeScript / React / Vite / Tailwind CSS |
| KI | Anthropic Claude API |
| Semantisches Matching | fastembed (ONNX, lokal) |
| Deployment | Docker / Docker Compose |
| CI/CD | GitHub Actions → GitHub Container Registry |

---

## Bekannte Einschränkungen

- **PDF-Format**: Das PDF muss eine eingebettete Text-Schicht enthalten (durchsuchbares PDF). Eingescannte Rezeptbücher ohne Texterkennung werden nicht unterstützt.
- **Sprache**: Ausschließlich mit **deutschsprachigen Rezepten** getestet. Die UI kann auf Englisch umgestellt werden, der Import in Englisch wurde jedoch nie erprobt.
- **Einzelnutzer**: Es kann immer nur **ein Import gleichzeitig** laufen.
- **Kategorien & Tags**: Das automatische Tagging basiert auf dem in der jeweiligen Mealie-Instanz eingerichteten System.

---

## Lizenz

MIT License — freie Nutzung, Modifikation und Weitergabe unter Nennung der Quelle.

---

*Erstellt mit [Claude](https://claude.ai) von Anthropic — 100 % Vibe-Coding.*
