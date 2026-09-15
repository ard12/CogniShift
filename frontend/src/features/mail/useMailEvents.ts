import { useEffect } from "react";
import { buildUrl } from "@/api/clients";
import { getStoredToken } from "@/lib/token-storage";
import { getDeviceSession } from "@/lib/device-identity";

interface UseMailEventsOptions {
  onNewMail: () => void | Promise<void>;
  enabled?: boolean;
}

export function useMailEvents({ onNewMail, enabled = true }: UseMailEventsOptions) {
  useEffect(() => {
    if (!enabled) return;

    let active = true;
    let retryTimeout: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();

    async function streamEvents() {
      while (active) {
        try {
          const token = getStoredToken();
          const deviceSession = getDeviceSession();
          const deviceId =
            typeof window !== "undefined"
              ? window.localStorage.getItem("cognishift_device_id")
              : null;

          const headers: Record<string, string> = {};
          if (token) headers["Authorization"] = `Bearer ${token}`;
          if (deviceSession) headers["X-Device-Session"] = deviceSession;
          if (deviceId) headers["X-Device-ID"] = deviceId;

          const response = await fetch(buildUrl("/api/v1/mail/events"), {
            headers,
            signal: controller.signal,
          });

          if (!response.ok || !response.body) {
            await new Promise((resolve) => {
              retryTimeout = setTimeout(resolve, 5000);
            });
            continue;
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";

          while (active) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split("\n\n");
            buffer = parts.pop() ?? "";
            for (const part of parts) {
              if (part.includes("event: new_mail")) {
                void onNewMail();
              }
            }
          }
        } catch (err: unknown) {
          if (active && (!(err instanceof Error) || err.name !== "AbortError")) {
            await new Promise((resolve) => {
              retryTimeout = setTimeout(resolve, 5000);
            });
          }
        }
      }
    }

    void streamEvents();

    return () => {
      active = false;
      controller.abort();
      if (retryTimeout) clearTimeout(retryTimeout);
    };
  }, [onNewMail, enabled]);
}
