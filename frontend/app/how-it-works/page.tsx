"use client";

import Link from "next/link";
import { useState, useEffect, useRef } from "react";
import ThemeToggle from "@/components/ThemeToggle";
import {
  Search,
  Zap,
  GitBranch,
  Code2,
  Wrench,
  ShieldCheck,
  HardDrive,
  CheckCircle2,
  Telescope,
  PenSquare,
  Monitor,
  Brain,
  Cog,
  Download,
  Database,
  Globe,
  Sparkles,
  Cpu,
  Server,

} from "lucide-react";

/* ═══════════════════════════════════════════════════════
   DATA — maps exactly to graph.py pipeline
═══════════════════════════════════════════════════════ */

const PIPELINE_NODES = [
  {
    id: "parser",
    icon: <Search size={22} />,
    label: "Parser",
    color: "#6366f1",
    shadow: "rgba(99,102,241,0.4)",
    description: "Intent classification via Gemini 2.5 Flash",
    detail: "Receives your plain-English prompt and calls parse_query_to_spec(). Uses Gemini to output a structured AgentSpec JSON: agent_name, task_type (code_gen or research), tools_needed, frontend_type, and requires_web_search.",
    code: `# app/core/parser.py
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
spec = AgentSpec(
  agent_name="travel_agent",
  task_type="code_gen",
  tools_needed=["save_code_to_file"],
  frontend_type="chat",
)`,
  },
  {
    id: "realtime_detector",
    icon: <Zap size={22} />,
    label: "Realtime Detector",
    color: "#f59e0b",
    shadow: "rgba(245,158,11,0.4)",
    description: "Detects if live data APIs are needed",
    detail: "Checks the parsed spec for categories like cricket, stocks, weather, currency. If detected, enriches realtime_config with the exact API endpoint, key env var, free tier info, and a pre-validated tool template — injected directly into the coder's system prompt.",
    code: `# app/agents/realtime_detector.py
realtime_config = {
  "category": "cricket",
  "api_name": "CricAPI",
  "live_url": "https://api.cricapi.com/v1/currentMatches",
  "key_env_var": "CRICAPI_KEY",
  "tool_template": "...",  # verified code
}`,
  },
  {
    id: "supervisor",
    icon: <GitBranch size={22} />,
    label: "Supervisor",
    color: "#8b5cf6",
    shadow: "rgba(139,92,246,0.4)",
    description: "Routes to Coder or Researcher",
    detail: "A simple routing node: if task_type == 'code_gen' → routes to the Coder pipeline. Otherwise → routes to the Researcher pipeline. Determines the entire downstream flow from a single field.",
    code: `# app/agents/graph.py — supervisor_node
def supervisor_node(state):
    spec = state["agent_spec"]
    next_agent = (
        "coder" if spec.task_type == "code_gen"
        else "researcher"
    )
    return {"next_agent": next_agent}`,
  },
  {
    id: "coder",
    icon: <Code2 size={22} />,
    label: "Coder",
    color: "#10b981",
    shadow: "rgba(16,185,129,0.4)",
    description: "Generates agent.py, .env and ui.html",
    detail: "The main generation node. Binds save_code_to_file tool to Gemini with tool_choice='required'. Retries up to 5× until all 3 files are accumulated. Loads dev_standards.md and ui_standards.md as guardrails. Locks the canonical agent name to prevent folder drift.",
    code: `# app/agents/graph.py — coder_node
bound_llm = llm.bind_tools(
    [save_code_to_file], tool_choice="required"
)
# Retries until 3 files present:
# agent.py  .env  ui.html`,
  },
  {
    id: "import_fixer",
    icon: <Wrench size={22} />,
    label: "Import Fixer",
    color: "#06b6d4",
    shadow: "rgba(6,182,212,0.4)",
    description: "Deterministic import correction pass",
    detail: "Before any file hits disk, runs fix_imports() and fix_code_patterns() over every tool call argument. Replaces banned imports (langchain_core.pydantic_v1, TavilySearchResults, ChatOpenAI) with correct ones. Runs purely on regex — no LLM call.",
    code: `# app/agents/code_fixes.py
BAD_IMPORTS = {
  "from langchain_core.pydantic_v1": 
    "from pydantic",
  "TavilySearchResults": 
    "TavilySearch",
}
code, changes = fix_imports(code)`,
  },
  {
    id: "validator",
    icon: <ShieldCheck size={22} />,
    color: "#a855f7",
    label: "Validator",
    shadow: "rgba(168,85,247,0.4)",
    description: "Checks generated code against hard rules",
    detail: "Validates tool call code arguments against banned patterns and required blocks before writing to disk. Checks for missing set_entry_point, conflicting edges, missing @tool decorators, and dead state fields. Emits warnings but doesn't block — issues are logged.",
    code: `# app/agents/code_fixes.py
issues = validate_generated_code(code, filename)
# Checks: entry_point, @tool, ToolNode,
# duplicate kwargs, missing CORS, etc.`,
  },
  {
    id: "code_tools",
    icon: <HardDrive size={22} />,
    label: "Code Tools (ToolNode)",
    color: "#f97316",
    shadow: "rgba(249,115,22,0.4)",
    description: "Executes save_code_to_file — writes files to disk",
    detail: "LangGraph ToolNode that physically executes save_code_to_file. Merges .env files (never overwrites existing API keys). Copies staged realtime .env from current_agent/ to the real agent folder. Files land in generated_agents/<agent_name>/.",
    code: `# app/agents/coder_tools.py
@tool
def save_code_to_file(filename, code) -> str:
    path = os.path.join(
        settings.generated_agents_dir, filename
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)`,
  },
  {
    id: "runtime_check",
    icon: <CheckCircle2 size={22} />,
    label: "Runtime Check",
    color: "#22c55e",
    shadow: "rgba(34,197,94,0.4)",
    description: "Syntax-checks and persists to SQLite",
    detail: "Runs py_compile on the generated agent.py to catch syntax errors. On a clean pass, persists the agent to agents.db (SQLite) via save_agent() or save_new_version(). Archives code in agent_registry/<name>__<id>/v<n>/ for version history.",
    code: `# app/agents/persistence.py
py_compile.compile(agent_py_path, doraise=True)
agent_id = save_agent(
    canonical_name=agent_name,
    source_code_dir=agent_dir,
    category=category,   # cricket, stocks…
)  # → agents.db + agent_registry/`,
  },
];

