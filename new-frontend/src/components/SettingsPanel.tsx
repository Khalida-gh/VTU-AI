import React from "react";
import { Moon, Sun, Type, Sparkles } from "lucide-react";
import "./SettingsPanel.css";

interface SettingsPanelProps {
  darkMode: boolean;
  setDarkMode: React.Dispatch<React.SetStateAction<boolean>>;
}

export default function SettingsPanel({
  darkMode,
  setDarkMode,
}: SettingsPanelProps) {
  return (
    <div className="settings-panel">
      <h3>Settings</h3>

      <button onClick={() => setDarkMode(!darkMode)}>
        {darkMode ? <Sun size={17} /> : <Moon size={17} />}
        {darkMode ? "Light Mode" : "Dark Mode"}
      </button>

      <button>
        <Type size={17} />
        Font Size
      </button>

      <button>
        <Sparkles size={17} />
        AI Style
      </button>

      <p className="settings-hint">
        Answers are generated from your indexed notes and formatted for the
        marks you selected.
      </p>
    </div>
  );
}
