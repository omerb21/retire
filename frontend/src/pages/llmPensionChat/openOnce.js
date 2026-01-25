// Returns true if allowed to open now, false if it's a duplicate burst.
export function shouldOpenOnce(key, ttlMs = 1500) {
  try {
    const now = Date.now();
    const k = "__open_once__:" + key;
    const last = Number(sessionStorage.getItem(k) || "0");
    if (last && now - last < ttlMs) return false;
    sessionStorage.setItem(k, String(now));
    return true;
  } catch {
    // If storage blocked, fail open (do not break UX)
    return true;
  }
}
