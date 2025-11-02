# Layout-Konfiguration

Diese Datei erklärt, wie du die zentrale Layout-Konfiguration verwendest und anpasst.

## 📁 Datei: `layout.config.ts`

Alle visuellen Layout-Parameter sind hier zentral definiert.

## 🎯 Schnellstart

### Spalten-Verhältnis ändern

**Aktuell:** 60% links, 40% rechts (3fr:2fr)

⚠️ **WICHTIG:** Tailwind JIT benötigt vollständige Klassen-Namen! Dynamische Template-Strings funktionieren NICHT.

```typescript
// RICHTIG: Vollständige Klasse
gridClasses: 'grid grid-cols-1 xl:grid-cols-[3fr_2fr] gap-6 h-full min-h-0'

// FALSCH: Dynamisch generiert (funktioniert nicht!)
gridClasses: `grid grid-cols-1 xl:grid-cols-[${left}fr_${right}fr] ...`
```

**Beispiele für andere Verhältnisse:**

```typescript
// 50:50 Aufteilung
gridClasses: 'grid grid-cols-1 xl:grid-cols-[1fr_1fr] gap-6 h-full min-h-0'

// 70:30 Aufteilung
gridClasses: 'grid grid-cols-1 xl:grid-cols-[7fr_3fr] gap-6 h-full min-h-0'

// 40:60 Aufteilung (wie im HTML-Beispiel)
gridClasses: 'grid grid-cols-1 xl:grid-cols-[2fr_3fr] gap-6 h-full min-h-0'
```

### Mindestbreiten anpassen

```typescript
minWidth: {
  left: 384,   // 384px (= min-w-96 in Tailwind)
  right: 320,  // 320px (= min-w-80 in Tailwind)
}
```

**Gängige Werte:**
- 256px = min-w-64 (sehr schmal)
- 320px = min-w-80 (schmal)
- 384px = min-w-96 (mittel)
- 448px = min-w-112 (breit)

### Breakpoint ändern

Ab welcher Bildschirmbreite wird das Layout zweispaltig?

```typescript
breakpoint: 'xl'  // 1280px
```

**Verfügbare Breakpoints:**
- `'sm'` = 640px (sehr klein)
- `'md'` = 768px (mittel)
- `'lg'` = 1024px (groß)
- `'xl'` = 1280px (extra groß) ← Aktuell
- `'2xl'` = 1536px (sehr groß)

### Border-Radius ändern

```typescript
borderRadius: {
  small: 'rounded-full',   // Buttons
  medium: 'rounded-2xl',   // Karten
  large: 'rounded-3xl',    // Container
}
```

**Verfügbare Werte:**
- `'rounded'` = 4px
- `'rounded-lg'` = 8px
- `'rounded-xl'` = 12px
- `'rounded-2xl'` = 16px
- `'rounded-3xl'` = 24px
- `'rounded-full'` = vollständig rund

## 📝 Verwendung in Components

### Import

```typescript
import { layoutConfig } from "../../config/layout.config";
```

### Grid-Spalten verwenden

```typescript
const { left, right } = layoutConfig.grid.columns;
const { breakpoint, gap } = layoutConfig.grid;

const gridClasses = `grid grid-cols-1 ${breakpoint}:grid-cols-[${left}fr_${right}fr] gap-${gap} h-full min-h-0`;

return <div className={gridClasses}>...</div>;
```

### Border-Radius verwenden

```typescript
import clsx from "clsx";

<div className={clsx(
  "border border-border bg-panel",
  layoutConfig.borderRadius.large
)}>
  ...
</div>
```

## 🎨 Best Practices

1. **Ändere nur die Config-Datei** - nicht die einzelnen Components
2. **Teste nach Änderungen** alle Bildschirmgrößen
3. **Dokumentiere große Änderungen** in dieser README
4. **Verwende die Typen** für Type-Safety:
   ```typescript
   import type { BorderRadiusSize } from "./layout.config";
   ```

## 🔧 Erweitern der Config

Du kannst jederzeit neue Parameter hinzufügen:

```typescript
export const layoutConfig = {
  // Bestehende Config...

  // Neu: Animation-Timings
  animation: {
    fast: 'duration-150',
    normal: 'duration-300',
    slow: 'duration-500',
  },

  // Neu: Z-Index-Stufen
  zIndex: {
    dropdown: 'z-10',
    modal: 'z-50',
    tooltip: 'z-60',
  },
} as const;
```

## 📚 Weitere Infos

Siehe auch: `LAYOUT_FIX_DOKUMENTATION.md` für die Hintergrunde des Layout-Systems.
