const DB_NAME = "cognishift-device";
const STORE = "keys";
const DEVICE_ID_KEY = "cognishift_device_id";
const DEVICE_SESSION_KEY = "cognishift_device_session";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function storedKeyPair(): Promise<CryptoKeyPair | null> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const request = db.transaction(STORE).objectStore(STORE).get("device-key");
    request.onsuccess = () => resolve((request.result as CryptoKeyPair | undefined) ?? null);
    request.onerror = () => reject(request.error);
  });
}

async function saveKeyPair(pair: CryptoKeyPair) {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const request = db.transaction(STORE, "readwrite").objectStore(STORE).put(pair, "device-key");
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

function b64url(bytes: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function decodeB64url(value: string): ArrayBuffer {
  const raw = atob(value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - value.length % 4) % 4));
  const result = new ArrayBuffer(raw.length);
  const bytes = new Uint8Array(result);
  for (let index = 0; index < raw.length; index += 1) bytes[index] = raw.charCodeAt(index);
  return result;
}

export async function ensureDeviceIdentity() {
  let pair = await storedKeyPair();
  if (!pair) {
    const generated = (await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"])) as CryptoKeyPair;
    const privatePkcs8 = await crypto.subtle.exportKey("pkcs8", generated.privateKey);
    const privateKey = await crypto.subtle.importKey("pkcs8", privatePkcs8, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
    pair = { privateKey, publicKey: generated.publicKey };
    await saveKeyPair(pair);
  }
  let deviceId = localStorage.getItem(DEVICE_ID_KEY);
  if (!deviceId) {
    deviceId = crypto.randomUUID();
    localStorage.setItem(DEVICE_ID_KEY, deviceId);
  }
  const publicKeyJwk = await crypto.subtle.exportKey("jwk", pair.publicKey);
  return {
    deviceId,
    publicKeyJwk,
    displayName: `${navigator.platform || "Browser"} · ${navigator.userAgent.split(" ").slice(-1)[0]}`,
    sign: async (challenge: string) => b64url(await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, pair!.privateKey, decodeB64url(challenge))),
  };
}

export const getDeviceSession = () => sessionStorage.getItem(DEVICE_SESSION_KEY);
export const setDeviceSession = (value: string | null) => value ? sessionStorage.setItem(DEVICE_SESSION_KEY, value) : sessionStorage.removeItem(DEVICE_SESSION_KEY);
