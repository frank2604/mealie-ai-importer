/**
 * Zentrale Layout-Konfiguration
 *
 * Struktur:
 * - common: Projekt-weite Einstellungen (Border-Radius, Spacing, Shadows, etc.)
 * - step1, step2, step3, step4: Step-spezifische Layout-Konfigurationen
 */

export const layoutConfig = {
  // ============================================================================
  // ALLGEMEINE KONFIGURATION (Projekt-weit)
  // ============================================================================

  /**
   * Border-Radius für abgerundete Ecken
   * Wird in allen Steps verwendet
   *
   * Mögliche Werte:
   * - 'rounded-none'   : Keine Abrundung (eckig)
   * - 'rounded-sm'     : Sehr kleine Abrundung (2px)
   * - 'rounded'        : Kleine Abrundung (4px)
   * - 'rounded-md'     : Mittlere Abrundung (6px)
   * - 'rounded-lg'     : Große Abrundung (8px)
   * - 'rounded-xl'     : Sehr große Abrundung (12px)
   * - 'rounded-2xl'    : Extra große Abrundung (16px)
   * - 'rounded-3xl'    : Maximale Abrundung (24px)
   * - 'rounded-full'   : Vollständig abgerundet (Kreis/Pille)
   */
  borderRadius: {
    /** Kleine interaktive Elemente: Buttons, Badges, kleine Input-Felder, Status-Tags, Step-Nummern, Icon-Container */
    small: 'rounded-full',
    /** Normale Karten/Panels: Content-Karten, Input-Felder, Dropdown-Listen, Preview-Boxen */
    medium: 'rounded-xl',
    /** Große Container: Hauptcontainer, Modals, große Panels, PDF-Viewer */
    large: 'rounded-xl',
  },

  /**
   * Spacing/Padding nach Verschachtelungsebenen
   * Hierarchisches 4-Ebenen-System für konsistente visuelle Abstände
   *
   * Mögliche Werte (Tailwind):
   *
   * Padding (px-*, py-*):
   * - px-0, py-0      : Kein Padding (0px)
   * - px-1, py-1      : Sehr klein (4px)
   * - px-2, py-2      : Klein (8px)
   * - px-3, py-3      : Kompakt (12px)
   * - px-4, py-4      : Normal (16px)
   * - px-5, py-5      : Mittel (20px)
   * - px-6, py-6      : Großzügig (24px)
   * - px-8, py-8      : Sehr groß (32px)
   * - px-12, py-12    : Maximal (48px)
   *
   * Gap (gap-*):
   * - gap-0   : Kein Abstand (0px)
   * - gap-1   : Sehr eng (4px)
   * - gap-2   : Eng (8px)
   * - gap-3   : Normal (12px)
   * - gap-4   : Mittel (16px)
   * - gap-6   : Weit (24px)
   * - gap-8   : Sehr weit (32px)
   *
   * Space (space-y-*):
   * - space-y-0  : Kein Abstand (0px)
   * - space-y-1  : Sehr eng (4px)
   * - space-y-2  : Eng (8px)
   * - space-y-3  : Kompakt (12px)
   * - space-y-4  : Normal (16px)
   * - space-y-5  : Mittel (20px)
   * - space-y-6  : Großzügig (24px)
   * - space-y-8  : Sehr groß (32px)
   */
  spacing: {
    /**
     * EBENE 1: Layout - Hauptspalten und große Bereiche
     * Orange Markierung im Screenshot (Spalten-Abstand innerhalb des Hauptinhaltes)
     */
    layout: {
      /** Abstand zwischen Haupt-Spalten (z.B. Step3: Rezept ↔ PDF-Viewer) */
      columns: 'gap-6',
      /** Padding für äußerste Container/Panels (INNEN-Abstand, nicht zwischen Spalten!) */
      container: { x: 'px-6', y: 'py-6' },
      /** Abstand zwischen Seiteninhalt und Viewport-Rand */
      page: { x: 'px-6', y: 'py-6' },
    },

    /**
     * EBENE 2: Section - Große Bereiche innerhalb einer Spalte
     * Türkis Markierung im Screenshot (Elemente-Abstand innerhalb der Spalten)
     */
    section: {
      /** Vertikaler Abstand zwischen Sections (z.B. Titel → Portionen → Zutaten) */
      vertical: 'space-y-6',
      /** Padding innerhalb von Section-Panels */
      padding: { x: 'px-6', y: 'py-6' },
      /** Gap für Header-Elemente oder Section-Grids */
      gap: 'gap-4',
    },

    /**
     * EBENE 3: Element - Cards/Panels innerhalb einer Section
     * Rot Markierung im Screenshot (Weitere Elemente innerhalb der Elemente)
     */
    element: {
      /** Vertikaler Abstand zwischen Cards/Elementen (z.B. zwischen Zutat-Cards) */
      vertical: 'space-y-4',
      /** Padding innerhalb von Cards/Content-Boxen */
      padding: { x: 'px-4', y: 'py-3' },
      /** Gap zwischen zusammengehörenden Elementen (z.B. Badge + Text) */
      gap: 'gap-3',
    },

    /**
     * EBENE 4: Item - Zeilen in Listen/Tabellen
     * Lila Markierung im Screenshot (Zeilen-Abstände von Auflistungen)
     */
    item: {
      /** Vertikaler Abstand zwischen Listeneinträgen (z.B. Menge → Zutat → Notiz) */
      vertical: 'space-y-2',
      /** Padding in Tabellenzeilen oder kleinen List-Items */
      padding: { x: 'px-4', y: 'py-3' },
      /** Gap für sehr eng zusammenhängende Items (z.B. Status-Icon + Text) */
      gap: 'gap-2',
    },

    /**
     * Spezielle Button/Badge-Paddings
     * Für interaktive Elemente unabhängig von der Hierarchie
     */
    button: {
      /** Standard Action-Buttons (Modal-Buttons, Footer-Buttons) */
      default: { x: 'px-4', y: 'py-2' },
      /** Kleine Buttons (Filter, Zoom, Navigation, Pager) */
      compact: { x: 'px-3', y: 'py-1' },
      /** Badges und Status-Tags */
      badge: { x: 'px-2', y: 'py-0.5' },
    },
  },

  /**
   * Shadow-Konfiguration
   * Einheitliche Schatten für Karten und Panels
   */
  shadow: {
    card: 'shadow-sm',
    panel: 'shadow-sm',
  },

  // ============================================================================
  // STEP 1: Auswählen
  // ============================================================================
  step1: {
    // Platzhalter für zukünftige Step-1-spezifische Konfiguration
  },

  // ============================================================================
  // STEP 2: Analysieren
  // ============================================================================
  step2: {
    // Platzhalter für zukünftige Step-2-spezifische Konfiguration
  },

  // ============================================================================
  // STEP 3: Prüfen (Review-Seite)
  // ============================================================================
  /**
   * Step 3: Zweispaltiges Layout (Rezeptdaten + PDF-Viewer)
   *
   * Layout-Verhalten:
   * - Mobile/Tablet (< 1280px): Einspaltig, nur Rezeptdaten sichtbar
   * - Desktop (≥ 1280px): Zweispaltig, Verhältnis 3:2 (60% : 40%)
   * - Beide Spalten feste Höhe zwischen Header und Footer
   * - Linke Spalte: Scrollbar bei Überlauf (mit abgerundeten Caps)
   * - Rechte Spalte: PDF-Viewer passt sich der Höhe an
   */
  step3: {
    /**
     * Grid-Layout für die zweispaltige Ansicht
     */
    grid: {
      /**
       * Vollständige Grid-Container-Klassen
       * WICHTIG: Tailwind JIT benötigt vollständige Klassen-Namen!
       * Dynamische Template-Strings funktionieren NICHT.
       *
       * - Basis: Einspaltiges Grid mit eigener Scrollbar
       * - Ab XL: Zweispaltiges Grid mit 3:2 Verhältnis
       */
      gridClasses: 'grid h-full min-h-0 flex-1 grid-cols-1 overflow-y-auto xl:grid-cols-[3fr_2fr] xl:overflow-visible',

      /**
       * Klassen für die rechte Spalte (PDF-Viewer)
       * - Flexibles Einspaltenlayout unterhalb des Breakpoints mit Mindesthöhe
       * - sm:min-h-[320px]: Höhere Mindestfläche auf größeren Smartphones/Tablets
       * - xl:h-full: Volle Höhe im zweispaltigen Desktop-Layout
       */
      rightColumnClasses: 'flex min-h-[240px] flex-col sm:min-h-[320px] xl:min-h-0 xl:h-full',

      /**
       * Dokumentation der Layout-Parameter
       * (Nur zur Referenz, nicht direkt in Code verwenden)
       */
      _params: {
        /** Spalten-Verhältnis (Flexbox fr-Einheiten) */
        columnRatio: {
          left: 2,   // 60% der verfügbaren Breite
          right: 3,  // 40% der verfügbaren Breite
        },
        /** Abstand zwischen den Spalten */
        /** gap: '1.5rem',  // gap-6 */
        /** Breakpoint für zweispaltiges Layout */
        breakpoint: {
          name: 'xl',
          minWidth: '1280px',
        },
      },
    },
  },

  // ============================================================================
  // STEP 4: Übertragen
  // ============================================================================
  step4: {
    // Platzhalter für zukünftige Step-4-spezifische Konfiguration
  },
} as const;

