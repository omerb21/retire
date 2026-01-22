export function findFirstNavigatePath(payload) {
  const actions = payload && typeof payload === "object" ? payload.actions : null;
  if (!Array.isArray(actions)) return null;
  const navigateAction = actions.find(
    (a) => a && typeof a === "object" && a.type === "navigate" && typeof a.path === "string" && a.path.trim(),
  );
  if (!navigateAction) return null;
  const path = String(navigateAction.path || "").trim();
  return path ? path : null;
}

export function applyUiNavigateIfPresent(payload, navigateFn) {
  const path = findFirstNavigatePath(payload);
  if (!path) return false;
  navigateFn(path);
  return true;
}
