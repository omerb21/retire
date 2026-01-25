export function renderHtmlReport({ mode = "manual", htmlContent, openWindow, alertFn } = {}) {
  if (mode === "auto") {
    return { opened: false, htmlContent: htmlContent || "" };
  }

  const open = openWindow || ((...args) => window.open(...args));
  const notify = alertFn || ((msg) => alert(msg));

  const reportWindow = open("", "_blank");
  if (!reportWindow) {
    notify("יש לאפשר פתיחת חלונות קופצים להצגת הדוח");
    return { opened: false, htmlContent: htmlContent || "" };
  }

  reportWindow.document.open();
  reportWindow.document.write(htmlContent || "");
  reportWindow.document.close();
  reportWindow.focus();

  return { opened: true, htmlContent: htmlContent || "" };
}
