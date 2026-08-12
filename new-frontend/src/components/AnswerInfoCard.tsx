import type { AnswerMeta } from "../types";

interface AnswerInfoCardProps {
  meta: AnswerMeta;
}

export default function AnswerInfoCard({
  meta,
}: AnswerInfoCardProps) {
  const items = [
    {
      label: "Subject",
      value: meta.subject,
    },
    {
      label: "Marks",
      value: meta.marks,
    },
    {
      label: "Generation Time",
      value: `${(meta.generationTimeMs / 1000).toFixed(2)} s`,
    },
    {
      label: "Sources Used",
      value: meta.sourcesUsed,
    },
    {
      label: "Word Count",
      value: meta.wordCount,
    },
  ];

  return (
    <div
      style={{
        maxWidth: "900px",
        margin: "20px auto",
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
        gap: "16px",
      }}
    >
      {items.map((item) => (
        <div
          key={item.label}
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: "12px",
            padding: "18px",
            background: "#ffffff",
          }}
        >
          <div
            style={{
              fontSize: "13px",
              color: "#6b7280",
              marginBottom: "8px",
            }}
          >
            {item.label}
          </div>

          <div
            style={{
              fontSize: "20px",
              fontWeight: 700,
            }}
          >
            {item.value}
          </div>
        </div>
      ))}
    </div>
  );
}