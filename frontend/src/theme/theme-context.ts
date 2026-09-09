import { createContext } from "react";

export type ThemeMode = "normal" | "dark" | "light";
export type BackgroundKind = "plain" | "bubbles" | "mesh" | "grid" | "glow" | "image";
export type FontKind = "inter" | "sora" | "serif" | "system";

export const THEME_MODES: { id: ThemeMode; label: string; hint: string }[] = [
  { id: "normal", label: "Normal", hint: "Industrial console" },
  { id: "dark", label: "Dark", hint: "Deep navy blue" },
  { id: "light", label: "Light", hint: "Soft & airy" },
];

export const BACKGROUNDS: { id: BackgroundKind; label: string }[] = [
  { id: "plain", label: "Plain" },
  { id: "bubbles", label: "Bubbles" },
  { id: "mesh", label: "Mesh" },
  { id: "grid", label: "Grid" },
  { id: "glow", label: "Glow" },
  { id: "image", label: "Circuit" },
];

export const FONTS: { id: FontKind; label: string }[] = [
  { id: "inter", label: "Inter" },
  { id: "sora", label: "Sora" },
  { id: "serif", label: "Serif" },
  { id: "system", label: "System" },
];

export const SCALE_MIN = 0.85;
export const SCALE_MAX = 1.4;
export const SCALE_STEP = 0.05;
export const SCALE_DEFAULT = 1.06;

export interface ThemeContextValue {
  theme: ThemeMode;
  background: BackgroundKind;
  font: FontKind;
  scale: number;
  petalsActive: boolean;
  setTheme: (theme: ThemeMode) => void;
  setBackground: (background: BackgroundKind) => void;
  setFont: (font: FontKind) => void;
  setScale: (scale: number) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  resetZoom: () => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);