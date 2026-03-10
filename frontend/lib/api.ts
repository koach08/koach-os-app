import type { MessageMetadata } from "./types";

interface ChatParams {
  message: string;
  domain: string;
  history: { role: string; content: string }[];
  engine_override?: string | null;
  level_override?: string | null;
  acceptance_gradient?: string | null;
}

interface StreamCallbacks {
  onMetadata: (meta: MessageMetadata) => void;
  onText: (chunk: string) => void;
  onDone: () => void;
  onError: (error: string) => void;
}

export async function streamChat(params: ChatParams, callbacks: StreamCallbacks) {
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });

    if (!res.ok) {
      callbacks.onError(`API error: ${res.status}`);
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      callbacks.onError("No response stream");
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === "metadata") callbacks.onMetadata(data.data);
          else if (data.type === "text") callbacks.onText(data.data);
          else if (data.type === "done") callbacks.onDone();
        } catch {
          // skip malformed lines
        }
      }
    }
  } catch (err) {
    callbacks.onError(String(err));
  }
}

export async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ─── Style Analysis API ───

export async function analyzeText(text: string, context: string, genre: string) {
  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, context, genre }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `API error: ${res.status}` }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function analyzeUpload(file: File, context: string, genre: string) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("context", context);
  formData.append("genre", genre);
  const res = await fetch("/api/analyze/upload", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `API error: ${res.status}` }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function analyzeBatch(
  files: File[],
  context: string,
  genre: string,
): Promise<{
  total: number;
  analyzed: number;
  failed: number;
  results: { file: string; id: string; extracted_length: number; voice_summary: string }[];
  errors: { file: string; error: string }[];
}> {
  const formData = new FormData();
  for (const f of files) formData.append("files", f);
  formData.append("context", context);
  formData.append("genre", genre);
  const res = await fetch("/api/analyze/batch", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `API error: ${res.status}` }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function analyzeUrl(url: string, genre: string) {
  const res = await fetch("/api/analyze/url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, genre }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `API error: ${res.status}` }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function analyzeGDrive(url: string, genre: string) {
  const res = await fetch("/api/analyze/gdrive", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, genre }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `API error: ${res.status}` }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function fetchSampleCount(): Promise<{ total: number; by_genre: Record<string, number> }> {
  return fetchJSON("/api/analyze/samples");
}

export async function fetchStyleGuide(): Promise<{ content: string; exists: boolean }> {
  return fetchJSON("/api/analyze/style-guide");
}

export async function regenerateStyleGuide(): Promise<{ content: string }> {
  const res = await fetch("/api/analyze/regenerate", { method: "POST" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
