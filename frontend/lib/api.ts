/** Typed client for the Agent Builder FastAPI backend. */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ChatRequest {
  query: string;
  thread_id: string;
}

export interface GeneratedFile {
  name: string;
  download_url: string;
  size: number;
}

//  Streaming event types 
export type StreamEvent =
  | { type: "token";         content: string }
  | { type: "tool_start";    tool: string }
  | { type: "tool_end";      tool: string }
  | { type: "file_saved";    file: string; tool: string }
  | { type: "agent_created"; result: string; agent_name: string | null; files: GeneratedFile[]; task_type: string }
  | { type: "done" }
  | { type: "error";         detail: string };

// Stream chat with SSE 
export async function streamChat(
  request: ChatRequest,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Server error ${res.status}: ${text}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;
      try {
        const event = JSON.parse(line.slice(6)) as StreamEvent;
        onEvent(event);
      } catch {
        // skip malformed lines
      }
    }
  }
}

// Health check 
export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

// Download a generated file 
export function getDownloadUrl(agentName: string, filename: string): string {
  return `${API_BASE}/download/${encodeURIComponent(agentName)}/${encodeURIComponent(filename)}`;
}
