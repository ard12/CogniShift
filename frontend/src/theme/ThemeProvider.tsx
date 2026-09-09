import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { BackgroundLayer } from "@/components/BackgroundLayer";
import { PetalOverlay } from "@/components/PetalOverlay";
import {
  SCALE_DEFAULT,
  SCALE_MAX,
  SCALE_MIN,
  SCALE_STEP,
  ThemeContext,
  type BackgroundKind,
  type FontKind,
  type ThemeContextValue,
  type ThemeMode,
} from "./theme-context";

const STORAGE_KEYS = {
  theme: "cognishift.theme",
  background: "cognishift.background",
  font: "cognishift.font",
  scale: "cognishift.scale",
} as const;

function readStored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const value = localStorage.getItem(key);
    if (value && (allowed as readonly string[]).includes(value)) {
      return value as T;
    }
  } catch {
    /* localStorage unavailable — fall back to default */
  }
  return fallback;
}

function readStoredScale(): number {
  try {
    const value = Number(localStorage.getItem(STORAGE_KEYS.scale));
    if (Number.isFinite(value) && value >= SCALE_MIN && value <= SCALE_MAX) {
      return value;
    }
  } catch {
    /* ignore */
  }
  return SCALE_DEFAULT;
}

function clampScale(value: number): number {
  return Math.min(SCALE_MAX, Math.max(SCALE_MIN, Math.round(value * 100) / 100));
}

const THEME_VALUES: ThemeMode[] = ["normal", "dark", "light"];
const BG_VALUES: BackgroundKind[] = ["plain", "bubbles", "mesh", "grid", "glow", "image"];
const FONT_VALUES: FontKind[] = ["inter", "sora", "serif", "system"];

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>(() =>
    readStored(STORAGE_KEYS.theme, THEME_VALUES, "normal")
  );
  const [background, setBackgroundState] = useState<BackgroundKind>(() =>
    readStored(STORAGE_KEYS.background, BG_VALUES, "bubbles")
  );
  const [font, setFontState] = useState<FontKind>(() =>
    readStored(STORAGE_KEYS.font, FONT_VALUES, "inter")
  );
  const [scale, setScaleState] = useState<number>(() => readStoredScale());
  const [petalsActive, setPetalsActive] = useState(false);

  const timers = useRef<number[]>([]);

  useLayoutEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    root.style.colorScheme = theme === "light" ? "light" : "dark";
    try {
      localStorage.setItem(STORAGE_KEYS.theme, theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  useLayoutEffect(() => {
    document.documentElement.setAttribute("data-bg", background);
    try {
      localStorage.setItem(STORAGE_KEYS.background, background);
    } catch {
      /* ignore */
    }
  }, [background]);

  useLayoutEffect(() => {
    document.documentElement.setAttribute("data-font", font);
    try {
      localStorage.setItem(STORAGE_KEYS.font, font);
    } catch {
      /* ignore */
    }
  }, [font]);

  useLayoutEffect(() => {
    document.documentElement.style.setProperty("--ui-scale", String(scale));
    try {
      localStorage.setItem(STORAGE_KEYS.scale, String(scale));
    } catch {
      /* ignore */
    }
  }, [scale]);

  useEffect(() => {
    const captured = timers;
    return () => {
      captured.current.forEach((id) => window.clearTimeout(id));
    };
  }, []);

  const setTheme = useCallback((next: ThemeMode) => {
    setThemeState((current) => {
      if (next === current) return current;

      const prefersReduced = window.matchMedia?.(
        "(prefers-reduced-motion: reduce)"
      ).matches;

      if (prefersReduced) {
        return next;
      }

      setPetalsActive(true);
      timers.current.push(window.setTimeout(() => setThemeState(next), 650));
      timers.current.push(window.setTimeout(() => setPetalsActive(false), 2600));
      return current;
    });
  }, []);

  const setBackground = useCallback((next: BackgroundKind) => {
    setBackgroundState(next);
  }, []);

  const setFont = useCallback((next: FontKind) => {
    setFontState(next);
  }, []);

  const setScale = useCallback((next: number) => {
    setScaleState(clampScale(next));
  }, []);

  const zoomIn = useCallback(() => setScaleState((s) => clampScale(s + SCALE_STEP)), []);
  const zoomOut = useCallback(() => setScaleState((s) => clampScale(s - SCALE_STEP)), []);
  const resetZoom = useCallback(() => setScaleState(SCALE_DEFAULT), []);

  const value = useMemo<ThemeContextValue>(
    () => ({
      theme,
      background,
      font,
      scale,
      petalsActive,
      setTheme,
      setBackground,
      setFont,
      setScale,
      zoomIn,
      zoomOut,
      resetZoom,
    }),
    [theme, background, font, scale, petalsActive, setTheme, setBackground, setFont, setScale, zoomIn, zoomOut, resetZoom]
  );

  return (
    <ThemeContext.Provider value={value}>
      <BackgroundLayer />
      {children}
      <PetalOverlay active={petalsActive} />
    </ThemeContext.Provider>
  );
}