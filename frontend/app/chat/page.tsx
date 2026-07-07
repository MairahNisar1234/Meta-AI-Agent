"use client";

import Link from "next/link";
import {
  useState, useRef, useEffect, useCallback,
  type KeyboardEvent,
} from "react";
import { streamChat, getDownloadUrl, type StreamEvent, type GeneratedFile } from "@/lib/api";
import ThemeToggle from "@/components/ThemeToggle";

function md(text: string) {
  return text
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm,  "<h3>$1</h3>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br />");
}

interface Message {
  id: string; role: "user" | "agent";
  content: string; streaming?: boolean;
  agentName?: string; files?: GeneratedFile[];
}

let counter = 0;
const uid = () => `c${++counter}`;

const FILE_ICONS: Record<string, string> = { "agent.py": "🐍", ".env": "🔑", "ui.html": "🌐" };
const FILE_DESC: Record<string, string>  = {
  "agent.py": "FastAPI + LangGraph backend",
  ".env":     "API keys (fill in your keys)",
  "ui.html":  "Ready-to-use browser UI",
};

function DownloadCard({ agentName, files }: { agentName: string; files: GeneratedFile[] }) {
  return (
    <div style={{
      marginTop: 12,
      background: "rgba(120,50,220,.08)",
      border: "1px solid rgba(130,80,255,.25)",
      borderRadius: 12,
      padding: "12px 14px",
    }}>
      <p style={{ fontSize: ".8rem", fontWeight: 700, color: "var(--accent2)", marginBottom: 10 }}>
        📦 {agentName} — download generated files
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
        {files.map((f) => (
          <a
            key={f.name}
            href={getDownloadUrl(agentName, f.name)}
            download={f.name}
            style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "8px 12px", borderRadius: 8,
              background: "rgba(130,80,255,.1)",
              border: "1px solid rgba(130,80,255,.22)",
              textDecoration: "none",
              transition: "background .18s, transform .15s",
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(130,80,255,.2)"; (e.currentTarget as HTMLElement).style.transform = "translateX(2px)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(130,80,255,.1)"; (e.currentTarget as HTMLElement).style.transform = "translateX(0)"; }}
          >
            <span style={{ fontSize: "1.15rem", flexShrink: 0 }}>{FILE_ICONS[f.name] ?? "📄"}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ fontWeight: 600, fontSize: ".82rem", color: "var(--text)", margin: 0 }}>{f.name}</p>
              <p style={{ fontSize: ".72rem", color: "var(--muted)", margin: 0 }}>{FILE_DESC[f.name] ?? ""}</p>
            </div>
            <span style={{ fontSize: ".7rem", color: "var(--dim)", flexShrink: 0 }}>{(f.size / 1024).toFixed(1)} KB</span>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--accent2)" strokeWidth="2.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
            </svg>
          </a>
        ))}
      </div>
      <p style={{ fontSize: ".7rem", color: "var(--muted)", marginTop: 10, lineHeight: 1.6 }}>
        <strong style={{ color: "var(--dim)" }}>Run locally:</strong>{" "}
        <code style={{ background: "rgba(130,80,255,.12)", borderRadius: 4, padding: "1px 5px", color: "var(--accent2)" }}>
          cd generated_agents/{agentName} &amp;&amp; python agent.py
        </code>
        {" "}then open{" "}
        <code style={{ background: "rgba(130,80,255,.12)", borderRadius: 4, padding: "1px 5px", color: "var(--accent2)" }}>
          http://127.0.0.1:8000
        </code>
      </p>
    </div>
  );
}

const GREETING = `👋 Hi! I'm your **Agent Builder**.

Tell me what kind of agent you want and I'll generate the complete \`agent.py\`, \`.env\` and \`ui.html\` — ready to run immediately.

**Try asking:**
- Build me a cricket score agent
- Create a stock price assistant
- Make a mental health support chatbot
- Build a currency converter
- Create a news summarizer`;

const EXAMPLES = [
  "🏏 Cricket score agent",
  "📈 Stock price tracker",
  "🌤 Weather assistant",
  "📰 News summarizer",
  "💬 Mental health chatbot",
  "💱 Currency converter",
  "📦 Inventory manager",
  "🎵 Music recommender",
];

