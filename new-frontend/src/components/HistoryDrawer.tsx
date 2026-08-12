import "./HistoryDrawer.css";
import { X } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function HistoryDrawer({
  open,
  onClose,
}: Props) {
  return (
    <div className={`history-overlay ${open ? "show" : ""}`}>

      <div className="history-drawer">

        <div className="history-header">

          <h2>History</h2>

          <button onClick={onClose}>
            <X />
          </button>

        </div>

        <div className="history-list">

          <div className="history-card">
            Explain SDLC
          </div>

          <div className="history-card">
            Normalization
          </div>

          <div className="history-card">
            Deadlock
          </div>

          <div className="history-card">
            AVL Tree
          </div>

        </div>

      </div>

    </div>
  );
}