// ============================================================================
// HELPER-FUNKTIONEN
// ============================================================================

/**
 * Helper-Funktionen für Step 3 Layout
 *
 * Hinweis: Wegen Tailwind JIT sollten die vorgefertigten gridClasses
 * aus layoutConfig.step3.grid direkt verwendet werden, statt diese Helpers.
 * Diese Funktionen sind nur zur Laufzeit-Berechnung gedacht.
 */
export const step3LayoutHelpers = {
  /**
   * Gibt die Dokumentation der Grid-Parameter zurück
   */
  getGridParams: () => {
    if (!layoutConfig.step3.grid) {
      throw new Error('Step 3 grid configuration not found');
    }
    return layoutConfig.step3.grid._params;
  },

  /**
   * Prüft, ob das zweispaltige Layout bei gegebener Breite aktiv ist
   */
  isDesktopLayout: (windowWidth: number): boolean => {
    return windowWidth >= 1280; // xl breakpoint
  },

  /**
   * Berechnet die Spaltenbreiten basierend auf Container-Breite
   * Nützlich für dynamische Anpassungen oder Canvas-Rendering
   */
  calculateColumnWidths: (containerWidth: number, gap: number = 24) => {
    if (!layoutConfig.step3.grid) {
      throw new Error('Step 3 grid configuration not found');
    }
    const { columnRatio } = layoutConfig.step3.grid._params;
    const totalRatio = columnRatio.left + columnRatio.right;
    const availableWidth = containerWidth - gap;

    return {
      left: (availableWidth * columnRatio.left) / totalRatio,
      right: (availableWidth * columnRatio.right) / totalRatio,
    };
  },
};

