import { useMemo } from "react";
import type { CSSProperties } from "react";

/** Soft, enchanting pastel palette for the drifting petals. */
const PETAL_COLORS = [
  ["#ffd1e8", "#ff8fc4"], // pink
  ["#ffe0c2", "#ffb27a"], // peach
  ["#e7d4ff", "#b98bff"], // lavender
  ["#d3f2ff", "#7cc7ff"], // sky
  ["#d6ffe6", "#79e6a8"], // mint
  ["#fff3c4", "#ffd85e"], // gold
  ["#ffd6d6", "#ff9aa0"], // rose
];

const PETAL_COUNT = 42;

interface PetalDef {
  key: number;
  style: CSSProperties;
}

function buildPetals(): PetalDef[] {
  return Array.from({ length: PETAL_COUNT }, (_, i) => {
    const [light, deep] = PETAL_COLORS[i % PETAL_COLORS.length];
    const size = 10 + Math.random() * 20; // 10 – 30px
    const left = Math.random() * 100; // vw
    const drift = (Math.random() * 44 - 8) * (Math.random() > 0.5 ? 1 : -1); // vw sideways breeze
    const spin = 220 + Math.random() * 520; // deg
    const duration = 1.9 + Math.random() * 1.4; // s
    const delay = Math.random() * 0.7; // s

    const style: CSSProperties = {
      left: `${left}vw`,
      width: `${size}px`,
      height: `${size * 0.78}px`,
      color: deep,
      background: `radial-gradient(circle at 30% 30%, ${light}, ${deep})`,
      animationDuration: `${duration}s`,
      animationDelay: `${delay}s`,
      ["--drift" as string]: `${drift}vw`,
      ["--spin" as string]: `${spin}deg`,
    };

    return { key: i, style };
  });
}

export function PetalOverlay({ active }: { active: boolean }) {
  const petals = useMemo(() => (active ? buildPetals() : []), [active]);

  if (!active) return null;

  return (
    <div className="petal-overlay" aria-hidden="true">
      {petals.map((petal) => (
        <span key={petal.key} className="petal" style={petal.style} />
      ))}
    </div>
  );
}