export default function ChatPage() {
  const [msgs,     setMsgs]    = useState<Message[]>([{ id: uid(), role: "agent", content: GREETING }]);
  const [input,    setInput]   = useState("");
  const [busy,     setBusy]    = useState(false);
  const [tool,     setTool]    = useState<string | null>(null);
  const [progress, setProgress] = useState<string[]>([]);
  const [thread]               = useState(() => `t-${Date.now()}`);
  const [sidebar,  setSidebar] = useState(true);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLTextAreaElement>(null);
  const abortRef  = useRef<AbortController | null>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);
  useEffect(() => { setTimeout(() => inputRef.current?.focus(), 120); }, []);

  const resize = () => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 150)}px`;
  };

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    if (inputRef.current) inputRef.current.style.height = "auto";
    setBusy(true); setTool(null); setProgress([]);

    const agentId = uid();
    setMsgs((p) => [
      ...p,
      { id: uid(), role: "user",  content: text },
      { id: agentId, role: "agent", content: "", streaming: true },
    ]);

    abortRef.current = new AbortController();
    let acc = "";

    try {
      await streamChat({ query: text, thread_id: thread }, (ev: StreamEvent) => {
        switch (ev.type) {
          case "token":
            acc += ev.content;
            setMsgs((p) => p.map((m) => m.id === agentId ? { ...m, content: acc } : m));
            break;
          case "tool_start": setTool(ev.tool); break;
          case "tool_end":   setTool(null); break;
          case "file_saved":
            if (ev.file) setProgress((p) => [...new Set([...p, ev.file])]);
            setTool(null);
            break;
          case "agent_created":
            setMsgs((p) => p.map((m) =>
              m.id === agentId
                ? { ...m, content: ev.result, streaming: false, agentName: ev.agent_name ?? undefined, files: ev.files }
                : m
            ));
            setTool(null); setProgress([]); setBusy(false);
            break;
          case "done":
            setMsgs((p) => p.map((m) => m.id === agentId ? { ...m, streaming: false } : m));
            setBusy(false); break;
          case "error":
            setMsgs((p) => p.map((m) =>
              m.id === agentId ? { ...m, content: `⚠️ **Error:** ${ev.detail}`, streaming: false } : m
            ));
            setBusy(false); break;
        }
      }, abortRef.current.signal);
    } catch (err: unknown) {
      const msg = err instanceof Error && err.name === "AbortError"
        ? "Cancelled."
        : `⚠️ Connection error: ${err instanceof Error ? err.message : String(err)}`;
      setMsgs((p) => p.map((m) => m.id === agentId ? { ...m, content: msg, streaming: false } : m));
      setBusy(false);
    }
  }, [input, busy, thread]);

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  return (
    <div
      style={{
        display: "flex",
        height: "100dvh",
        overflow: "hidden",
        background: "var(--bg)",
        fontFamily: "'Space Grotesk', system-ui, sans-serif",
        position: "relative",
      }}
    >
      {/* bg blob */}
      <div style={{
        position: "fixed", borderRadius: "50%", pointerEvents: "none", zIndex: 0,
        width: "clamp(300px,55vw,700px)", height: "clamp(220px,40vw,500px)",
        top: "45%", left: "50%",
        transform: "translate(-50%,-50%)",
        background: "radial-gradient(ellipse,var(--blob1a) 0%,var(--blob1b) 40%,transparent 72%)",
        filter: "blur(70px)",
        animation: "breathe 8s ease-in-out infinite",
      }} aria-hidden />

      {/* ── SIDEBAR ─────────────────────────────────────────────────── */}
      <aside
        style={{
          width: sidebar ? 230 : 0,
          flexShrink: 0,
          overflow: "hidden",
          transition: "width .3s",
          background: "var(--sidebar-bg)",
          borderRight: "1px solid var(--sidebar-border)",
          display: "flex",
          flexDirection: "column",
          zIndex: 20,
        }}
      >
        {/* inner — fixed 230px so transitions don't reflow content */}
        <div style={{ width: 230, display: "flex", flexDirection: "column", height: "100%" }}>
          {/* header */}
          <div style={{
            display: "flex", alignItems: "center", gap: 9,
            padding: "14px 14px",
            borderBottom: "1px solid var(--sidebar-border)",
          }}>
            <div style={{
              width: 26, height: 26, borderRadius: 7,
              background: "linear-gradient(135deg,#5b21b6,#a855f7)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: ".85rem", flexShrink: 0,
            }}>🤖</div>
            <span style={{ fontWeight: 700, fontSize: ".88rem", color: "var(--text)", letterSpacing: "-.01em" }}>
              AgentBuilder
            </span>
          </div>

          {/* new chat */}
          <div style={{ padding: "10px 10px 6px" }}>
            <button
              onClick={() => {
                counter = 0;
                setMsgs([{ id: uid(), role: "agent", content: GREETING }]);
                setInput("");
              }}
              style={{
                width: "100%",
                display: "flex", alignItems: "center", gap: 7,
                padding: "9px 12px",
                borderRadius: 10,
                fontSize: ".82rem", fontWeight: 600,
                color: "var(--text)",
                background: "rgba(130,80,255,.12)",
                border: "1px solid rgba(130,80,255,.28)",
                cursor: "pointer",
                transition: "background .2s",
                fontFamily: "inherit",
              }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 5v14M5 12h14" />
              </svg>
              New conversation
            </button>
          </div>

          {/* examples */}
          <div style={{ padding: "4px 10px", flex: 1, overflowY: "auto" }}>
            <p style={{ fontSize: ".68rem", fontWeight: 700, textTransform: "uppercase",
              letterSpacing: ".08em", color: "var(--muted)", padding: "4px 4px 6px" }}>
              Quick examples
            </p>
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                onClick={() => { setInput(ex.replace(/^\S+\s/, "")); setTimeout(() => inputRef.current?.focus(), 40); }}
                style={{
                  display: "block", width: "100%", textAlign: "left",
                  padding: "7px 8px", borderRadius: 8,
                  fontSize: ".78rem", color: "var(--dim)",
                  background: "transparent", border: "none",
                  cursor: "pointer",
                  transition: "background .18s, color .18s",
                  fontFamily: "inherit",
                }}
                onMouseEnter={(e) => { const el = e.currentTarget as HTMLElement; el.style.background = "rgba(130,80,255,.08)"; el.style.color = "var(--text)"; }}
                onMouseLeave={(e) => { const el = e.currentTarget as HTMLElement; el.style.background = "transparent"; el.style.color = "var(--dim)"; }}
              >
                {ex}
              </button>
            ))}
          </div>

          {/* back */}
          <div style={{ padding: "8px 10px", borderTop: "1px solid var(--sidebar-border)" }}>
            <Link href="/" style={{ textDecoration: "none" }}>
              <button
                style={{
                  width: "100%", display: "flex", alignItems: "center", gap: 7,
                  padding: "7px 8px", borderRadius: 8,
                  fontSize: ".78rem", color: "var(--muted)",
                  background: "transparent", border: "none", cursor: "pointer",
                  transition: "background .18s, color .18s", fontFamily: "inherit",
                }}
                onMouseEnter={(e) => { const el = e.currentTarget as HTMLElement; el.style.background = "rgba(130,80,255,.08)"; el.style.color = "var(--text)"; }}
                onMouseLeave={(e) => { const el = e.currentTarget as HTMLElement; el.style.background = "transparent"; el.style.color = "var(--muted)"; }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M19 12H5M12 5l-7 7 7 7" />
                </svg>
                Back to home
              </button>
            </Link>
          </div>
        </div>
      </aside>

      {/* ── MAIN CHAT ───────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", position: "relative", zIndex: 10, minWidth: 0 }}>

        {/* top bar */}
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "0 16px", height: 54, flexShrink: 0,
          background: "rgba(7,7,26,.55)",
          backdropFilter: "blur(18px)", WebkitBackdropFilter: "blur(18px)",
          borderBottom: "1px solid var(--sidebar-border)",
        }}>
          {/* hamburger */}
          <button
            onClick={() => setSidebar((v) => !v)}
            style={{
              width: 30, height: 30, borderRadius: 8, border: "none",
              background: "transparent", color: "var(--dim)",
              display: "flex", alignItems: "center", justifyContent: "center",
              cursor: "pointer", flexShrink: 0,
            }}
            aria-label="Toggle sidebar"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 12h18M3 6h18M3 18h18" />
            </svg>
          </button>

          {/* title */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              width: 24, height: 24, borderRadius: 7,
              background: "linear-gradient(135deg,#5b21b6,#a855f7)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: ".78rem", flexShrink: 0,
            }}>🤖</div>
            <span style={{ fontWeight: 600, fontSize: ".9rem", color: "var(--text)", letterSpacing: "-.01em" }}>
              Agent Builder
            </span>
          </div>

          {/* status */}
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span className={busy ? "dot-busy" : "dot-live"} />
            <span style={{ fontSize: ".72rem", color: "var(--muted)" }}>
              {busy ? (tool ? `Running ${tool}` : "Thinking…") : "Ready"}
            </span>
          </div>

          <div style={{ flex: 1 }} />
          <ThemeToggle />
        </div>

        {/* tool banner */}
        {tool && (
          <div className="fi" style={{
            padding: "5px 16px", fontSize: ".74rem",
            display: "flex", alignItems: "center", gap: 7,
            background: "rgba(130,60,220,.1)", color: "var(--accent2)",
            borderBottom: "1px solid rgba(130,80,255,.14)",
          }}>
            <span style={{ width:7, height:7, borderRadius:"50%", background:"var(--accent2)", boxShadow:"0 0 7px var(--accent2)", display:"inline-block", flexShrink:0 }} />
            Executing <strong style={{ color:"var(--text)" }}>{tool}</strong>…
          </div>
        )}
        {/* file generation progress */}
        {busy && progress.length > 0 && (
          <div style={{
            padding: "5px 16px", fontSize: ".73rem",
            display: "flex", alignItems: "center", gap: 10,
            background: "rgba(34,197,94,.06)", color: "var(--dim)",
            borderBottom: "1px solid rgba(34,197,94,.15)",
          }}>
            <span style={{ color: "#22c55e", fontWeight: 600, flexShrink: 0 }}>Generated:</span>
            {["agent.py", ".env", "ui.html"].map((f) => (
              <span key={f} style={{ color: progress.includes(f) ? "#22c55e" : "var(--muted)", display: "flex", alignItems: "center", gap: 3 }}>
                {progress.includes(f) ? "✓" : "○"} {f}
              </span>
            ))}
          </div>
        )}

        {/* messages */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px clamp(14px,3vw,28px)", display: "flex", flexDirection: "column", gap: 14 }}>
          {msgs.map((m) => (
            <div key={m.id} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start", gap: 10 }}>
              {m.role === "agent" && (
                <div style={{
                  width: 26, height: 26, borderRadius: 8, flexShrink: 0, marginTop: 2,
                  background: "linear-gradient(135deg,#5b21b6,#7c3aed)",
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: ".78rem",
                }}>🤖</div>
              )}
              <div
                className={m.role === "user" ? "bub-u" : "bub-a"}
                style={{ maxWidth: "min(72%, 600px)" }}
              >
                {m.role === "agent" ? (
                  <>
                    <div dangerouslySetInnerHTML={{ __html: md(m.content) }} />
                    {m.streaming && !m.content && <div className="typing" style={{ marginTop: 4 }}><span /><span /><span /></div>}
                    {m.streaming && m.content && (
                      <span style={{ display:"inline-block", width:2, height:"1em", background:"var(--accent2)", marginLeft:2, verticalAlign:"text-bottom", animation:"blink .9s step-end infinite" }} />
                    )}
                    {!m.streaming && m.agentName && m.files && m.files.length > 0 && (
                      <DownloadCard agentName={m.agentName} files={m.files} />
                    )}
                  </>
                ) : m.content}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* input */}
        <div style={{ padding: "10px clamp(14px,3vw,28px) 16px", borderTop: "1px solid var(--sidebar-border)", flexShrink: 0 }}>
          <div style={{
            display: "flex", alignItems: "flex-end", gap: 10,
            background: "var(--input-bg)", border: "1px solid var(--input-border)",
            borderRadius: 14, padding: "10px 12px",
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
                fontSize: ".875rem", lineHeight: 1.56, maxHeight: 150,
                fontFamily: "'Space Grotesk', system-ui, sans-serif",
              }}
            />
            {busy ? (
              <button
                onClick={() => abortRef.current?.abort()}
                style={{
                  flexShrink: 0, padding: "6px 14px", borderRadius: 9,
                  fontSize: ".78rem", fontWeight: 600,
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
                  flexShrink: 0, width: 36, height: 36, borderRadius: 10,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  background: input.trim() ? "linear-gradient(135deg,#7c3aed,#a855f7)" : "rgba(130,80,255,.15)",
                  color: "#fff", border: "none",
                  cursor: input.trim() ? "pointer" : "not-allowed",
                  opacity: input.trim() ? 1 : .3,
                  transition: "opacity .2s, transform .15s",
                  boxShadow: input.trim() ? "0 3px 12px rgba(120,50,220,.4)" : "none",
                }}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M22 2 11 13M22 2 15 22 11 13 2 9l20-7z" />
                </svg>
              </button>
            )}
          </div>
          <p style={{ textAlign: "center", fontSize: ".68rem", color: "var(--muted)", marginTop: 6 }}>
            <kbd style={{ padding:"1px 5px", borderRadius:4, background:"var(--kbd-bg)", border:"1px solid var(--kbd-border)", fontFamily:"inherit" }}>Enter</kbd>
            {" "}to send ·{" "}
            <kbd style={{ padding:"1px 5px", borderRadius:4, background:"var(--kbd-bg)", border:"1px solid var(--kbd-border)", fontFamily:"inherit" }}>Shift+Enter</kbd>
            {" "}for new line
          </p>
        </div>
      </div>
    </div>
  );
}
