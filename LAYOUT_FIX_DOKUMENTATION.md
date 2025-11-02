# Layout-Fix Dokumentation für Step3Review

## Datum: 2025-11-01

## Problem
Das zweispaltige Layout in `Step3Review.tsx` hatte kein korrektes Scroll-Verhalten:
- Spalten liefen über den unteren Rand hinaus
- Keine unabhängigen Scrollbalken in den Spalten
- Inkonsistente Höhen

## Lösung
Die Layout-Struktur wurde an das funktionierende HTML-Beispiel aus dem Lernprojekt angepasst.

## Änderungen in Step3Review.tsx

### 1. Haupt-Container (Zeile 125)
**Vorher:**
```tsx
<div className="flex min-h-0 flex-1 gap-6">
```

**Nachher:**
```tsx
<div className="grid grid-cols-1 xl:grid-cols-[2fr_3fr] gap-6 h-full min-h-0">
```

**Warum:**
- `grid` statt `flex` für bessere Spalten-Kontrolle
- `grid-cols-[2fr_3fr]` = 40:60 Verhältnis mit automatischer Gap-Berechnung
- `h-full min-h-0` = volle Höhe mit korrektem Overflow-Verhalten
- `xl:grid-cols-[2fr_3fr]` = erst ab XL-Breakpoint zweispaltig

### 2. Linke Spalte (Zeile 127)
**Vorher:**
```tsx
<div className="flex min-h-0 flex-1 flex-col overflow-hidden ...">
```

**Nachher:**
```tsx
<div className="flex min-h-0 flex-col overflow-hidden ... h-full">
```

**Warum:**
- `h-full` hinzugefügt für volle Grid-Höhe
- `flex-1` entfernt (nicht nötig bei Grid)
- Rest bleibt gleich (overflow-hidden ist korrekt, da das innere div den scroll hat)

### 3. Rechte Spalte (Zeile 353)
**Vorher:**
```tsx
<aside className="hidden min-h-0 w-[420px] xl:block">
  <div className="flex h-full flex-col">
    <PdfViewerPlaceholder />
  </div>
</aside>
```

**Nachher:**
```tsx
<aside className="hidden min-h-0 xl:flex xl:flex-col h-full">
  <PdfViewerPlaceholder />
</aside>
```

**Warum:**
- `w-[420px]` entfernt - Grid übernimmt die Breitensteuerung (3fr)
- `xl:flex xl:flex-col` statt `xl:block` für bessere Höhenkontrolle
- Wrapper-div entfernt (unnötig)
- `h-full` hinzugefügt

## Die Layout-Hierarchie (wie im HTML-Beispiel)

```
App.tsx: <main> (flex flex-col, flex-1, overflow-hidden)
  └── Step3Review (grid, h-full, min-h-0)
       ├── Linke Spalte (flex flex-col, h-full)
       │    └── Scroll-Container (flex-1, overflow-y-auto) ← Scrollt hier!
       │         └── Inhalt
       └── Rechte Spalte (flex flex-col, h-full)
            └── PdfViewerPlaceholder (flex flex-col, h-full)
```

## Wichtige CSS-Konzepte

### `fr`-Einheiten im Grid
- `2fr_3fr` = 40:60 Verhältnis
- Browser rechnet automatisch den `gap` ab
- Besser als Prozente, da kein Überlauf möglich

### `min-h-0`
- Wichtig für Flexbox/Grid Overflow-Verhalten
- Erlaubt Kindern, kleiner als ihr Inhalt zu werden
- Notwendig für funktionierende Scrollbars

### `h-full`
- 100% der Elternhöhe
- Muss in der gesamten Kette gesetzt sein

### `overflow-y-auto`
- Scrollbalken nur wenn nötig
- Muss auf dem Element sein, das scrollen soll (nicht auf dem Parent!)

## Backup
Eine Backup-Datei wurde erstellt:
`/Users/frank/Documents/Entwicklung/mealie-ai-importer/src/app/routes/Step3Review.tsx.backup`

