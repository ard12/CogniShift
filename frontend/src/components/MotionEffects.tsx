import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/**
 * Presentational-only motion layer.
 *
 * Attaches a subtle pointer-driven 3D tilt and a scroll-triggered reveal to
 * every `.panel` card on the page — without touching any page markup, so the
 * layout and position of every card stays exactly the same. It re-scans on
 * route changes and watches for panels that are added asynchronously (e.g.
 * after data loads). All effects are skipped when the user prefers reduced
 * motion, and tilt is only enabled for fine pointers (mouse/trackpad).
 */
export function MotionEffects() {
  const location = useLocation();

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
    const main = document.querySelector("main");
    if (!main) return;

    const revealObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("reveal-in");
            revealObserver.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.08, rootMargin: "0px 0px -5% 0px" }
    );

    const enhance = () => {
      const panels = main.querySelectorAll<HTMLElement>(".panel:not([data-motion])");
      let index = 0;
      panels.forEach((panel) => {
        panel.dataset.motion = "true";
        if (finePointer && !reduced) panel.classList.add("tilt");
        if (!reduced) {
          panel.classList.add("reveal");
          panel.style.transitionDelay = `${Math.min(index, 6) * 60}ms`;
          revealObserver.observe(panel);
          index += 1;
        }
      });
    };

    enhance();

    const mutationObserver = new MutationObserver(() => enhance());
    mutationObserver.observe(main, { childList: true, subtree: true });

    // ---- Pointer-driven 3D tilt (event-delegated on <main>) ----
    const MAX_TILT = 5; // degrees
    let active: HTMLElement | null = null;

    const resetTilt = (el: HTMLElement) => {
      el.style.setProperty("--tilt-rx", "0deg");
      el.style.setProperty("--tilt-ry", "0deg");
      el.classList.remove("is-tilting");
    };

    const onPointerMove = (event: Event) => {
      if (!finePointer || reduced) return;
      const e = event as PointerEvent;
      const target = (e.target as HTMLElement | null)?.closest<HTMLElement>(".panel.tilt") ?? null;
      if (active && active !== target) resetTilt(active);
      if (!target) {
        active = null;
        return;
      }
      active = target;
      const rect = target.getBoundingClientRect();
      const px = (e.clientX - rect.left) / rect.width;
      const py = (e.clientY - rect.top) / rect.height;
      const ry = (px - 0.5) * 2 * MAX_TILT;
      const rx = (0.5 - py) * 2 * MAX_TILT;
      target.style.setProperty("--tilt-ry", `${ry.toFixed(2)}deg`);
      target.style.setProperty("--tilt-rx", `${rx.toFixed(2)}deg`);
      target.classList.add("is-tilting");
    };

    const onPointerLeave = () => {
      if (active) {
        resetTilt(active);
        active = null;
      }
    };

    main.addEventListener("pointermove", onPointerMove);
    main.addEventListener("pointerleave", onPointerLeave);

    return () => {
      revealObserver.disconnect();
      mutationObserver.disconnect();
      main.removeEventListener("pointermove", onPointerMove);
      main.removeEventListener("pointerleave", onPointerLeave);
    };
  }, [location.pathname]);

  return null;
}