import "./QuestionForm.css";
import { useState } from "react";
import { VTU_SUBJECTS, type QueryPayload } from "../types";

interface Props {
  onSubmit: (payload: QueryPayload) => void;
  loading: boolean;
}

const PRESET_MARKS = [2, 5, 8, 10, 12, 15, 20];

export default function QuestionForm({ onSubmit, loading }: Props) {
  const [subject, setSubject] = useState<string>(VTU_SUBJECTS[0]);
  const [question, setQuestion] = useState("");
  const [marks, setMarks] = useState(5);
  const [customMarks, setCustomMarks] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    onSubmit({ subject, question, marks });
  }

  return (
    <form className="question-container" onSubmit={submit}>
      <span className="hero-eyebrow">Indexed on your notes</span>

      <h1 className="hero-title">Welcome back 👋</h1>

      <p className="hero-subtitle">
        Ask any VTU question, pick the marks it's worth, and get an
        exam-ready answer drawn from your own study material.
      </p>

      <div className="top-row">
        <div className="subject-section">
          <label className="form-label" htmlFor="subject-select">
            Subject
          </label>

          <select
            id="subject-select"
            className="subject-select"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
          >
            {VTU_SUBJECTS.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>

          <p className="subject-code">Searching notes for “{subject}”</p>
        </div>

        <div className="marks-section">
          <label className="form-label" htmlFor="marks-select">
            Marks
          </label>

          <div className="marks-row">
            <select
              id="marks-select"
              className="marks-select"
              value={PRESET_MARKS.includes(marks) ? marks : "custom"}
              onChange={(e) => {
                if (e.target.value === "custom") {
                  setMarks(Number(customMarks) || 0);
                } else {
                  setMarks(Number(e.target.value));
                }
              }}
            >
              {PRESET_MARKS.map((m) => (
                <option key={m} value={m}>
                  {m} Marks
                </option>
              ))}
              <option value="custom">Custom</option>
            </select>

            {!PRESET_MARKS.includes(marks) && (
              <input
                type="number"
                min="1"
                className="custom-marks-input"
                placeholder="Marks"
                value={customMarks}
                onChange={(e) => {
                  setCustomMarks(e.target.value);
                  setMarks(Number(e.target.value));
                }}
              />
            )}
          </div>
        </div>
      </div>

      <div className="form-group">
        <label className="form-label" htmlFor="question-box">
          Question
        </label>

        <textarea
          id="question-box"
          className="question-box"
          placeholder="Example: Explain SDLC with neat diagram."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        ></textarea>
      </div>

      <div className="generate-row">
        <button className="generate-btn" disabled={loading}>
          {loading ? "Generating…" : "Generate VTU Answer"}
        </button>
      </div>
    </form>
  );
}
