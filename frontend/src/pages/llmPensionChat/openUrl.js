export function buildOpenUrl(url, origin, hash) {
  const trimmed = String(url || "").trim();
  if (!trimmed) return "";

  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    return trimmed;
  }

  const safeOrigin = String(origin || "").trim();
  if (!safeOrigin) {
    return trimmed;
  }

  const hashStr = String(hash || "");
  const isHashRouter = hashStr.startsWith("#/");

  if (trimmed.startsWith("/")) {
    return isHashRouter ? `${safeOrigin}/#${trimmed}` : `${safeOrigin}${trimmed}`;
  }

  return isHashRouter ? `${safeOrigin}/#/${trimmed}` : `${safeOrigin}/${trimmed}`;
}

export function openUrlOnce({ url, origin, hash, win, lastOpenAtRef, lastOpenUrlRef, ttlMs = 2500 }) {
  const finalUrl = buildOpenUrl(url, origin, hash);
  if (!finalUrl) return { opened: false, finalUrl: "" };

  const now = Date.now();
  const lastAt = Number(lastOpenAtRef?.current || 0);
  const lastUrl = lastOpenUrlRef?.current || null;

  if (now - lastAt < ttlMs && lastUrl === finalUrl) {
    return { opened: false, finalUrl };
  }

  if (lastOpenAtRef) lastOpenAtRef.current = now;
  if (lastOpenUrlRef) lastOpenUrlRef.current = finalUrl;

  win?.open?.(finalUrl, "_blank", "noopener,noreferrer");
  return { opened: true, finalUrl };
}
