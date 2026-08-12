import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AnswerResponse } from "../types";

interface AnswerCardProps {
  answer: AnswerResponse;
}

export default function AnswerCard({ answer }: AnswerCardProps) {
  const [language, setLanguage] = useState("Hindi");
  const [translatedAnswer, setTranslatedAnswer] = useState<string | null>(null);
  const [translating, setTranslating] = useState(false);

  async function handleTranslate() {
  setTranslating(true);

  try {
    const res = await fetch("http://127.0.0.1:8000/translate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        answer: answer.answerMarkdown,
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
  return (
    <div
      style={{
        maxWidth: "900px",
        margin: "30px auto",
        padding: "24px",
        border: "1px solid #e5e7eb",
        borderRadius: "12px",
        background: "#ffffff",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "20px",
        }}
      >
        <h2 style={{ margin: 0 }}>
          Generated Answer
        </h2>

        <div
          style={{
            display: "flex",
            gap: "8px",
            alignItems: "center",
          }}
        >
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            style={{
              padding: "8px 10px",
              borderRadius: "8px",
              border: "1px solid #d1d5db",
              cursor: "pointer",
            }}
          >
            <option value="Hindi">Hindi</option>
            <option value="Kannada">Kannada</option>
            <option value="English">English</option>
            <option value="Marathi">Marathi</option>
            <option value="Telugu">Telugu</option>
            <option value="Tamil">Tamil</option>
          </select>

          <button
  type="button"
  disabled={translating}
  onClick={handleTranslate}
  style={{
    padding: "8px 14px",
    borderRadius: "8px",
    border: "none",
    background: "#2563eb",
    color: "white",
    cursor: translating ? "not-allowed" : "pointer",
    fontWeight: 600,
    opacity: translating ? 0.7 : 1,
  }}
>
  {translating ? "Translating..." : "🌐 Translate"}
</button>
        </div>
      </div>

      <ReactMarkdown remarkPlugins={[remarkGfm]}>
  {translatedAnswer ?? answer.answerMarkdown}
</ReactMarkdown>
    </div>
  );
}