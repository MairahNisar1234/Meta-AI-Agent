"use client";

import {
  useState,
  useRef,
  useEffect,
  useCallback,
  type KeyboardEvent,
} from "react";
import { streamChat, type StreamEvent } from "@/lib/api";

// Tiny markdown renderer
function parseMarkdown(text: string): string {
  return text
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h3>$1</h3>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br />");
}

//  Types 
interface Message {
  id: string;
  role: "user" | "agent";
  content: string;        // final text
  streaming?: boolean;    // still receiving tokens
  tool?: string | null;   // currently active tool
}

interface ToolEvent {
  name: string;
  active: boolean;
}

// Greeting shown on first open 
const GREETING = `👋 Hi! I'm your **Agent Builder**.

Tell me what kind of agent you want, and I'll build it for you — including the full \`agent.py\`, \`.env\`, and a \`ui.html\` frontend.

**Examples:**
- *Build me a cricket score agent*
- *Create a stock price assistant*
- *Make a mental health support chatbot*

What would you like to build?`;

//  Component
interface Props {
  open: boolean;
  onClose: () => void;
}

let msgCounter = 0;
const uid = () => `msg-${++msgCounter}`;

export default function ChatBot({ open, onClose }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    { id: uid(), role: "agent", content: GREETING },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [toolEvent, setToolEvent] = useState<ToolEvent | null>(null);
  const [threadId] = useState(() => `thread-${Date.now()}`);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input when opened
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 100);
  }, [open]);

  //  Send message
  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;

    setInput("");
    setBusy(true);
    setToolEvent(null);

    const userMsg: Message = { id: uid(), role: "user", content: text };
    const agentId = uid();
    const agentMsg: Message = {
      id: agentId,
      role: "agent",
      content: "",
      streaming: true,
      tool: null,
    };

    setMessages((prev) => [...prev, userMsg, agentMsg]);

    abortRef.current = new AbortController();
    let accumulated = "";

    try {
      await streamChat(
        { query: text, thread_id: threadId },
        (event: StreamEvent) => {
          switch (event.type) {
            case "token":
              accumulated += event.content;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === agentId
                    ? { ...m, content: accumulated, streaming: true }
                    : m
                )
              );
              break;

            case "tool_start":
              setToolEvent({ name: event.tool, active: true });
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === agentId ? { ...m, tool: event.tool } : m
                )
              );
              break;

            case "tool_end":
              setToolEvent({ name: event.tool, active: false });
              setTimeout(() => setToolEvent(null), 1200);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === agentId ? { ...m, tool: null } : m
                )
              );
              break;

            case "done":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === agentId ? { ...m, streaming: false, tool: null } : m
                )
              );
              setBusy(false);
              break;

            case "error":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === agentId
                    ? {
                        ...m,
                        content: `⚠️ **Error:** ${event.detail}`,
                        streaming: false,
                      }
                    : m
                )
              );
              setBusy(false);
              break;
          }
        },
        abortRef.current.signal
      );
    } catch (err: unknown) {
      const msg =
        err instanceof Error && err.name === "AbortError"
          ? "Request cancelled."
          : `⚠️ **Connection error:** ${err instanceof Error ? err.message : String(err)}`;

      setMessages((prev) =>
        prev.map((m) =>
          m.id === agentId ? { ...m, content: msg, streaming: false } : m
        )
      );
      setBusy(false);
    }
  }, [input, busy, threadId]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const cancel = () => {
    abortRef.current?.abort();
  };

  //  Render 
  if (!open) return null;

  return (
    <div
      className="animate-slide-in-right fixed bottom-6 right-6 z-50 flex flex-col"
      style={{
        width: "min(420px, calc(100vw - 24px))",
        height: "min(620px, calc(100vh - 96px))",
      }}
    >
      {/* Panel */}
      <div
        className="glass flex flex-col w-full h-full rounded-2xl overflow-hidden"
        style={{ boxShadow: "0 8px 60px rgba(99,102,241,0.25), 0 2px 20px rgba(0,0,0,0.6)" }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-3 border-b"
          style={{ borderColor: "var(--border)" }}
        >
          <div className="flex items-center gap-3">
            {/* Animated bot avatar */}
            <div
              className="animate-pulse-glow flex items-center justify-center rounded-full text-lg font-bold select-none"
              style={{
                width: 38,
                height: 38,
                background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
              }}
            >
              🤖
            </div>
            <div>
              <div className="font-semibold text-sm" style={{ color: "var(--text)" }}>
                Agent Builder
              </div>
              <div className="text-xs flex items-center gap-1" style={{ color: "var(--muted)" }}>
                <span
                  className="inline-block w-1.5 h-1.5 rounded-full"
                  style={{ background: busy ? "#f59e0b" : "#22c55e" }}
                />
                {busy ? "Building..." : "Ready"}
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="rounded-lg p-1.5 transition-colors hover:bg-white/10"
            aria-label="Close chat"
            style={{ color: "var(--muted)" }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tool indicator */}
        {toolEvent && (
          <div
            className="px-4 py-1.5 text-xs flex items-center gap-2 animate-fade-in"
            style={{ background: "rgba(99,102,241,0.12)", color: "#a5b4fc" }}
          >
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ background: "#6366f1", boxShadow: "0 0 6px #6366f1" }}
            />
            {toolEvent.active ? `Running ${toolEvent.name}…` : `✓ ${toolEvent.name} done`}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={msg.role === "user" ? "bubble-user" : "bubble-agent"}
            >
              {msg.role === "agent" ? (
                <>
                  <div
                    dangerouslySetInnerHTML={{
                      __html: parseMarkdown(msg.content),
                    }}
                  />
                  {msg.streaming && !msg.content && (
                    <div className="typing-indicator flex gap-1 mt-1">
                      <span /><span /><span />
                    </div>
                  )}
                  {msg.streaming && msg.content && (
                    <span
                      className="inline-block w-0.5 h-4 ml-0.5 rounded-sm"
                      style={{
                        background: "var(--accent)",
                        animation: "blink-cursor 1s step-end infinite",
                        verticalAlign: "text-bottom",
                      }}
                    />
                  )}
                </>
              ) : (
                <span>{msg.content}</span>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <div
          className="px-3 pb-3 pt-2 border-t"
          style={{ borderColor: "var(--border)" }}
        >
          <div
            className="flex items-end gap-2 rounded-xl px-3 py-2"
            style={{
              background: "var(--surface2)",
              border: "1px solid var(--border)",
            }}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={busy}
              placeholder="Describe the agent you want to build…"
              rows={1}
              className="flex-1 resize-none bg-transparent text-sm outline-none placeholder:opacity-40"
              style={{
                color: "var(--text)",
                maxHeight: 120,
                lineHeight: 1.5,
              }}
            />

            {busy ? (
              <button
                onClick={cancel}
                className="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
                style={{
                  background: "rgba(239,68,68,0.15)",
                  color: "#f87171",
                  border: "1px solid rgba(239,68,68,0.3)",
                }}
              >
                Stop
              </button>
            ) : (
              <button
                onClick={send}
                disabled={!input.trim()}
                className="rounded-lg p-2 transition-all disabled:opacity-30"
                style={{
                  background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                  color: "#fff",
                }}
                aria-label="Send"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M22 2 11 13M22 2 15 22 11 13 2 9l20-7z" />
                </svg>
              </button>
            )}
          </div>
          <p className="text-center text-xs mt-2" style={{ color: "var(--muted)" }}>
            Press <kbd className="px-1 py-0.5 rounded text-xs" style={{ background: "var(--surface2)", border: "1px solid var(--border)" }}>Enter</kbd> to send · <kbd className="px-1 py-0.5 rounded text-xs" style={{ background: "var(--surface2)", border: "1px solid var(--border)" }}>Shift+Enter</kbd> for new line
          </p>
        </div>
      </div>
    </div>
  );
}
