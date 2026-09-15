import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/**
 * Presentational motion layer.
 * Keeps functional panels, chat threads, and textareas rock-solid and stable.
 */
export function MotionEffects() {
  const location = useLocation();

  useEffect(() => {
    // Ensures clean, stable layout without 3D wobbling or font blur
  }, [location.pathname]);

  return null;
}