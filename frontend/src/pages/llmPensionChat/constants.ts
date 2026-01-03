export const PROTECTED_COMPONENT_FIELDS_AFTER_CONVERSION = new Set<string>([
  "פיצויים_מעסיק_נוכחי",
  "פיצויים_שלא_עברו_התחשבנות",
  "פיצויים_ממעסיקים_קודמים_רצף_זכויות",
]);

export const BALANCE_ZERO_EPSILON = 0.01;

export const MODEL_PRESETS: Record<string, { value: string; label: string }[]> = {
  ollama: [
    { value: "", label: "ברירת מחדל (מהשרת)" },
    { value: "gemma3:4b", label: "gemma3:4b" },
    { value: "qwen3:8b", label: "qwen3:8b" },
  ],
  openai: [
    { value: "", label: "ברירת מחדל (gpt-5-mini)" },
    { value: "gpt-5-mini", label: "gpt-5-mini (מומלץ)" },
    { value: "gpt-4o-mini", label: "gpt-4o-mini" },
    { value: "gpt-4o", label: "gpt-4o" },
  ],
  gemini: [
    { value: "", label: "ברירת מחדל (gemini-2.0-flash)" },
    { value: "gemini-2.0-flash", label: "gemini-2.0-flash (מומלץ)" },
    { value: "gemini-1.5-flash", label: "gemini-1.5-flash" },
    { value: "gemini-1.5-pro", label: "gemini-1.5-pro" },
  ],
  anthropic: [
    { value: "", label: "ברירת מחדל (claude-3-haiku-20240307)" },
    { value: "claude-3-haiku-20240307", label: "claude-3-haiku-20240307" },
    { value: "claude-3-5-sonnet-20241022", label: "claude-3-5-sonnet-20241022" },
  ],
};

export const ILS_PER_USD = 3.6;
