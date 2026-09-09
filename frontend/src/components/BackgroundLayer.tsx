/**
 * Fixed, non-interactive decorative canvas that sits behind the whole app.
 * The actual pattern is driven purely by the `data-bg` attribute on <html>
 * (see index.css → `.app-bg-layer`), so this component stays dumb and the
 * app layout is never affected.
 */
export function BackgroundLayer() {
  return <div className="app-bg-layer" aria-hidden="true" />;
}