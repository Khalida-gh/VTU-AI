import { BookOpen } from "lucide-react";

export default function EmptyState() {
  return (
    <div
      style={{
        maxWidth: 900,
        margin: "60px auto",
        textAlign: "center",
        color: "#6b7280",
      }}
    >
      <BookOpen size={60} />

      <h2>No Answer Generated Yet</h2>

      <p>
        Select a subject, enter your VTU question, choose the marks,
        and click <strong>Generate Answer</strong>.
      </p>
    </div>
  );
}