/**
 * usePush — Web Push subscription management.
 *
 * Registers the service worker, fetches the VAPID public key from Vello's
 * backend, creates a PushSubscription, and persists it via POST /api/v1/push/subscribe.
 *
 * Returns:
 *   supported   — browser supports push
 *   permission  — "default" | "granted" | "denied"
 *   subscribed  — whether an active subscription exists
 *   subscribe() — request permission + create subscription
 *   unsubscribe() — cancel subscription
 */
import { useCallback, useEffect, useRef, useState } from "react";

type Permission = "default" | "granted" | "denied";

export interface PushAPI {
  supported:   boolean;
  permission:  Permission;
  subscribed:  boolean;
  loading:     boolean;
  subscribe:   () => Promise<void>;
  unsubscribe: () => Promise<void>;
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64  = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

export function usePush(): PushAPI {
  const [permission, setPermission] = useState<Permission>(
    () => (typeof Notification !== "undefined" ? (Notification.permission as Permission) : "default")
  );
  const [subscribed, setSubscribed]   = useState(false);
  const [loading, setLoading]         = useState(false);
  const swRegRef = useRef<ServiceWorkerRegistration | null>(null);

  const supported =
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window;

  // Register SW + check existing subscription on mount
  useEffect(() => {
    if (!supported) return;
    navigator.serviceWorker.register("/sw.js").then((reg) => {
      swRegRef.current = reg;
      return reg.pushManager.getSubscription();
    }).then((sub) => {
      if (sub) setSubscribed(true);
    }).catch(() => {});
  }, [supported]);

  const subscribe = useCallback(async () => {
    if (!supported || !swRegRef.current) return;
    setLoading(true);
    try {
      // Request notification permission
      const result = await Notification.requestPermission();
      setPermission(result as Permission);
      if (result !== "granted") return;

      // Fetch VAPID public key
      const keyRes = await fetch("/api/v1/push/vapid-public-key", { credentials: "include" });
      if (!keyRes.ok) return;
      const { public_key } = await keyRes.json() as { public_key: string };

      // Create subscription
      const sub = await swRegRef.current.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(public_key),
      });

      const json = sub.toJSON();
      await fetch("/api/v1/push/subscribe", {
        method:      "POST",
        credentials: "include",
        headers:     { "Content-Type": "application/json" },
        body: JSON.stringify({
          endpoint: json.endpoint,
          p256dh:   (json.keys as Record<string, string>)?.p256dh || "",
          auth:     (json.keys as Record<string, string>)?.auth || "",
          user_agent: navigator.userAgent,
        }),
      });
      setSubscribed(true);
    } catch { /* user cancelled or browser denied */ } finally {
      setLoading(false);
    }
  }, [supported]);

  const unsubscribe = useCallback(async () => {
    if (!swRegRef.current) return;
    setLoading(true);
    try {
      const sub = await swRegRef.current.pushManager.getSubscription();
      if (sub) {
        await fetch(`/api/v1/push/subscribe?endpoint=${encodeURIComponent(sub.endpoint)}`, {
          method: "DELETE", credentials: "include",
        });
        await sub.unsubscribe();
        setSubscribed(false);
      }
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, []);

  return { supported, permission, subscribed, loading, subscribe, unsubscribe };
}