const RESEARCHER_NODES = [
  {
    id: "researcher",
    icon: <Telescope size={22} />,
    label: "Researcher",
    color: "#3b82f6",
    shadow: "rgba(59,130,246,0.4)",
    description: "Web research via TavilySearch",
    detail: "When task_type is 'research', the researcher node invokes TavilySearch (max 2 results) and returns the findings as a streaming response. Loops back to itself until the LLM stops emitting tool calls.",
    code: `# Researcher path
search_tool = TavilySearch(max_results=2)
response = llm.bind_tools(
    [search_tool]
).invoke(messages)`,
  },
];

const STEP_CARDS = [
  {
    number: "01",
    icon: <PenSquare size={24} />,
    title: "Describe Your Agent",
    body: "Type a plain-English description in the chat. No syntax, no config files — just what you want the agent to do.",
    example: '"Build me a cricket score agent with live scores"',
    color: "#6366f1",
  },
  {
    number: "02",
    icon: <Brain size={24} />,
    title: "AI Parses & Plans",
    body: "Gemini 2.5 Flash classifies your intent into a structured spec: agent name, tools needed, frontend type, and whether live APIs are required.",
    example: 'task_type: "code_gen" · tools: ["save_code_to_file"] · realtime: cricket',
    color: "#f59e0b",
  },
  {
    number: "03",
    icon: <Cog size={24} />,
    title: "Multi-Step Generation",
    body: "The coder node generates all 3 files with up to 5 retry attempts. An import fixer and validator run deterministically before anything touches disk.",
    example: "agent.py · .env · ui.html — all generated & validated",
    color: "#10b981",
  },
  {
    number: "04",
    icon: <Download size={24} />,
    title: "Download & Run",
    body: "Files are saved to generated_agents/ and served for download. Add your API keys to .env and run python agent.py to start your agent.",
    example: "cd generated_agents/cricket_agent && python agent.py",
    color: "#a855f7",
  },
];

