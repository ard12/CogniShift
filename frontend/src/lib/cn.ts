type ClassValue = string | number | null | undefined | false | ClassValue[];

/** Minimal `classnames`-style joiner — avoids pulling in a dependency for this. */
export function cn(...values: ClassValue[]): string {
  const out: string[] = [];

  for (const v of values) {
    if (!v) continue;

    if (Array.isArray(v)) {
      const nested = cn(...v);
      if (nested) out.push(nested);
    } else {
      out.push(String(v));
    }
  }

  return out.join(" ");
}