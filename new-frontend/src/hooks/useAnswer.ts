import { useState } from "react";
import { api } from "../services/api";
import type {
  AnswerResponse,
  QueryPayload,
  LoadingStage,
} from "../types";

export function useAnswer() {
  const [answer, setAnswer] = useState<AnswerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState<LoadingStage>("idle");
  const [error, setError] = useState("");

  async function ask(payload: QueryPayload) {
    try {
      setLoading(true);
      setError("");
      setAnswer(null);

      setStage("searching");

      await new Promise((r) => setTimeout(r, 300));

      setStage("retrieving");

      await new Promise((r) => setTimeout(r, 300));

      setStage("generating");

      const res = await api.post(
  "/generate-answer",
  {
    topic: payload.question,
    marks: payload.marks,
    subject: payload.subject,
  }
);
console.log(res.data);
      setStage("formatting");

      await new Promise((r) => setTimeout(r, 300));

      setAnswer({
       answerMarkdown: res.data.answer,
       meta: {
       subject: res.data.subject,
       marks: res.data.marks,
       generationTimeMs: 0,
       sourcesUsed: res.data.sources?.length ?? 0,
       wordCount: res.data.answer.split(/\s+/).length,
  },
});
      setStage("done");
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ??
          "Unable to generate answer."
      );
      setStage("idle");
    } finally {
      setLoading(false);
    }
  }

  return {
    ask,
    answer,
    loading,
    stage,
    error,
  };
}