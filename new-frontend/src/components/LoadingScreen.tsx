import type { LoadingStage } from "../types";
import { LOADING_STAGE_LABELS } from "../types";

interface LoadingScreenProps {
  stage: LoadingStage;
}

export default function LoadingScreen({
  stage,
}: LoadingScreenProps) {
  if (stage === "idle" || stage === "done") return null;

  return (
    <div
      style={{
        maxWidth: "900px",
        margin: "30px auto",
        padding: "24px",
        border: "1px solid #e5e7eb",
        borderRadius: "12px",
        background: "#ffffff",
        textAlign: "center",
      }}
    >
      <h2>Generating Answer...</h2>

      <p
        style={{
          color: "#6b7280",
          marginTop: "12px",
          fontSize: "16px",
        }}
      >
        {LOADING_STAGE_LABELS[stage]}
      </p>

      <div
        style={{
          marginTop: "20px",
          fontSize: "40px",
        }}
      >
        ⏳
      </div>
    </div>
  );
}