// ============================================================================
// TYPE EXPORTS
// ============================================================================

/**
 * Type-Safe Exports für TypeScript
 */
export type LayoutConfig = typeof layoutConfig;
export type BorderRadiusSize = keyof typeof layoutConfig.borderRadius;
export type StepNumber = 1 | 2 | 3 | 4;

// ============================================================================
// VERWENDUNGSBEISPIELE
// ============================================================================

/**
 * Beispiel für Step3Review.tsx:
 *
 * import { layoutConfig } from '../../config/layout.config';
 * import clsx from 'clsx';
 *
 * // Grid-Container
 * <div className={layoutConfig.step3.grid.gridClasses}>
 *
 *   // Linke Spalte
 *   <div className={clsx(
 *     "flex min-h-0 flex-col overflow-hidden border border-border bg-panel",
 *     layoutConfig.borderRadius.large,
 *     layoutConfig.shadow.panel
 *   )}>
 *     <div className={clsx(
 *       "scrollbar-rounded flex-1 overflow-y-auto",
 *       layoutConfig.spacing.container.x,
 *       layoutConfig.spacing.container.y
 *     )}>
 *       <div className={layoutConfig.spacing.section}>
 *         // Inhalt
 *       </div>
 *     </div>
 *   </div>
 *
 *   // Rechte Spalte (PDF-Viewer)
 *   <aside className={layoutConfig.step3.grid.rightColumnClasses}>
 *     <PdfViewerPlaceholder />
 *   </aside>
 *
 * </div>
 *
 * ---
 *
 * Beispiel für andere Steps:
 *
 * import { layoutConfig } from '../../config/layout.config';
 *
 * // Allgemeine Styles verwenden
 * <div className={clsx(
 *   "p-6",
 *   layoutConfig.borderRadius.medium,
 *   layoutConfig.shadow.card
 * )}>
 *   <div className={layoutConfig.spacing.section}>
 *     // Inhalt
 *   </div>
 * </div>
 */
