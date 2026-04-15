import type { ChatMessage } from "./types";

export const SERVICE_URL = import.meta.env.VITE_FEEDBACK_SERVICE_URL || "http://localhost:3001";

export function apiHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const apiKey = import.meta.env.VITE_PIPELINE_API_KEY;
  if (apiKey) headers["x-api-key"] = apiKey;
  return headers;
}

export async function sendChatMessage(
  message: string,
  history: { role: string; content: string }[],
  userId?: string
): Promise<{ reply: string; sources: string[]; message_id: string | null }> {
  const response = await fetch(`${SERVICE_URL}/chat`, {
    method: "POST",
    headers: apiHeaders(),
    body: JSON.stringify({ message, history, user_id: userId }),
  });

  if (!response.ok) {
    throw new Error("Failed to get response from mentor");
  }

  return response.json();
}

export async function submitFeedback(
  messageId: string,
  feedback: "helpful" | "not_helpful"
): Promise<void> {
  const response = await fetch(`${SERVICE_URL}/chat/feedback`, {
    method: "POST",
    headers: apiHeaders(),
    body: JSON.stringify({ message_id: messageId, feedback }),
  });
  if (!response.ok) throw new Error("Failed to submit feedback");
}

export function formatHistory(messages: ChatMessage[]) {
  return messages.map((m) => ({
    role: m.role,
    content: m.content,
  }));
}
