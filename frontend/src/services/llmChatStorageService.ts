import type { LlmChatMessageDto } from '../lib/api';

const getLlmChatStorageKey = (clientId: string | number | undefined): string => {
  if (clientId === undefined || clientId === null) {
    return 'llmChat_global';
  }
  return `llmChat_client_${clientId}`;
};

export const loadLlmChatFromStorage = (
  clientId: string | number | undefined,
): LlmChatMessageDto[] | null => {
  try {
    const raw = localStorage.getItem(getLlmChatStorageKey(clientId));
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return null;
    }

    return parsed as LlmChatMessageDto[];
  } catch (error) {
    console.error('Failed to load LLM chat from localStorage', error);
    return null;
  }
};

export const saveLlmChatToStorage = (
  clientId: string | number | undefined,
  messages: LlmChatMessageDto[],
): void => {
  try {
    localStorage.setItem(getLlmChatStorageKey(clientId), JSON.stringify(messages));
  } catch (error) {
    console.error('Failed to save LLM chat to localStorage', error);
  }
};

export const clearLlmChatFromStorage = (
  clientId: string | number | undefined,
): void => {
  try {
    localStorage.removeItem(getLlmChatStorageKey(clientId));
  } catch (error) {
    console.error('Failed to clear LLM chat from localStorage', error);
  }
};
