"use client";

import {
  useState, useRef, useEffect, useCallback,
  type KeyboardEvent,
} from "react";
import { streamChat, getDownloadUrl, type StreamEvent, type GeneratedFile } from "@/lib/api";

/* ── markdown ────────────────────────────────────────────────────────────── */
function md(text: string) {
  return text
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm,  "<h3>$1</h3>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br />");
}

/* ── types ───────────────────────────────────────────────────────────────── */
interface Msg {
  id: string;
  role: "user" | "agent";
  content: string;
  streaming?: boolean;
  /* attached when agent_created fires */
  agentName?: string;
  files?: GeneratedFile[];
}
let seq = 0;
const uid = () => `m${++seq}`;

const GREETING = `👋 Hi! I'm your **Agent Builder**.

Tell me what kind of agent you want and I'll generate the full \`agent.py\`, \`.env\` and \`ui.html\` — ready to run.

**Examples:**
- Build me a cricket score agent
- Create a stock price assistant
- Make a mental health support chatbot`;

/* ── file icon map ───────────────────────────────────────────────────────── */
const FILE_ICONS: Record<string, string> = {
  "agent.py": "🐍",
  ".env":     "🔑",
  "ui.html":  "🌐",
};
const FILE_DESC: Record<string, string> = {
  "agent.py": "FastAPI + LangGraph backend",
  ".env":     "API keys (fill in your keys)",
  "ui.html":  "Ready-to-use browser UI",
};

/* ── DownloadCard ────────────────────────────────────────────────────────── */
function DownloadCard({ agentName, files }: { agentName: string; files: GeneratedFile[] }) {
  return (
    <div style={{
      marginTop: 10,
      background: "rgba(120,50,220,.08)",
      border: "1px solid rgba(130,80,255,.25)",
      borderRadius: 12,
      padding: "12px 14px",
    }}>
      <p style={{ fontSize: ".78rem", fontWeight: 700, color: "var(--accent2)", marginBottom: 8, letterSpacing: ".01em" }}>
        📦 {agentName} — download files
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {files.map((f) => (
          <a
            key={f.name}
            href={getDownloadUrl(agentName, f.name)}
            download={f.name}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "7px 10px",
              borderRadius: 8,
              background: "rgba(130,80,255,.1)",
              border: "1px solid rgba(130,80,255,.2)",
              textDecoration: "none",
              transition: "background .18s, transform .15s",
              cursor: "pointer",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background = "rgba(130,80,255,.2)";
              (e.currentTarget as HTMLElement).style.transform = "translateX(2px)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = "rgba(130,80,255,.1)";
              (e.currentTarget as HTMLElement).style.transform = "translateX(0)";
            }}
          >
            <span style={{ fontSize: "1.1rem", flexShrink: 0 }}>{FILE_ICONS[f.name] ?? "📄"}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ fontWeight: 600, fontSize: ".8rem", color: "var(--text)", margin: 0 }}>{f.name}</p>
              <p style={{ fontSize: ".7rem", color: "var(--muted)", margin: 0 }}>{FILE_DESC[f.name] ?? ""}</p>
            </div>
            <span style={{ fontSize: ".68rem", color: "var(--dim)", flexShrink: 0 }}>
              {(f.size / 1024).toFixed(1)} KB
            </span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--accent2)" strokeWidth="2.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
            </svg>
          </a>
        ))}
      </div>
      <p style={{ fontSize: ".68rem", color: "var(--muted)", marginTop: 8, lineHeight: 1.5 }}>
        Run: <code style={{ background: "rgba(130,80,255,.12)", borderRadius: 4, padding: "1px 5px", color: "var(--accent2)" }}>
          cd generated_agents/{agentName} &amp;&amp; python agent.py
        </code>
      </p>
    </div>
  );
}