const STATE_FIELDS = [
  { key: "query", type: "str", desc: "Original user prompt — passed unchanged through the whole graph" },
  { key: "messages", type: "Annotated[list[BaseMessage], operator.add]", desc: "Accumulates all LLM / tool / human messages. operator.add merges across nodes." },
  { key: "agent_spec", type: "Optional[AgentSpec]", desc: "Structured intent: agent_name, task_type, tools_needed, frontend_type, requires_web_search" },
  { key: "next_agent", type: "str", desc: "Set by supervisor_node — 'coder' or 'researcher'" },
  { key: "realtime_config", type: "Optional[dict]", desc: "API config injected by realtime_detector: endpoint URL, key var, tool template" },
  { key: "agent_id", type: "Optional[str]", desc: "8-char UUID returned by persistence.save_agent() after a successful syntax check" },
];


/* ═══════════════════════════════════════════════════════
   SUB-COMPONENTS
═══════════════════════════════════════════════════════ */

function PipelineNode({
  node, active, onClick, index,
}: {
  node: typeof PIPELINE_NODES[0];
  active: boolean;
  onClick: () => void;
  index: number;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
        cursor: "pointer",
        background: "none",
        border: "none",
        padding: 0,
        flexShrink: 0,
        width: 90,
      }}
    >
      {/* circle */}
     <div
  style={{
    width: 56,
    height: 56,
    borderRadius: "50%",

    background: active
      ? "rgba(255,255,255,0.08)"
      : "var(--surface2, rgba(20,20,50,0.8))",

    border: active
      ? `2px solid ${node.color}`
      : "2px solid rgba(130,80,255,0.25)",

    boxShadow: active
      ? `0 0 10px ${node.color}40`
      : "none",

    display: "flex",
    alignItems: "center",
    justifyContent: "center",

    transition: "all .25s",

    transform: active ? "scale(1.08)" : "scale(1)",
  }}
>
  {node.icon}
</div>
      <span style={{
        fontSize: ".72rem",
        fontWeight: active ? 700 : 500,
        color: active ? node.color : "var(--dim)",
        textAlign: "center",
        lineHeight: 1.3,
        transition: "color .25s",
      }}>
        {node.label}
      </span>
      {/* index badge */}
      <span style={{
        fontSize: ".6rem",
        fontWeight: 700,
        color: "var(--muted)",
        letterSpacing: ".06em",
      }}>
        {String(index + 1).padStart(2, "0")}
      </span>
    </button>
  );
}

function Arrow({ color }: { color: string }) {
  return (
    <div style={{
      display: "flex", alignItems: "center",
      flexShrink: 0, paddingBottom: 28,
    }}>
      <div style={{ width: 24, height: 2, background: `${color}60` }} />
      <div style={{
        width: 0, height: 0,
        borderTop: "5px solid transparent",
        borderBottom: "5px solid transparent",
        borderLeft: `7px solid ${color}80`,
      }} />
    </div>
  );
}

