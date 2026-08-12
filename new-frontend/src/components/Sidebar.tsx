import { useEffect, useState } from "react";
import { Star } from "lucide-react";
import "./sidebar.css";
import {
  getHistory,
  deleteAnswer,
  toggleFavourite,
  updateHistory,
  getFolders,
  createFolder,
  deleteFolder,
  type SavedAnswer,
  type StudyFolder,
} from "../utils/storage";

interface Props {
  onHistoryClick: (item: SavedAnswer) => void;
  showFavourites?: boolean;
}

export default function Sidebar({
  onHistoryClick,
  showFavourites = false,
}: Props) {
  const [history, setHistory] = useState<SavedAnswer[]>([]);
  const [folders, setFolders] = useState<StudyFolder[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);

  function loadHistory() {
    setHistory(getHistory());
    setFolders(getFolders());
  }

  function handleCreateFolder() {
    const name = prompt("Enter folder name:");
    if (!name || !name.trim()) return;
    createFolder(name);
    setFolders(getFolders());
  }

  useEffect(() => {
    loadHistory();
  }, []);

  function handleDelete(id: string) {
    deleteAnswer(id);
    loadHistory();
  }

  function handleFavourite(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    toggleFavourite(id);
    loadHistory();
  }

  function handleDeleteFolder(folderId: string) {
    const folder = folders.find((f) => f.id === folderId);
    if (!folder) return;

    const confirmed = window.confirm(
      `Delete folder "${folder.name}"?\n\nThe answers inside it will NOT be deleted. They will move back to History.`
    );
    if (!confirmed) return;

    deleteFolder(folderId);
    setSelectedFolder(null);
    loadHistory();
  }

  const visibleHistory = history.filter((item) => {
    if (selectedFolder) return item.folderId === selectedFolder;
    return !showFavourites || item.favourite;
  });

  return (
    <div className="sidebar">
      <h2 className="sidebar-title">
        {selectedFolder
          ? folders.find((f) => f.id === selectedFolder)?.name
          : showFavourites
          ? "Favourites"
          : "History"}
      </h2>

      <div className="sidebar-actions">
        <button className="new-folder-btn" onClick={handleCreateFolder}>
          + New Folder
        </button>

        {selectedFolder && (
          <button
            className="back-history-button"
            onClick={() => setSelectedFolder(null)}
          >
            ← History
          </button>
        )}
      </div>

      {folders.length > 0 &&
        !selectedFolder &&
        folders.map((folder) => (
          <div
            key={folder.id}
            className="folder-card"
            onClick={() => setSelectedFolder(folder.id)}
          >
            <span className="folder-name">📁 {folder.name}</span>

            <button
              className="folder-delete-button"
              onClick={(e) => {
                e.stopPropagation();
                handleDeleteFolder(folder.id);
              }}
              title="Delete folder"
            >
              🗑️
            </button>
          </div>
        ))}

      {visibleHistory.length === 0 && (
        <p className="sidebar-empty">
          {selectedFolder
            ? "No answers in this folder yet."
            : showFavourites
            ? "No favourites yet."
            : "No history yet — generated answers will show up here."}
        </p>
      )}

      {visibleHistory.map((item) => (
        <div
          key={item.id}
          className="history-card"
          onClick={() => onHistoryClick(item)}
        >
          <div className="history-card-top">
            <h4>{item.question}</h4>

            <button
              className={`favourite-button ${item.favourite ? "active" : ""}`}
              onClick={(e) => handleFavourite(e, item.id)}
              title={
                item.favourite ? "Remove from favourites" : "Add to favourites"
              }
            >
              <Star size={16} fill={item.favourite ? "currentColor" : "none"} />
            </button>
          </div>

          <small>
            {item.subject} • {item.marks} Marks
          </small>

          <select
            value={item.folderId || ""}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => {
              e.stopPropagation();
              const updatedHistory = history.map((answer) =>
                answer.id === item.id
                  ? { ...answer, folderId: e.target.value || undefined }
                  : answer
              );
              updateHistory(updatedHistory);
              setHistory(updatedHistory);
            }}
          >
            <option value="">No Folder</option>
            {folders.map((folder) => (
              <option key={folder.id} value={folder.id}>
                📁 {folder.name}
              </option>
            ))}
          </select>

          <button
            className="delete-button"
            onClick={(e) => {
              e.stopPropagation();
              handleDelete(item.id);
            }}
          >
            Delete
          </button>
        </div>
      ))}
    </div>
  );
}
