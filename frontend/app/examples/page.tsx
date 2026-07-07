"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import ThemeToggle from "@/components/ThemeToggle";
import { API_BASE } from "@/lib/api";
import type { LucideIcon } from "lucide-react";

import {
  Bot,
  Brain,
  HeartHandshake,
  Flame,
  BookOpen,
  Plane,
  Map,
  CloudSun,
  Cloud,
  ChartCandlestick,
  Trophy,
  Coins,
  HeartPulse,
  ClipboardList,
  Package,
  Truck,
  FilePenLine,
  Mic,
  GraduationCap,
} from "lucide-react";


/* ── types ───────────────────────────────────────────────────────────── */
interface AgentFile {
  name: string;
  download_url: string;
  size: number;
}

interface Agent {
  id: string;
  canonical_name: string;
  display_name: string;
  original_prompt: string;
  category: string;
  current_version: number;
  created_at: string;
  metadata: Record<string, unknown>;
  files: AgentFile[];
  has_files: boolean;
}

/* ── helpers ─────────────────────────────────────────────────────────── */
const AGENT_ICONS: Record<string, LucideIcon> = {
  mental_health_agent: Brain,
  mental_health_assistant: HeartHandshake,
  motivation_agent: Flame,
  study_agent: BookOpen,
  travel_agent: Plane,
  travel_assistant: Map,
  weather_tracker: CloudSun,
  live_weather_agent: Cloud,
  stock_price_agent: ChartCandlestick,
  cricket_score_agent: Trophy,
  currency_converter: Coins,
  health_tracker: HeartPulse,
  hr_policy_assistant: ClipboardList,
  inventory_manager: Package,
  order_status_tracker: Truck,
  content_draft: FilePenLine,
  webinar_tracker: Mic,
  staff_training: GraduationCap,
};


const AGENT_COLORS: Record<string, string> = {
  mental_health_agent:     "#10b981",
  mental_health_assistant: "#10b981",
  motivation_agent:        "#f59e0b",
  study_agent:             "#6366f1",
  travel_agent:            "#3b82f6",
  travel_assistant:        "#3b82f6",
  weather_tracker:         "#06b6d4",
  live_weather_agent:      "#06b6d4",
  stock_price_agent:       "#22c55e",
  cricket_score_agent:     "#f97316",
  currency_converter:      "#a855f7",
  health_tracker:          "#ef4444",
  hr_policy_assistant:     "#8b5cf6",
  inventory_manager:       "#eab308",
  order_status_tracker:    "#14b8a6",
  content_draft:           "#ec4899",
  webinar_tracker:         "#6366f1",
  staff_training:          "#f59e0b",
};

function getIcon(name: string): LucideIcon {
  return AGENT_ICONS[name] ?? Bot;
}
function getColor(name: string) {
  return AGENT_COLORS[name] ?? "#7c3aed";
}

function formatDate(iso: string) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric",
    });
  } catch { return ""; }
}