function DetailPanel({ node }: { node: typeof PIPELINE_NODES[0] }) {
  return (
    <div
      style={{
        borderRadius: 16,
        border: "1px solid rgba(255,255,255,0.08)",
        background: "var(--surface, rgba(14,14,38,0.92))",
        overflow: "hidden",
        animation: "fadeIn .25s ease",
      }}
    >
      {/* Accent bar */}
      <div
        style={{
          height: 4,
          background: node.color,
        }}
      />

      <div
        style={{
          padding: "20px 24px",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginBottom: 18,
          }}
        >
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: 12,
              background: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(255,255,255,0.10)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {node.icon}
          </div>

          <div>
            <h3
              style={{
                margin: 0,
                fontWeight: 700,
                fontSize: "1rem",
                color: "var(--text)",
              }}
            >
              {node.label}
            </h3>

            <p
              style={{
                margin: 0,
                marginTop: 2,
                fontSize: ".78rem",
                color: "var(--muted)",
              }}
            >
              {node.description}
            </p>
          </div>
        </div>

        {/* Description */}
        <p
          style={{
            fontSize: ".86rem",
            color: "var(--text)",
            lineHeight: 1.75,
            marginBottom: 18,
          }}
        >
          {node.detail}
        </p>

        {/* Code */}
        <pre
          style={{
            background: "#1f2937",
            border: "1px solid #374151",
            borderRadius: 10,
            padding: "14px 16px",
            margin: 0,
            overflowX: "auto",
            fontSize: ".75rem",
            color: "#f9fafb",
            fontFamily: "'Fira Code', 'Fira Mono', monospace",
            lineHeight: 1.65,
          }}
        >
          {node.code}
        </pre>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════
   PAGE
═══════════════════════════════════════════════════════ */

export default function HowItWorksPage() {
  const [activeNode, setActiveNode] = useState<string>("parser");
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  const activeNodeData =
    PIPELINE_NODES.find((n) => n.id === activeNode) ??
    RESEARCHER_NODES.find((n) => n.id === activeNode);

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
            <span className="nav-link" style={{ color: "var(--accent2)", fontWeight: 700 }}>How it works</span>
            <Link href="/examples" style={{ textDecoration: "none" }}><span className="nav-link">Examples</span></Link>
            
          </nav>
         <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <ThemeToggle />
            
          </div> 
        </div>
      </header>

      <main style={{
        position: "relative", zIndex: 1, flex: 1,
        padding: "clamp(40px,6vw,80px) clamp(16px,4vw,32px) clamp(40px,6vw,80px)",
      }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>

          {/* HERO */}
          <div className="su" style={{ textAlign: "center", marginBottom: "clamp(48px,6vw,80px)" }}>
            <div style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "5px 16px", borderRadius: 999,
              fontSize: ".76rem", fontWeight: 500,
              color: "var(--dim)",
              background: "rgba(130,80,255,.1)",
              border: "1px solid rgba(130,80,255,.28)",
              marginBottom: 20,
            }}>
               Under the hood
            </div>
            <h1 style={{
              fontWeight: 700,
              fontSize: "clamp(1.9rem,4.5vw,3.2rem)",
              letterSpacing: "-.034em",
              lineHeight: 1.14,
              color: "var(--text)",
              marginBottom: 16,
            }}>
              How AgentBuilder works<br />
              <span className="g-text">the LangGraph pipeline</span>
            </h1>
            <p style={{
              fontSize: "clamp(.9rem,2vw,.98rem)",
              color: "var(--dim)",
              maxWidth: 560,
              margin: "0 auto",
              lineHeight: 1.72,
            }}>
              Every agent you describe goes through a deterministic multi-node graph.
              Click any node below to see exactly what it does.
            </p>
          </div>

          {/* ── STEP CARDS ───────────────────────────────────────────── */}
          <section style={{ marginBottom: "clamp(48px,6vw,80px)" }}>
            <h2 style={{
              fontWeight: 700, fontSize: "1.1rem",
              color: "var(--text)", marginBottom: 24,
              textAlign: "center", letterSpacing: "-.02em",
            }}>
              From prompt to running agent in 4 steps
            </h2>
            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))",
              gap: 16,
            }}>
              {STEP_CARDS.map((s) => (
                <div key={s.number} style={{
                  borderRadius: 16,
                  background: "var(--surface, rgba(14,14,38,0.85))",
                  border: "1px solid rgba(130,80,255,0.16)",
                  padding: "20px 18px",
                  position: "relative",
                  overflow: "hidden",
                }}>
                  {/* background number */}
                  <span style={{
                    position: "absolute", top: -4, right: 12,
                    fontSize: "4rem", fontWeight: 900,
                    color: `${s.color}12`,
                    lineHeight: 1, userSelect: "none",
                    letterSpacing: "-.04em",
                  }}>{s.number}</span>
                  <span style={{ fontSize: "1.5rem", display: "block", marginBottom: 10 }}>{s.icon}</span>
                  <h3 style={{
                    fontWeight: 700, fontSize: ".92rem",
                    color: s.color, marginBottom: 8, lineHeight: 1.3,
                  }}>
                    {s.title}
                  </h3>
                  <p style={{ fontSize: ".8rem", color: "var(--dim)", lineHeight: 1.65, marginBottom: 12 }}>
                    {s.body}
                  </p>
                  <code style={{
                    display: "block",
                    fontSize: ".72rem",
                    background: `${s.color}14`,
                    border: `1px solid ${s.color}30`,
                    borderRadius: 8,
                    padding: "6px 10px",
                    color: s.color,
                    fontFamily: "'Fira Code', monospace",
                    lineHeight: 1.5,
                    wordBreak: "break-all",
                  }}>
                    {s.example}
                  </code>
                </div>
              ))}
            </div>
          </section>

          {/* ── INTERACTIVE PIPELINE ─────────────────────────────────── */}
          <section style={{ marginBottom: "clamp(48px,6vw,80px)" }}>
            <h2 style={{
              fontWeight: 700, fontSize: "1.1rem",
              color: "var(--text)", marginBottom: 8,
              letterSpacing: "-.02em",
            }}>
              LangGraph pipeline — click any node to inspect
            </h2>
            <p style={{ fontSize: ".8rem", color: "var(--muted)", marginBottom: 28 }}>
              Code generation path · nodes run left → right
            </p>

            {/* scrollable node row */}
            <div style={{
              overflowX: "auto",
              paddingBottom: 12,
              marginBottom: 20,
            }}>
              <div style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 0,
                minWidth: "max-content",
                padding: "8px 4px",
              }}>
                {PIPELINE_NODES.map((node, i) => (
                  <div key={node.id} style={{ display: "flex", alignItems: "flex-start" }}>
                    <PipelineNode
                      node={node}
                      active={activeNode === node.id}
                      onClick={() => setActiveNode(node.id)}
                      index={i}
                    />
                    {i < PIPELINE_NODES.length - 1 && (
                      <Arrow color={activeNode === node.id ? node.color : "#6366f120"} />
                    )}
                  </div>
                ))}
                {/* END node */}
                <div style={{ display: "flex", alignItems: "flex-start" }}>
                  <Arrow color="#22c55e40" />
                  <div style={{
                    display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
                  }}>
                    <div
  style={{
    width: 56,
    height: 56,
    borderRadius: "50%",
    background: "rgba(34,197,94,0.12)",
    border: "2px solid rgba(34,197,94,0.4)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  }}
>
  <CheckCircle2
    size={28}
    color="#22c55e"
    strokeWidth={2.5}
  />
</div>
                    <span style={{ fontSize: ".72rem", fontWeight: 500, color: "#22c55e", textAlign: "center" }}>
                      END
                    </span>
                    <span style={{ fontSize: ".6rem", color: "var(--muted)", fontWeight: 700 }}>
                      DONE
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* detail panel */}
            {activeNodeData && <DetailPanel node={activeNodeData} />}

            {/* researcher branch note */}
            <div style={{
              marginTop: 16,
              borderRadius: 12,
              background: "rgba(59,130,246,0.06)",
              border: "1px solid rgba(59,130,246,0.2)",
              padding: "12px 16px",
              display: "flex", alignItems: "center", gap: 12,
              flexWrap: "wrap",
            }}>
              <span style={{ fontSize: "1.2rem" }}>🔭</span>
              <div>
                <p style={{ fontSize: ".8rem", fontWeight: 700, color: "#60a5fa", margin: 0 }}>
                  Research path (task_type = &quot;research&quot;)
                </p>
                <p style={{ fontSize: ".76rem", color: "var(--dim)", margin: 0 }}>
                  Supervisor → Researcher ⇄ research_tools (TavilySearch) → END
                  &nbsp;· Used when you ask for facts rather than code.
                </p>
              </div>
            </div>
          </section>

          {/* ── AGENT STATE TABLE ────────────────────────────────────── */}
          <section style={{ marginBottom: "clamp(48px,6vw,80px)" }}>
            <h2 style={{
              fontWeight: 700, fontSize: "1.1rem",
              color: "var(--text)", marginBottom: 8,
              letterSpacing: "-.02em",
            }}>
              AgentState — shared memory across all nodes
            </h2>
            <p style={{ fontSize: ".8rem", color: "var(--muted)", marginBottom: 20 }}>
              Defined as a TypedDict in graph.py — every node reads from and writes to this object.
            </p>
            <div style={{
              borderRadius: 14,
              border: "1px solid rgba(130,80,255,0.18)",
              overflow: "hidden",
              background: "var(--surface, rgba(14,14,38,0.85))",
            }}>
              {STATE_FIELDS.map((f, i) => (
                <div key={f.key} style={{
                  display: "grid",
                  gridTemplateColumns: "minmax(120px,auto) minmax(180px,auto) 1fr",
                  gap: 0,
                  borderBottom: i < STATE_FIELDS.length - 1 ? "1px solid rgba(130,80,255,0.1)" : "none",
                  padding: "12px 18px",
                  alignItems: "start",
                }}>
                  <code style={{
                    fontSize: ".78rem", fontWeight: 700,
                    color: "#c084fc",
                    fontFamily: "'Fira Code', monospace",
                    paddingRight: 16,
                  }}>
                    {f.key}
                  </code>
                  <code style={{
                    fontSize: ".7rem", color: "#60a5fa",
                    fontFamily: "'Fira Code', monospace",
                    paddingRight: 16,
                    wordBreak: "break-all",
                  }}>
                    {f.type}
                  </code>
                  <p style={{ fontSize: ".78rem", color: "var(--dim)", margin: 0, lineHeight: 1.6 }}>
                    {f.desc}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* ── TECH STACK ───────────────────────────────────────────── */}
         <section style={{ marginBottom: "clamp(32px,4vw,48px)" }}>
  <h2
    style={{
      fontWeight: 700,
      fontSize: "1.1rem",
      color: "var(--text)",
      marginBottom: 20,
      letterSpacing: "-.02em",
    }}
  >
    Tech stack
  </h2>

  <div
    style={{
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
      gap: 12,
    }}
  >
    {[
      {
        icon: <GitBranch size={22} />,
        name: "LangGraph",
        desc: "Graph orchestration",
        color: "#6366f1",
      },
      {
        icon: <Sparkles size={22} />,
        name: "Gemini 2.5 Flash",
        desc: "Code generation LLM",
        color: "#f59e0b",
      },
      {
        icon: <Search size={22} />,
        name: "TavilySearch",
        desc: "Real-time web search",
        color: "#3b82f6",
      },
      {
        icon: <Server size={22} />,
        name: "FastAPI",
        desc: "Backend API + SSE",
        color: "#10b981",
      },
      {
        icon: <Database size={22} />,
        name: "SQLite",
        desc: "Agent version history",
        color: "#a855f7",
      },
      {
        icon: <Monitor size={22} />,
        name: "Next.js 15",
        desc: "Frontend (App Router)",
        color: "#06b6d4",
      },
    ].map((t) => (
      <div
        key={t.name}
        style={{
          borderRadius: 12,
          background: "var(--surface, rgba(14,14,38,0.85))",
          border: `1px solid ${t.color}30`,
          padding: "14px",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <div
          style={{
            color: t.color,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            minWidth: 24,
          }}
        >
          {t.icon}
        </div>

        <div>
          <p
            style={{
              fontWeight: 700,
              fontSize: ".82rem",
              color: t.color,
              margin: 0,
            }}
          >
            {t.name}
          </p>

          <p
            style={{
              fontSize: ".72rem",
              color: "var(--muted)",
              margin: 0,
            }}
          >
            {t.desc}
          </p>
        </div>
      </div>
    ))}
  </div>
</section>

          {/* CTA */}
          <div style={{ textAlign: "center", paddingTop: 16 }}>
            <p style={{ fontSize: ".88rem", color: "var(--dim)", marginBottom: 18 }}>
              Ready to build your first agent?
            </p>
            <Link href="/chat">
              <span className="pill-btn" style={{ fontSize: ".9rem", padding: "12px 28px" }}>
                Start Building →
              </span>
            </Link>
          </div>

        </div>
      </main>

      <footer style={{
        position: "relative", zIndex: 1,
        textAlign: "center",
        padding: "14px clamp(16px,4vw,32px)",
        fontSize: ".74rem", color: "var(--muted)",
        borderTop: "1px solid var(--divider)",
      }}>
        © 2025 AgentBuilder · Powered by LangGraph &amp; Gemini
      </footer>

      <style>{`
        @keyframes fadeIn { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:none } }
      `}</style>
    </div>
  );
}
