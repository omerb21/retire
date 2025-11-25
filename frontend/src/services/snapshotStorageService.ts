/**
 * Centralized helpers for client snapshot data in localStorage
 */

const getSnapshotStorageKey = (clientId: string | number): string => {
  return `snapshot_client_${clientId}`;
};

export const loadSnapshotRawFromStorage = (
  clientId: string | number
): string | null => {
  try {
    return localStorage.getItem(getSnapshotStorageKey(clientId));
  } catch (error) {
    console.error('Failed to load snapshot from localStorage:', error);
    return null;
  }
};

export const saveSnapshotRawToStorage = (
  clientId: string | number,
  rawData: string
): void => {
  try {
    localStorage.setItem(getSnapshotStorageKey(clientId), rawData);
  } catch (error) {
    console.error('Failed to save snapshot to localStorage:', error);
  }
};

export const removeSnapshotFromStorage = (clientId: string | number): void => {
  try {
    localStorage.removeItem(getSnapshotStorageKey(clientId));
  } catch (error) {
    console.error('Failed to remove snapshot from localStorage:', error);
  }
};