function prettifyName(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function getFrontendType(meta: Record<string, unknown>): string {
  return (meta?.frontend_type as string) ?? "chat";
}

function getToolsUsed(meta: Record<string, unknown>): string[] {
  return (meta?.tools_needed as string[]) ?? [];
}

const FILE_ICONS: Record<string, string> = {
  "agent.py": "🐍",
  ".env":     "🔑",
  "ui.html":  "🌐",
};


/* ── Agent Card ──────────────────────────────────────────────────────── */
function AgentCard({ agent, onSelect }: { agent: Agent; onSelect: () => void }) {
  const color = getColor(agent.canonical_name);
  const Icon = getIcon(agent.canonical_name);

  return (
    <div
      onClick={onSelect}
      style={{
        borderRadius: 16,
        border: `1px solid ${color}28`,
        background: "var(--surface, rgba(14,14,38,0.85))",
        padding: "18px 18px 14px",
        cursor: "pointer",
        transition: "transform .18s, box-shadow .18s, border-color .18s",
        display: "flex",
        flexDirection: "column",
        gap: 10,
        position: "relative",
        overflow: "hidden",
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLElement;
        el.style.transform = "translateY(-3px)";
        el.style.boxShadow = `0 12px 40px ${color}22`;
        el.style.borderColor = `${color}55`;
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLElement;
        el.style.transform = "translateY(0)";
        el.style.boxShadow = "none";
        el.style.borderColor = `${color}28`;
      }}
    >
      {/* version badge */}
      {agent.current_version > 1 && (
        <span style={{
          position: "absolute", top: 12, right: 12,
          fontSize: ".64rem", fontWeight: 700,
          padding: "2px 7px", borderRadius: 99,
          background: `${color}18`, color: color,
          border: `1px solid ${color}35`,
        }}>
          v{agent.current_version}
        </span>
      )}

      {/* header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 12, flexShrink: 0,
          background: `${color}18`,
          border: `1px solid ${color}35`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: "1.4rem",
        }}>
          <Icon size={24} color={color} />
        </div>
        <div style={{ minWidth: 0 }}>
          <p style={{
            fontWeight: 700, fontSize: ".9rem",
            color: "var(--text)", margin: 0,
            letterSpacing: "-.01em",
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          }}>
            {prettifyName(agent.canonical_name)}
          </p>
          <p style={{ fontSize: ".7rem", color: "var(--muted)", margin: 0, marginTop: 2 }}>
            {formatDate(agent.created_at)}
          </p>
        </div>
      </div>

      {/* prompt */}
      <p style={{
        fontSize: ".78rem", color: "var(--dim)", margin: 0,
        lineHeight: 1.5, fontStyle: "italic",
        display: "-webkit-box",
        WebkitLineClamp: 2,
        WebkitBoxOrient: "vertical",
        overflow: "hidden",
      }}>
        &ldquo;{agent.original_prompt}&rdquo;
      </p>

      {/* tags row */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
        <span style={{
          fontSize: ".65rem", fontWeight: 600,
          padding: "2px 8px", borderRadius: 99,
          background: `${color}14`, color: color,
          border: `1px solid ${color}30`,
        }}>
          {getFrontendType(agent.metadata)} UI
        </span>
        {getToolsUsed(agent.metadata).slice(0, 2).map((t) => (
          <span key={t} style={{
            fontSize: ".65rem", fontWeight: 500,
            padding: "2px 8px", borderRadius: 99,
            background: "rgba(130,80,255,.08)", color: "var(--dim)",
            border: "1px solid rgba(130,80,255,.18)",
          }}>
            {t.replace(/_/g, " ")}
          </span>
        ))}
        {agent.has_files && (
          <span style={{
            fontSize: ".65rem", fontWeight: 600,
            padding: "2px 8px", borderRadius: 99,
            background: "rgba(34,197,94,.1)", color: "#22c55e",
            border: "1px solid rgba(34,197,94,.25)",
          }}>
            ✓ files ready
          </span>
        )}
      </div>

      {/* file count */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        paddingTop: 6,
        borderTop: `1px solid ${color}15`,
      }}>
        <span style={{ fontSize: ".7rem", color: "var(--muted)" }}>
          {agent.files.length} file{agent.files.length !== 1 ? "s" : ""}
        </span>
        <span style={{ fontSize: ".7rem", color: "var(--muted)", marginLeft: "auto" }}>
          View &amp; download →
        </span>
      </div>
    </div>
  );
}


/* ── Detail Modal ────────────────────────────────────────────────────── */
function AgentModal({ agent, onClose }: { agent: Agent; onClose: () => void }) {
  const color = getColor(agent.canonical_name);
  const Icon = getIcon(agent.canonical_name);

  // close on backdrop click
  const handleBackdrop = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div
      onClick={handleBackdrop}
      style={{
        position: "fixed", inset: 0, zIndex: 100,
        background: "rgba(0,0,0,.65)",
        backdropFilter: "blur(6px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 20,
        animation: "fadeIn .2s ease",
      }}
    >
      <div style={{
        width: "100%", maxWidth: 560,
        maxHeight: "90dvh",
        overflowY: "auto",
        borderRadius: 20,
        background: "var(--surface, #0e0e26)",
        border: `1px solid ${color}40`,
        boxShadow: `0 24px 80px rgba(0,0,0,.6), 0 0 0 1px ${color}20`,
        padding: "24px 24px 20px",
        animation: "slideUp .25s cubic-bezier(.22,1,.36,1)",
      }}>
        {/* header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 18 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{
              width: 52, height: 52, borderRadius: 14, flexShrink: 0,
              background: `${color}18`, border: `1px solid ${color}40`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: "1.7rem",
            }}>
              <Icon size={28} color={color} />
            </div>
            <div>
              <h2 style={{
                fontWeight: 700, fontSize: "1.08rem",
                color: "var(--text)", margin: 0, letterSpacing: "-.02em",
              }}>
                {prettifyName(agent.canonical_name)}
              </h2>
              <p style={{ fontSize: ".74rem", color: "var(--muted)", margin: "3px 0 0" }}>
                v{agent.current_version} · {formatDate(agent.created_at)}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 30, height: 30, borderRadius: 8,
              background: "rgba(255,255,255,.06)",
              border: "1px solid rgba(255,255,255,.1)",
              color: "var(--dim)", cursor: "pointer",
              display: "flex", alignItems: "center", justifyContent: "center",
              flexShrink: 0,
            }}
            aria-label="Close"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        {/* original prompt */}
        <div style={{
          background: `${color}0e`,
          border: `1px solid ${color}25`,
          borderRadius: 10, padding: "10px 14px", marginBottom: 16,
        }}>
          <p style={{ fontSize: ".7rem", fontWeight: 700, color: color, margin: "0 0 4px", textTransform: "uppercase", letterSpacing: ".06em" }}>
            Original Prompt
          </p>
          <p style={{ fontSize: ".84rem", color: "var(--text)", margin: 0, lineHeight: 1.6, fontStyle: "italic" }}>
            &ldquo;{agent.original_prompt}&rdquo;
          </p>
        </div>

        {/* metadata pills */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 18 }}>
          {[
            { label: "Frontend: " + getFrontendType(agent.metadata), col: color },
            ...getToolsUsed(agent.metadata).map((t) => ({ label: t.replace(/_/g, " "), col: "#7c3aed" })),
          ].map((p, i) => (
            <span key={i} style={{
              fontSize: ".7rem", fontWeight: 600,
              padding: "3px 10px", borderRadius: 99,
              background: `${p.col}14`, color: p.col,
              border: `1px solid ${p.col}30`,
            }}>
              {p.label}
            </span>
          ))}
        </div>

        {/* files */}
        {agent.files.length > 0 ? (
          <>
            <p style={{
              fontSize: ".78rem", fontWeight: 700, color: "var(--dim)",
              marginBottom: 10, textTransform: "uppercase", letterSpacing: ".06em",
            }}>
              Download Files
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 18 }}>
              {agent.files.map((f) => (
                <a
                  key={f.name}
                  href={`${API_BASE}${f.download_url}`}
                  download={f.name}
                  style={{
                    display: "flex", alignItems: "center", gap: 12,
                    padding: "10px 14px", borderRadius: 10,
                    background: "rgba(130,80,255,.08)",
                    border: "1px solid rgba(130,80,255,.2)",
                    textDecoration: "none",
                    transition: "background .18s, transform .15s",
                    cursor: "pointer",
                  }}
                  onMouseEnter={(e) => {
                    const el = e.currentTarget as HTMLElement;
                    el.style.background = "rgba(130,80,255,.18)";
                    el.style.transform = "translateX(3px)";
                  }}
                  onMouseLeave={(e) => {
                    const el = e.currentTarget as HTMLElement;
                    el.style.background = "rgba(130,80,255,.08)";
                    el.style.transform = "translateX(0)";
                  }}
                >
                  <span style={{ fontSize: "1.2rem", flexShrink: 0 }}>{FILE_ICONS[f.name] ?? "📄"}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontWeight: 700, fontSize: ".82rem", color: "var(--text)", margin: 0 }}>{f.name}</p>
                    <p style={{ fontSize: ".68rem", color: "var(--muted)", margin: 0 }}>
                      {(f.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent2)" strokeWidth="2.5">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>
                  </svg>
                </a>
              ))}
            </div>

            {/* run instructions */}
            <div
  style={{
    background: "rgba(255,255,255,0.08)",
    border: "1px solid rgba(130,80,255,.15)",
    borderRadius: 10,
    padding: "12px 14px",
  }}
