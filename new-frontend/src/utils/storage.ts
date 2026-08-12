export interface SavedAnswer {
  id: string;
  question: string;
  subject: string;
  marks: number;
  answer: string;
  createdAt: string;
  folderId?: string;
  favourite: boolean;
  readLater: boolean;
  pinned: boolean;
  views: number;
}

export interface StudyFolder {
  id: string;
  name: string;
  createdAt: string;
}

const KEY = "vtu_ai_history";
const FOLDER_KEY = "vtu_ai_folders";

// ==================== HISTORY ====================

export function getHistory(): SavedAnswer[] {
  return JSON.parse(localStorage.getItem(KEY) || "[]");
}

export function saveAnswer(item: SavedAnswer) {
  const history = getHistory();

  history.unshift(item);

  localStorage.setItem(KEY, JSON.stringify(history));
}

export function deleteAnswer(id: string) {
  const history = getHistory().filter((x) => x.id !== id);

  localStorage.setItem(KEY, JSON.stringify(history));
}

export function updateHistory(history: SavedAnswer[]) {
  localStorage.setItem(KEY, JSON.stringify(history));
}

// ==================== FAVOURITES ====================

export function toggleFavourite(id: string) {
  const history = getHistory();

  const updated = history.map((item) =>
    item.id === id
      ? { ...item, favourite: !item.favourite }
      : item
  );

  updateHistory(updated);
}

export function getFavourites(): SavedAnswer[] {
  return getHistory().filter((item) => item.favourite);
}

// ==================== FOLDERS ====================

export function getFolders(): StudyFolder[] {
  return JSON.parse(
    localStorage.getItem(FOLDER_KEY) || "[]"
  );
}

export function createFolder(name: string) {
  const folders = getFolders();

  const newFolder: StudyFolder = {
    id: crypto.randomUUID(),
    name: name.trim(),
    createdAt: new Date().toISOString(),
  };

  folders.push(newFolder);

  localStorage.setItem(
    FOLDER_KEY,
    JSON.stringify(folders)
  );

  return newFolder;
}

// Delete folder but KEEP the answers
export function deleteFolder(folderId: string) {
  // Remove folder
  const folders = getFolders().filter(
    (folder) => folder.id !== folderId
  );

  localStorage.setItem(
    FOLDER_KEY,
    JSON.stringify(folders)
  );

  // Remove folder assignment from answers
  const history = getHistory().map((answer) =>
    answer.folderId === folderId
      ? { ...answer, folderId: undefined }
      : answer
  );

  localStorage.setItem(
    KEY,
    JSON.stringify(history)
  );
}