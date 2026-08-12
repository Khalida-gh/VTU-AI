export type ThemeMode = "light" | "dark";

export const VTU_SUBJECTS = [
  "Data Structures",
  "Operating Systems",
  "Database Management Systems",
  "Computer Networks",
  "Software Engineering",
  "Object Oriented Programming",
  "Design and Analysis of Algorithms",
  "Computer Organization and Architecture",
  "Discrete Mathematical Structures",
  "Microcontrollers",
  "Web Technologies",
  "Artificial Intelligence",
  "Machine Learning",
  "Cloud Computing",
  "Compiler Design",
] as const;

export type VtuSubject = (typeof VTU_SUBJECTS)[number];

export interface QueryPayload {
  subject: string;
  question: string;
  marks: number;
}

export interface KnownAnswerMeta {
  subject: string;
  marks: number;
  generationTimeMs: number;
  sourcesUsed: number;
  wordCount: number;
}

export type AnswerMeta = KnownAnswerMeta & Record<string, unknown>;

export interface AnswerResponse {
  answerMarkdown: string;
  meta: AnswerMeta;
}

export interface HistoryEntry {
  id: string;
  question: string;
  subject: string;
  marks: number;
  timestamp: number;
  answerMarkdown: string;
  meta: AnswerMeta;
}

export type LoadingStage =
  | "idle"
  | "searching"
  | "retrieving"
  | "generating"
  | "formatting"
  | "done";

export const LOADING_STAGE_LABELS: Record<
  Exclude<LoadingStage, "idle" | "done">,
  string
> = {
  searching: "Searching notes...",
  retrieving: "Retrieving relevant context...",
  generating: "Generating answer...",
  formatting: "Formatting response...",
};

export interface ApiErrorShape {
  message: string;
  status?: number;
}

export const RENDERED_META_KEYS: (keyof KnownAnswerMeta)[] = [
  "subject",
  "marks",
  "generationTimeMs",
  "sourcesUsed",
  "wordCount",
];