## Zum Testen
1. Dev-Server starten: `npm run dev`
2. Zu Step 3 "Prüfen" navigieren
3. Prüfen:
   - ✅ Linke Spalte scrollt unabhängig
   - ✅ Rechte Spalte (PDF-Viewer) bleibt fix
   - ✅ Beide Spalten gleiche Höhe
   - ✅ Kein Überlauf über unteren Rand
   - ✅ Padding bleibt erhalten
   - ✅ Bei schmalem Fenster: einspaltig

## Falls Probleme auftreten
Zurück zur Backup-Version:
```bash
cp /Users/frank/Documents/Entwicklung/mealie-ai-importer/src/app/routes/Step3Review.tsx.backup /Users/frank/Documents/Entwicklung/mealie-ai-importer/src/app/routes/Step3Review.tsx
```

## Weitere Änderung: Footer von `fixed` zu normalem Layout

### Problem mit `fixed` Footer
Der Footer war ursprünglich `position: fixed`, was bedeutete:
- Schwebt über dem Content
- Nimmt keinen Platz im Layout ein
- Erfordert manuelles `padding-bottom` im Main
- Kann Content überdecken

### Lösung: Flexbox-Layout (wie im HTML-Beispiel)

**StickyFooter.tsx (Zeile 17):**
```tsx
// VORHER:
<footer className="fixed inset-x-0 bottom-0 border-t border-border bg-panel/95 backdrop-blur">

// NACHHER:
<footer className="border-t border-border bg-panel/95 backdrop-blur">
```

**App.tsx (Zeile 113):**
```tsx
// pb-24 zurück zu pb-6 (nicht mehr nötig)
<main className="... pb-6 ...">
```

### Neue Layout-Struktur in App.tsx:
```
<div className="flex h-screen flex-col"> (Zeile 55)
  ├── Header (sticky, feste Höhe)
  ├── Main (flex-1, wächst/schrumpft)
  │    └── Step3Review (h-full)
  └── Footer (feste Höhe) ← Nimmt jetzt Platz im Layout ein!
```

## Zentrale Layout-Config

### Neue Datei: `src/config/layout.config.ts`

Alle Layout-Parameter sind jetzt zentral konfigurierbar:

```typescript
export const layoutConfig = {
  grid: {
    columns: {
      left: 3,   // 60% (3 von 5 Teilen)
      right: 2,  // 40% (2 von 5 Teilen)
    },
    minWidth: {
      left: 384,   // 384px Mindestbreite
      right: 320,  // 320px Mindestbreite
    },
    gap: 6,        // 1.5rem (24px)
    breakpoint: 'xl',  // Ab 1280px zweispaltig
  },
  borderRadius: {
    small: 'rounded-full',
    medium: 'rounded-2xl',
    large: 'rounded-3xl',
  },
  // ... weitere Parameter
}
```

### Verwendung in Step3Review.tsx

```typescript
import { layoutConfig } from "../../config/layout.config";

// Im Component:
const { left, right } = layoutConfig.grid.columns;
const gridClasses = `grid grid-cols-1 xl:grid-cols-[${left}fr_${right}fr] gap-6 h-full min-h-0`;
```

### Vorteile

✅ Zentrale Wartung aller Layout-Parameter
✅ Einfache Anpassung des Spalten-Verhältnisses
✅ Konsistenz über das gesamte Projekt
✅ Type-Safety durch TypeScript

## Gelernte Prinzipien aus dem HTML-Beispiel
1. **Grid mit fr-Einheiten** ist besser als flex mit festen Breiten
2. **Höhen-Kette**: h-full muss durchgängig gesetzt sein
3. **min-h-0**: Kritisch für Flexbox/Grid mit Overflow
4. **overflow-y-auto**: Am richtigen Element (das scrollen soll, nicht am Parent)
5. **Flexbox für vertikale Layouts**: flex flex-col für Header/Content/Footer-Struktur
6. **Kein `position: fixed`**: Besser normales Flexbox-Layout verwenden
7. **Zentrale Config-Datei**: Alle Layout-Parameter an einem Ort verwalten