/* ── component ───────────────────────────────────────────────────────────── */
export default function InlineChat() {
  const [msgs,   setMsgs]   = useState<Msg[]>([{ id: uid(), role: "agent", content: GREETING }]);
  const [input,  setInput]  = useState("");
  const [busy,   setBusy]   = useState(false);
  const [tool,   setTool]   = useState<string | null>(null);
  const [progress, setProgress] = useState<string[]>([]);
  const [thread] = useState(() => `t-${Date.now()}`);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLTextAreaElement>(null);
  const abortRef  = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  useEffect(() => {
    const h = (e: Event) => {
      setInput((e as CustomEvent<string>).detail);
      setTimeout(() => inputRef.current?.focus(), 40);
    };
    window.addEventListener("agent-example", h);
    return () => window.removeEventListener("agent-example", h);
  }, []);

  const resize = () => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 108)}px`;
  };

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;

    setInput("");
    if (inputRef.current) inputRef.current.style.height = "auto";
    setBusy(true);
    setTool(null);
    setProgress([]);

    const agentId = uid();
    setMsgs((p) => [
      ...p,
      { id: uid(), role: "user", content: text },
      { id: agentId, role: "agent", content: "", streaming: true },
    ]);

    abortRef.current = new AbortController();
    let acc = "";

    try {
      await streamChat(
        { query: text, thread_id: thread },
        (ev: StreamEvent) => {
          switch (ev.type) {
            case "token":
              acc += ev.content;
              setMsgs((p) => p.map((m) => m.id === agentId ? { ...m, content: acc } : m));
              break;

            case "tool_start":
              setTool(ev.tool);
              break;

            case "tool_end":
              setTool(null);
              break;

            case "file_saved":
              if (ev.file) {
                setProgress((p) => [...new Set([...p, ev.file])]);
              }
              setTool(null);
              break;

            case "agent_created":
              // Replace the streaming message with the rich completion message
              setMsgs((p) => p.map((m) =>
                m.id === agentId
                  ? {
                      ...m,
                      content: ev.result,
                      streaming: false,
                      agentName: ev.agent_name ?? undefined,
                      files: ev.files,
                    }
                  : m
              ));
              setTool(null);
              setProgress([]);
              setBusy(false);
              break;

            case "done":
              // done fires after agent_created — just make sure streaming is cleared
              setMsgs((p) => p.map((m) => m.id === agentId ? { ...m, streaming: false } : m));
              setBusy(false);
              break;

            case "error":
              setMsgs((p) => p.map((m) =>
                m.id === agentId
                  ? { ...m, content: `⚠️ **Error:** ${ev.detail}`, streaming: false }
                  : m
              ));
              setBusy(false);
              break;
          }
        },
        abortRef.current.signal
      );
    } catch (err: unknown) {
      const msg =
        err instanceof Error && err.name === "AbortError"
          ? "Cancelled."
          : `⚠️ Connection error: ${err instanceof Error ? err.message : String(err)}`;
      setMsgs((p) => p.map((m) => m.id === agentId ? { ...m, content: msg, streaming: false } : m));
      setBusy(false);
    }
  }, [input, busy, thread]);

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  /* ── render ─────────────────────────────────────────────────────────── */
  return (
    <div
      className="glass"
      style={{
        borderRadius: 18,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        boxShadow: "0 0 0 1px rgba(130,80,255,.2), 0 20px 56px rgba(60,20,180,.22), 0 4px 16px rgba(0,0,0,.3)",
      }}
    >
      {/* ── HEADER ──────────────────────────────────────────────────── */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "12px 16px",
        borderBottom: "1px solid var(--border)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: 10,
            background: "linear-gradient(135deg,#4c1d95,#7c3aed,#a855f7)",
            boxShadow: "0 0 14px rgba(120,58,220,.5)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "1rem", userSelect: "none", flexShrink: 0,
          }}>🤖</div>
          <div>
            <p style={{ fontWeight: 600, fontSize: ".88rem", color: "var(--text)", letterSpacing: "-.01em", lineHeight: 1.2 }}>
              Agent Builder
            </p>
            <p style={{ fontSize: ".72rem", color: "var(--muted)", display: "flex", alignItems: "center", gap: 5, marginTop: 2 }}>
              {busy
                ? <><span className="dot-busy" />{tool ? `Saving ${tool.replace("save_code_to_file", "files")}…` : "Building agent…"}</>
                : <><span className="dot-live" />Ready to build</>
              }
            </p>
          </div>
        </div>
        <div style={{ display: "flex", gap: 5 }}>
          {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
            <span key={c} style={{ width: 10, height: 10, borderRadius: "50%", background: c, opacity: .65 }} />
          ))}
        </div>
      </div>

      {/* ── PROGRESS BAR ────────────────────────────────────────────── */}
      {busy && (
        <div className="fi" style={{
          padding: "6px 16px",
          fontSize: ".73rem",
          display: "flex", alignItems: "center", gap: 8,
          background: "rgba(130,60,220,.08)",
          borderBottom: "1px solid rgba(130,80,255,.12)",
          color: "var(--dim)",
        }}>
          <span style={{ color: "var(--accent2)", fontWeight: 600 }}>Generating:</span>
          {["agent.py", ".env", "ui.html"].map((f) => (
            <span key={f} style={{
              display: "inline-flex", alignItems: "center", gap: 3,
              color: progress.includes(f) ? "#22c55e" : "var(--muted)",
            }}>
              {progress.includes(f) ? "✓" : "○"} {f}
            </span>
          ))}
        </div>
      )}

      {/* ── MESSAGES ────────────────────────────────────────────────── */}
      <div style={{
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        gap: 10,
        padding: "14px 14px",
        minHeight: "clamp(180px, 28vh, 260px)",
        maxHeight: "clamp(260px, 38vh, 380px)",
      }}>
        {msgs.map((m) => (
          <div key={m.id} className={m.role === "user" ? "bub-u" : "bub-a"}>
            {m.role === "agent" ? (
              <>
                <div dangerouslySetInnerHTML={{ __html: md(m.content) }} />
                {m.streaming && !m.content && (
                  <div className="typing"><span /><span /><span /></div>
                )}
                {m.streaming && m.content && (
                  <span style={{
                    display: "inline-block", width: 2, height: "1em",
                    background: "var(--accent2)", marginLeft: 2,
                    verticalAlign: "text-bottom",
                    animation: "blink .9s step-end infinite",
                  }} />
                )}
                {/* Download card — shown when files are ready */}
                {!m.streaming && m.agentName && m.files && m.files.length > 0 && (
                  <DownloadCard agentName={m.agentName} files={m.files} />
                )}
              </>
            ) : m.content}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* ── INPUT ───────────────────────────────────────────────────── */}
      <div style={{ padding: "10px 12px 14px", borderTop: "1px solid var(--border)" }}>
        <div style={{
          display: "flex", alignItems: "flex-end", gap: 8,
          background: "var(--input-bg)",
          border: "1px solid var(--input-border)",
          borderRadius: 12,
          padding: "9px 11px",
        }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => { setInput(e.target.value); resize(); }}
            onKeyDown={onKey}
            disabled={busy}
            placeholder="Describe the agent you want to build…"
            rows={1}
            style={{
              flex: 1, resize: "none", background: "transparent",
              border: "none", outline: "none", color: "var(--text)",
              fontSize: ".875rem", lineHeight: 1.55, maxHeight: 108,
              fontFamily: "'Space Grotesk', system-ui, sans-serif",
            }}
          />
          {busy ? (
            <button
              onClick={() => abortRef.current?.abort()}
              style={{
                flexShrink: 0, padding: "5px 11px", borderRadius: 8,
                fontSize: ".74rem", fontWeight: 600,
                background: "rgba(239,68,68,.12)", color: "#f87171",
                border: "1px solid rgba(239,68,68,.25)", cursor: "pointer",
                fontFamily: "inherit", whiteSpace: "nowrap",
              }}
            >Stop</button>
          ) : (
            <button
              onClick={send}
              disabled={!input.trim()}
              aria-label="Send"
              style={{
                flexShrink: 0, width: 32, height: 32, borderRadius: 8,
                display: "flex", alignItems: "center", justifyContent: "center",
                background: input.trim() ? "linear-gradient(135deg,#7c3aed,#a855f7)" : "rgba(130,80,255,.15)",
                color: "#fff", border: "none",
                cursor: input.trim() ? "pointer" : "not-allowed",
                opacity: input.trim() ? 1 : .3,
                transition: "opacity .2s, transform .15s",
                boxShadow: input.trim() ? "0 3px 12px rgba(120,50,220,.4)" : "none",
              }}
              onMouseEnter={(e) => { if (input.trim()) (e.currentTarget as HTMLElement).style.transform = "scale(1.06)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.transform = "scale(1)"; }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M22 2 11 13M22 2 15 22 11 13 2 9l20-7z" />
              </svg>
            </button>
          )}
        </div>
        <p style={{ textAlign: "center", fontSize: ".69rem", color: "var(--muted)", marginTop: 7 }}>
          <kbd style={{ padding: "1px 5px", borderRadius: 4, background: "var(--kbd-bg)", border: "1px solid var(--kbd-border)", fontFamily: "inherit" }}>Enter</kbd>
          {" "}to send ·{" "}
          <kbd style={{ padding: "1px 5px", borderRadius: 4, background: "var(--kbd-bg)", border: "1px solid var(--kbd-border)", fontFamily: "inherit" }}>Shift+Enter</kbd>
          {" "}for new line
        </p>
      </div>
    </div>
  );
}
