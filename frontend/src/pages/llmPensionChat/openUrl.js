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
