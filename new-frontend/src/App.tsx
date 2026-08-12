import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BookOpen, Copy, Loader2 } from "lucide-react";

import { saveAnswer } from "./utils/storage";

import Navbar from "./components/Navbar";
import Sidebar from "./components/Sidebar";
import SettingsPanel from "./components/SettingsPanel";
import QuestionForm from "./components/QuestionForm";
import Footer from "./components/Footer";

import type { SavedAnswer } from "./utils/storage";
import type { QueryPayload } from "./types";

import "./App.css";

interface CurrentAnswer {
  question: string;
  subject: string;
  marks: number;
  text: string;
}

export default function App() {
  const [current, setCurrent] = useState<CurrentAnswer | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshHistory, setRefreshHistory] = useState(0);
  const [showFavourites, setShowFavourites] = useState(false);

  const [language, setLanguage] = useState("Hindi");
  const [translatedAnswer, setTranslatedAnswer] = useState<string | null>(null);
  const [translating, setTranslating] = useState(false);
 
  async function handleTranslate() {
  if (!current) return;

  setTranslating(true);

  try {
    const res = await fetch("http://127.0.0.1:8000/translate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        answer: current.text,
        language,
      }),
    });

    if (!res.ok) {
      throw new Error("Translation failed");
    }

    const data = await res.json();

    setTranslatedAnswer(data.translated_answer);
  } catch (error) {
    console.error(error);
    alert("Could not translate the answer.");
  } finally {
    setTranslating(false);
  }
}
  const [darkMode, setDarkMode] = useState(
    localStorage.getItem("theme") === "dark"
  );

  useEffect(() => {
    if (darkMode) {
      document.body.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.body.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  }, [darkMode]);

  function copyAnswer() {
    if (!current) return;
    navigator.clipboard.writeText(current.text);
    alert("Answer copied!");
  }

  async function generateAnswer(payload: QueryPayload) {
    setLoading(true);

    try {
      const res = await fetch("http://127.0.0.1:8000/generate-answer", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          topic: payload.question,
          marks: payload.marks,
          subject: payload.subject,
        }),
      });

      const data = await res.json();
      const answerText = data.answer ?? "No answer returned.";

      setCurrent({
        question: payload.question,
        subject: payload.subject,
        marks: payload.marks,
        text: answerText,
      });

      saveAnswer({
        id: crypto.randomUUID(),
        question: payload.question,
        subject: payload.subject,
        marks: payload.marks,
        answer: answerText,
        createdAt: new Date().toISOString(),
        favourite: false,
        readLater: false,
        pinned: false,
        views: 1,
      });

      setRefreshHistory((v) => v + 1);
    } catch (err) {
      console.error(err);
      setCurrent({
        question: payload.question,
        subject: payload.subject,
        marks: payload.marks,
        text: "Cannot connect to backend. Make sure the VTU AI server is running and try again.",
      });
    }

    setLoading(false);
  }

  return (
    <div className="app-shell">
      <Navbar onFavouritesClick={() => setShowFavourites(!showFavourites)} />

      <div className="app-layout">
        {/* LEFT - HISTORY */}
        <aside className="left-panel">
          <div className="panel">
            <Sidebar
              key={refreshHistory}
              showFavourites={showFavourites}
              onHistoryClick={(item: SavedAnswer) =>
                setCurrent({
                  question: item.question,
                  subject: item.subject,
                  marks: item.marks,
                  text: item.answer,
                })
              }
            />
          </div>
        </aside>

        {/* CENTER - QUESTION + ANSWER */}
        <main className="main-content">
          <QuestionForm onSubmit={generateAnswer} loading={loading} />

          {loading && (
            <div className="state-card loading">
              <div className="state-icon">
                <Loader2 size={22} />
              </div>
              <h3>Writing your answer…</h3>
              <p>
                Searching your indexed notes and drafting a response sized
                for the marks you picked.
              </p>
            </div>
          )}

          {!loading && !current && (
            <div className="state-card">
              <div className="state-icon">
                <BookOpen size={22} />
              </div>
              <h3>No answer generated yet</h3>
              <p>
                Pick a subject, enter your VTU question, choose the marks,
                and hit <strong>Generate VTU Answer</strong>.
              </p>
            </div>
          )}

          {!loading && current && (
            <div className="answer-sheet">
              <div className="answer-sheet-head">
                <div>
                  <h2>Generated Answer</h2>
                  <p>
                    {current.subject} · “{current.question}”
                  </p>
                </div>

                <div className="marks-stamp">
                  <strong>{current.marks}</strong>
                  <span>Marks</span>
                </div>
              </div>

              <div className="markdown-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
  {translatedAnswer ?? current.text}
</ReactMarkdown>
              </div>

              <div className="answer-actions">
  <select
    value={language}
    onChange={(e) => setLanguage(e.target.value)}
    disabled={translating}
  >
    <option value="Hindi">Hindi</option>
    <option value="Kannada">Kannada</option>
    <option value="English">English</option>
    <option value="Marathi">Marathi</option>
    <option value="Telugu">Telugu</option>
    <option value="Tamil">Tamil</option>
  </select>

  <button
    onClick={handleTranslate}
    disabled={translating}
  >
    {translating ? "Translating..." : "🌐 Translate"}
  </button>

  <button onClick={copyAnswer}>
    <Copy size={15} />
    Copy Answer
  </button>
</div>
            </div>
          )}
        </main>

        {/* RIGHT - SETTINGS */}
        <aside className="right-panel">
          <div className="panel">
            <SettingsPanel darkMode={darkMode} setDarkMode={setDarkMode} />
          </div>
        </aside>
      </div>

      <Footer />
    </div>
  );
}
