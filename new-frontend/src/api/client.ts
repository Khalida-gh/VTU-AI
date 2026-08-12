import axios from "axios";
import type { QueryPayload, AnswerResponse } from "../types";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
  timeout: 300000, // 5 minutes
});

export async function generateAnswer(
  payload: QueryPayload
): Promise<AnswerResponse> {
  const { data } = await api.post<AnswerResponse>("/answer", payload);
  return data;
}

export default api;