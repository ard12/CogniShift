import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { SVGProps } from "react";
import { cn } from "@/lib/cn";
import { useTheme } from "@/theme/useTheme";
import {
  BACKGROUNDS,
  FONTS,
  SCALE_MAX,
  SCALE_MIN,
  THEME_MODES,
} from "@/theme/theme-context";

function IconPalette(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" width={16} height={16} fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M12 3a9 9 0 1 0 0 18c1 0 1.6-.8 1.6-1.7 0-.5-.2-.9-.5-1.2-.3-.3-.5-.7-.5-1.1 0-1 .8-1.7 1.7-1.7H16a5 5 0 0 0 5-5c0-3.9-4-7.3-9-7.3Z" />
      <circle cx="7.5" cy="10.5" r="1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="7.5" r="1" fill="currentColor" stroke="none" />
      <circle cx="16.5" cy="10.5" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

function IconMinus(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" width={14} height={14} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" {...props}>
      <path d="M5 12h14" />
    </svg>
  );
}

function IconPlusSmall(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" width={14} height={14} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" {...props}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

/** Little preview swatch for each theme so the choice reads at a glance. */
const THEME_SWATCH: Record<string, string> = {
  normal: "linear-gradient(135deg,#0a0d12 0 50%,#06b6d4 50% 100%)",
  dark: "linear-gradient(135deg,#091326 0 50%,#5b93ff 50% 100%)",
  light: "linear-gradient(135deg,#f3f5fb 0 50%,#3f6ff0 50% 100%)",
};

/** Font-family preview so the picker shows the actual typeface. */
const FONT_PREVIEW: Record<string, string> = {
  inter: "'Inter', system-ui, sans-serif",
  sora: "'Sora', system-ui, sans-serif",
  serif: "Georgia, 'Times New Roman', serif",
  system: "system-ui, sans-serif",
};

export function AppearanceMenu() {
  const {
    theme,
    background,
    font,
    scale,
    setTheme,
    setBackground,
    setFont,
    zoomIn,
    zoomOut,
    resetZoom,
  } = useTheme();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent | TouchEvent) {
      const target = event.target as Node;
      if (
        rootRef.current && !rootRef.current.contains(target) &&
        panelRef.current && !panelRef.current.contains(target)
      ) {
        setOpen(false);
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("touchstart", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("touchstart", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const zoomPct = Math.round(scale * 100);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="appearance-trigger flex items-center gap-1.5 rounded-lg border border-surface-border px-2.5 py-1.5 text-ink-2 transition-all hover:text-ink-1"
        aria-haspopup="menu"
        aria-expanded={open}
        title="Appearance"
      >
        <IconPalette />
        <span className="hidden text-[11px] font-medium uppercase tracking-wide sm:inline">Theme</span>
      </button>

      {open &&
        createPortal(
          <div
            ref={panelRef}
            role="menu"
            className="appearance-panel fixed right-4 top-16 w-80 max-w-[calc(100vw-2rem)] rounded-2xl border border-surface-border-strong p-4"
          >
            <div className="mb-3 flex items-center justify-between">
              <p className="text-[10px] font-extrabold uppercase tracking-[0.22em] text-ink-1">Theme</p>
              <span className="appearance-chip rounded-full px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide text-brand">Menu</span>
            </div>

            <div className="mb-4 grid grid-cols-3 gap-2">
              {THEME_MODES.map((mode) => (
                <button
                  key={mode.id}
                  type="button"
                  onClick={() => setTheme(mode.id)}
                  className={cn(
                    "appearance-option flex flex-col items-center gap-1.5 rounded-xl border p-2 text-[11px] font-semibold",
                    theme === mode.id ? "is-active" : "text-ink-2 hover:text-ink-1"
                  )}
                  title={mode.hint}
                >
                  <span className="h-6 w-6 rounded-full border border-surface-border-strong shadow-inner" style={{ background: THEME_SWATCH[mode.id] }} aria-hidden="true" />
                  {mode.label}
                </button>
              ))}
            </div>

            <div className="mb-4">
              <p className="mb-1.5 text-[10px] font-extrabold uppercase tracking-[0.22em] text-ink-1">Background</p>
              <div className="flex flex-wrap gap-1.5">
                {BACKGROUNDS.map((bg) => (
                  <button
                    key={bg.id}
                    type="button"
                    onClick={() => setBackground(bg.id)}
                    className={cn(
                      "appearance-option rounded-md border px-2 py-1 text-[11px] font-semibold",
                      background === bg.id ? "is-active" : "text-ink-2 hover:text-ink-1"
                    )}
                  >
                    {bg.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="mb-4">
              <p className="mb-1.5 text-[10px] font-extrabold uppercase tracking-[0.22em] text-ink-1">Font</p>
              <div className="flex flex-wrap gap-1.5">
                {FONTS.map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setFont(f.id)}
                    style={{ fontFamily: FONT_PREVIEW[f.id] }}
                    className={cn(
                      "appearance-option rounded-md border px-2.5 py-1 text-[12px] font-semibold",
                      font === f.id ? "is-active" : "text-ink-2 hover:text-ink-1"
                    )}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="mb-1">
              <p className="mb-1.5 text-[10px] font-extrabold uppercase tracking-[0.22em] text-ink-1">Text size</p>
              <div className="flex items-center gap-2">
                <button type="button" onClick={zoomOut} disabled={scale <= SCALE_MIN} className="appearance-option flex h-7 w-7 items-center justify-center rounded-md border border-surface-border text-ink-2 hover:text-ink-1 disabled:opacity-40" aria-label="Decrease text size">
                  <IconMinus />
                </button>
                <button type="button" onClick={resetZoom} className="appearance-option flex-1 rounded-md border border-surface-border py-1 text-center font-mono text-[11px] font-extrabold text-ink-1" title="Reset text size">
                  {zoomPct}%
                </button>
                <button type="button" onClick={zoomIn} disabled={scale >= SCALE_MAX} className="appearance-option flex h-7 w-7 items-center justify-center rounded-md border border-surface-border text-ink-2 hover:text-ink-1 disabled:opacity-40" aria-label="Increase text size">
                  <IconPlusSmall />
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}