>
              <p style={{ fontSize: ".72rem", fontWeight: 700, color: "var(--dim)", margin: "0 0 6px", textTransform: "uppercase", letterSpacing: ".06em" }}>
                Run locally
              </p>
              <pre style={{
                fontSize: ".74rem", color: "#c084fc",
                fontFamily: "'Fira Code', monospace",
                margin: 0, lineHeight: 1.7,
                background: "none", whiteSpace: "pre-wrap",
              }}>
{`cd generated_agents/${agent.canonical_name}
pip install fastapi uvicorn python-dotenv
# fill in your API keys in .env
python agent.py
# open http://127.0.0.1:8000`}
              </pre>
            </div>
          </>
        ) : (
          <div style={{
            padding: "16px", borderRadius: 10,
            background: "rgba(245,158,11,.08)",
            border: "1px solid rgba(245,158,11,.25)",
            textAlign: "center",
          }}>
            <p style={{ fontSize: ".82rem", color: "#f59e0b", margin: 0 }}>
              ⚠️ Files not found on disk for this agent.
            </p>
            <p style={{ fontSize: ".74rem", color: "var(--muted)", margin: "4px 0 0" }}>
              The agent record exists in the database but its generated files may have been deleted.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}


/* ── Page ────────────────────────────────────────────────────────────── */
export default function ExamplesPage() {
  const [agents,   setAgents]   = useState<Agent[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState<string | null>(null);
  const [selected, setSelected] = useState<Agent | null>(null);
  const [filter,   setFilter]   = useState<"all" | "files">("all");

  useEffect(() => {
    fetch(`${API_BASE}/agents/list`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => { setAgents(d.agents ?? []); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, []);

  const filtered = filter === "files"
    ? agents.filter((a) => a.has_files)
    : agents;

  return (
    <div style={{ minHeight: "100dvh", display: "flex", flexDirection: "column" }}>
      <div className="blob-1" aria-hidden />
      <div className="blob-2" aria-hidden />
      <div className="grid-bg" aria-hidden />

      {/* NAVBAR */}
      <header style={{
        position: "sticky", top: 0, zIndex: 50,
        background: "var(--nav-bg)",
        backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)",
        borderBottom: "1px solid var(--nav-border)",
      }}>
        <div style={{
          maxWidth: 1100, width: "100%", margin: "0 auto",
          padding: "0 clamp(16px,4vw,32px)", height: 58,
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
        }}>
          <Link href="/" style={{ textDecoration: "none" }}>
            <span style={{ fontWeight: 700, fontSize: "1rem", letterSpacing: "-.02em", color: "var(--text)" }}>
              AgentBuilder
            </span>
          </Link>
          <nav style={{ display: "flex", alignItems: "center", gap: 2 }} className="hidden sm:flex">
             <Link href="/#" style={{ textDecoration: "none" }}><span className="nav-link">Home</span></Link>
            <Link href="/how-it-works" style={{ textDecoration: "none" }}><span className="nav-link">How it works</span></Link>
            <span className="nav-link" style={{ color: "var(--accent2)", fontWeight: 700 }}>Examples</span>
            
          </nav>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <ThemeToggle />
            <Link href="/chat">
              <span className="pill-btn">Build your own →</span>
            </Link>
          </div>
        </div>
      </header>

      <main style={{
        position: "relative", zIndex: 1, flex: 1,
        padding: "clamp(36px,5vw,70px) clamp(16px,4vw,32px) clamp(36px,5vw,70px)",
      }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>

          {/* HERO */}
          <div className="su" style={{ textAlign: "center", marginBottom: "clamp(36px,5vw,56px)" }}>
            <div style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "5px 16px", borderRadius: 999,
              fontSize: ".76rem", fontWeight: 500, color: "var(--dim)",
              background: "rgba(130,80,255,.1)", border: "1px solid rgba(130,80,255,.28)",
              marginBottom: 20,
            }}>
               {loading ? "Loading…" : `${agents.length} agent${agents.length !== 1 ? "s" : ""} built`}
            </div>
            <h1 style={{
              fontWeight: 700,
              fontSize: "clamp(1.9rem,4.5vw,3.2rem)",
              letterSpacing: "-.034em", lineHeight: 1.14,
              color: "var(--text)", marginBottom: 14,
            }}>
              Agents built by<br />
              <span className="g-text">AgentBuilder</span>
            </h1>
            <p style={{
              fontSize: "clamp(.88rem,2vw,.96rem)",
              color: "var(--dim)", maxWidth: 480, margin: "0 auto", lineHeight: 1.7,
            }}>
              Every agent below was generated from a plain-English prompt.
              Click any card to preview and download its files.
            </p>
          </div>

          {/* FILTER BAR */}
          {!loading && !error && (
            <div style={{
              display: "flex", alignItems: "center", gap: 10,
              marginBottom: 28, flexWrap: "wrap",
            }}>
              <span style={{ fontSize: ".78rem", color: "var(--muted)" }}>Show:</span>
              {(["all", "files"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  style={{
                    padding: "5px 14px", borderRadius: 99,
                    fontSize: ".78rem", fontWeight: 600,
                    cursor: "pointer", fontFamily: "inherit",
                    background: filter === f ? "var(--accent)" : "rgba(130,80,255,.08)",
                    color: filter === f ? "#fff" : "var(--dim)",
                    border: filter === f ? "1px solid var(--accent)" : "1px solid rgba(130,80,255,.22)",
                    transition: "all .18s",
                  }}
                >
                  {f === "all" ? `All (${agents.length})` : `Files ready (${agents.filter((a) => a.has_files).length})`}
                </button>
              ))}
            </div>
          )}

          {/* STATES */}
          {loading && (
            <div style={{ textAlign: "center", padding: "60px 20px" }}>
              <div style={{
                width: 40, height: 40, borderRadius: "50%", margin: "0 auto 16px",
                border: "3px solid rgba(130,80,255,.2)",
                borderTopColor: "var(--accent)",
                animation: "spin .7s linear infinite",
              }} />
              <p style={{ color: "var(--dim)", fontSize: ".88rem" }}>
                Loading agents from the database…
              </p>
            </div>
          )}

          {error && (
            <div style={{
              textAlign: "center", padding: "48px 20px",
              borderRadius: 16,
              background: "rgba(239,68,68,.07)",
              border: "1px solid rgba(239,68,68,.25)",
            }}>
              <p style={{ fontSize: "1.5rem", marginBottom: 10 }}>⚠️</p>
              <p style={{ color: "#f87171", fontWeight: 600, marginBottom: 8 }}>
                Could not load agents
              </p>
              <p style={{ fontSize: ".8rem", color: "var(--muted)" }}>
                Make sure the backend is running at{" "}
                <code style={{ color: "var(--accent2)" }}>{API_BASE}</code>
              </p>
              <p style={{ fontSize: ".75rem", color: "var(--muted)", marginTop: 6 }}>
                Error: {error}
              </p>
            </div>
          )}

          {!loading && !error && filtered.length === 0 && (
            <div style={{
              textAlign: "center", padding: "48px 20px",
              borderRadius: 16,
              background: "rgba(130,80,255,.06)",
              border: "1px solid rgba(130,80,255,.2)",
            }}>
              <p style={{ fontSize: "1.5rem", marginBottom: 10 }}>🤖</p>
              <p style={{ color: "var(--dim)", fontWeight: 600 }}>No agents yet</p>
              <p style={{ fontSize: ".8rem", color: "var(--muted)", marginTop: 6 }}>
                Build your first one using the chat builder!
              </p>
              <Link href="/chat" style={{ textDecoration: "none" }}>
                <span className="pill-btn" style={{ marginTop: 16, display: "inline-flex" }}>
                  Start Building →
                </span>
              </Link>
            </div>
          )}

          {/* GRID */}
          {!loading && !error && filtered.length > 0 && (
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
              gap: 16,
            }}>
              {filtered.map((agent) => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  onSelect={() => setSelected(agent)}
                />
              ))}
            </div>
          )}

          {/* CTA BOTTOM */}
          {!loading && !error && filtered.length > 0 && (
            <div style={{ textAlign: "center", marginTop: 48 }}>
              <p style={{ fontSize: ".86rem", color: "var(--dim)", marginBottom: 16 }}>
                Want to add yours to this list?
              </p>
              <Link href="/">
                <span className="pill-btn" style={{ fontSize: ".9rem", padding: "12px 28px" }}>
                  Build a new agent →
                </span>
              </Link>
            </div>
          )}

        </div>
      </main>

      <footer style={{
        position: "relative", zIndex: 1, textAlign: "center",
        padding: "14px clamp(16px,4vw,32px)",
        fontSize: ".74rem", color: "var(--muted)",
        borderTop: "1px solid var(--divider)",
      }}>
        © 2025 AgentBuilder · Powered by LangGraph &amp; Gemini
      </footer>

      {/* MODAL */}
      {selected && (
        <AgentModal agent={selected} onClose={() => setSelected(null)} />
      )}

      <style>{`
        @keyframes fadeIn  { from { opacity:0 } to { opacity:1 } }
        @keyframes slideUp { from { opacity:0; transform:translateY(20px) scale(.97) } to { opacity:1; transform:none } }
        @keyframes spin    { to   { transform:rotate(360deg) } }
      `}</style>
    </div>
  );
}
