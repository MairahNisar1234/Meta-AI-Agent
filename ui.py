import streamlit as st
import requests

st.set_page_config(
    page_title="Agent Forge",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:ital,wght@0,300;0,400;0,500;0,600;1,400&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp { background: #f7f7f5; color: #1a1a2e; }

#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
section[data-testid="stSidebar"] { display: none; }

/* Page shell  */
.block-container {
    max-width: 1200px !important;
    padding: 0 2rem 3rem !important;
}

/* Top nav  */
.forge-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.4rem 0 1.4rem;
    border-bottom: 1px solid #e4e4dc;
    margin-bottom: 2.5rem;
}
.forge-brand {
    display: flex;
    align-items: center;
    gap: 10px;
}
.forge-icon {
    width: 32px; height: 32px;
    background: #1a1a2e;
    border-radius: 7px;
    display: flex; align-items: center; justify-content: center;
    font-size: 15px; line-height: 1;
}
.forge-name {
    font-size: 1rem;
    font-weight: 600;
    color: #1a1a2e;
    letter-spacing: -0.02em;
}
.forge-badge {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    color: #8888a0;
    background: #ededea;
    border-radius: 4px;
    padding: 2px 7px;
}

/* Section labels */
.eyebrow {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem;
    font-weight: 500;
    color: #8888a0;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.35rem;
}
.section-heading {
    font-size: 1.05rem;
    font-weight: 600;
    color: #1a1a2e;
    letter-spacing: -0.02em;
    margin-bottom: 1rem;
}
/* Fix cursor visibility in textarea */
.stTextArea textarea {
    caret-color: #1a1a2e !important;   /* makes cursor visible */
}

/* Optional: stronger focus indicator */
.stTextArea textarea:focus {
    outline: none !important;
    border-color: #1a1a2e !important;
    box-shadow: 0 0 0 3px rgba(26,26,46,0.12) !important;
}

/* Optional: ensure blinking cursor contrast */
textarea {
    color: #1a1a2e !important;
}
/* Textarea */
.stTextArea textarea {
    background: #ffffff !important;
    border: 1.5px solid #e4e4dc !important;
    border-radius: 10px !important;
    color: #1a1a2e !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9rem !important;
    padding: 12px 14px !important;
    line-height: 1.6 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
}
.stTextArea textarea:focus {
    border-color: #1a1a2e !important;
    box-shadow: 0 0 0 3px rgba(26,26,46,0.08) !important;
    outline: none !important;
}
.stTextArea label { display: none !important; }
.stTextArea textarea::placeholder { color: #b0b0c0 !important; }

/* Primary button */
.stButton > button[kind="primary"] {
    background: #1a1a2e !important;
    border: none !important;
    color: #ffffff !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    border-radius: 8px !important;
    padding: 0.6rem 1.5rem !important;
    letter-spacing: -0.01em !important;
    transition: opacity 0.15s, transform 0.12s !important;
    box-shadow: 0 1px 3px rgba(26,26,46,0.2) !important;
}
.stButton > button[kind="primary"]:hover {
    opacity: 0.85 !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="primary"]:active {
    transform: translateY(0) !important;
}

/* Secondary button*/
.stButton > button:not([kind="primary"]) {
    background: #ffffff !important;
    border: 1.5px solid #e4e4dc !important;
    color: #8888a0 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.875rem !important;
    border-radius: 8px !important;
    transition: all 0.15s !important;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: #1a1a2e !important;
    color: #1a1a2e !important;
}

/* Divider */
.col-divider {
    width: 1px;
    background: #e4e4dc;
    align-self: stretch;
    margin: 0 0.5rem;
}

/* Output card */
.output-card {
    background: #ffffff;
    border: 1.5px solid #e4e4dc;
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(26,26,46,0.06);
}
.output-card-header {
    padding: 1rem 1.2rem;
    border-bottom: 1px solid #f0f0ec;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.output-card-title {
    font-size: 0.82rem;
    font-weight: 600;
    color: #1a1a2e;
}
.status-ready {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    color: #16a34a;
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 20px;
    padding: 3px 9px;
}
.status-working {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.7rem;
    color: #8888a0;
    background: #f7f7f5;
    border: 1px solid #e4e4dc;
    border-radius: 20px;
    padding: 3px 9px;
}
.pulse-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: #8888a0;
    animation: blink 1.4s infinite;
}
.green-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: #16a34a;
    border-radius: 50%;
}
@keyframes blink {
    0%,100% { opacity:1; } 50% { opacity:0.25; }
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid #e4e4dc !important;
    gap: 0 !important;
    padding: 0 1.2rem !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #a0a0b8 !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
    padding: 0.7rem 1rem !important;
    border-bottom: 2px solid transparent !important;
    margin-bottom: -1px !important;
}
.stTabs [aria-selected="true"] {
    color: #1a1a2e !important;
    border-bottom: 2px solid #1a1a2e !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab-panel"] {
    padding: 1.2rem 1.2rem !important;
}

/* Radio  */
div[data-testid="stRadio"] > label { display: none !important; }
.stRadio [data-baseweb="radio-group"] {
    gap: 5px !important;
    flex-wrap: wrap !important;
}
.stRadio label {
    background: #f7f7f5 !important;
    border: 1.5px solid #e4e4dc !important;
    border-radius: 6px !important;
    padding: 3px 11px !important;
    font-size: 0.75rem !important;
    font-family: 'IBM Plex Mono', monospace !important;
    color: #8888a0 !important;
    cursor: pointer !important;
    transition: all 0.12s !important;
}
.stRadio label:has(input:checked) {
    background: #1a1a2e !important;
    border-color: #1a1a2e !important;
    color: #ffffff !important;
}

/* Code */
.stCode, [data-testid="stCode"] {
    border-radius: 8px !important;
    border: 1px solid #e4e4dc !important;
    background: #fafaf8 !important;
}
.stCode code {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.8rem !important;
}

/*Download buttons*/
.stDownloadButton > button {
    background: #fafaf8 !important;
    border: 1.5px solid #e4e4dc !important;
    color: #8888a0 !important;
    font-size: 0.75rem !important;
    font-family: 'IBM Plex Mono', monospace !important;
    border-radius: 6px !important;
    padding: 4px 10px !important;
    transition: all 0.12s !important;
}
.stDownloadButton > button:hover {
    border-color: #1a1a2e !important;
    color: #1a1a2e !important;
    background: #ffffff !important;
}

/*  Example chips */
.chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 0.8rem;
}
.chip {
    font-size: 0.75rem;
    color: #4b4b66 !important;
    background: #ffffff;
    border: 1px solid #e4e4dc;
    border-radius: 20px;
    padding: 3px 10px;
    white-space: nowrap;
}

/* Empty state  */
.empty-wrap {
    padding: 3.5rem 1rem;
    text-align: center;
}
.empty-icon { font-size: 2rem; margin-bottom: 0.8rem; opacity: 0.25; }
.empty-msg { font-size: 0.85rem; color: #c0c0d0; }

/* Alert overrides */
.stAlert > div {
    border-radius: 8px !important;
    font-size: 0.85rem !important;
}

/* ── Preview browser chrome ── */
.browser-bar {
    background: #f7f7f5;
    border-bottom: 1px solid #e4e4dc;
    padding: 8px 14px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.bdot { width:10px;height:10px;border-radius:50%; }
.browser-url {
    margin-left: 10px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    color: #b0b0c0;
    background: #ffffff;
    border: 1px solid #e4e4dc;
    border-radius: 4px;
    padding: 2px 10px;
    flex: 1;
}
</style>
""", unsafe_allow_html=True)

# ── Nav ──────────────────────────────────────────────────────────
st.markdown("""
<div class="forge-nav">
  <div class="forge-brand">
    <div class="forge-icon">⚡</div>
    <span class="forge-name">Agent Forge</span>
    <span class="forge-badge">meta-agent</span>
  </div>
  <span style="font-family:'IBM Plex Mono',monospace;font-size:0.7rem;color:#c0c0d0;">
    LangGraph · FastAPI · LangChain
  </span>
</div>
""", unsafe_allow_html=True)

# Two-column layout
left, gap_col, right = st.columns([5, 0.15, 7], gap="small")

# LEFT: Input panel 
with left:
    st.markdown('<div class="eyebrow">// Build</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-heading">Describe your agent</div>', unsafe_allow_html=True)

    query = st.text_area(
        "query",
        height=150,
        placeholder="e.g. A travel planner that searches for flights, books hotels, and builds a day-by-day itinerary…",
        label_visibility="collapsed",
    )

    c1, c2 = st.columns([3, 1])
    with c1:
        generate = st.button("⚡ Forge Agent", type="primary", use_container_width=True)
    with c2:
        clear = st.button("Clear", use_container_width=True)
        if clear:
            st.session_state.pop("agent_result", None)
            st.session_state.pop("loaded_agent_name", None)
            st.rerun()

    st.markdown("""
    <div style="margin-top:1.4rem;">
      <div class="eyebrow" style="margin-bottom:0.5rem;">// examples</div>
      <div class="chip-row">
        <span class="chip">Stock price tracker</span>
        <span class="chip">HR policy Q&A</span>
        <span class="chip">Inventory manager</span>
        <span class="chip">Web researcher</span>
        <span class="chip">Travel planner</span>
        <span class="chip">Order tracker</span>
      </div>
    </div>

    <div style="margin-top:1.8rem; padding:1rem 1.1rem;
         background:#ffffff; border:1.5px solid #e4e4dc; border-radius:10px;">
      <div class="eyebrow" style="margin-bottom:0.6rem;">// what gets made</div>
      <div style="display:flex;flex-direction:column;gap:6px;">
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
                color:#1a1a2e;background:#f0f0f8;border:1px solid #e4e4dc;
                border-radius:4px;padding:1px 7px;">agent.py</span>
          <span style="font-size:0.8rem;color:#8888a0;">LangGraph + FastAPI backend</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
                color:#1a1a2e;background:#f0f0f8;border:1px solid #e4e4dc;
                border-radius:4px;padding:1px 7px;">.env</span>
          <span style="font-size:0.8rem;color:#8888a0;">API keys template</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
                color:#1a1a2e;background:#f0f0f8;border:1px solid #e4e4dc;
                border-radius:4px;padding:1px 7px;">ui.html</span>
          <span style="font-size:0.8rem;color:#8888a0;">Self-contained web interface</span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

with gap_col:
    st.markdown('<div class="col-divider" style="margin-top:0;height:100%;min-height:400px;"></div>', unsafe_allow_html=True)

# ── RIGHT: Output panel ──────────────────────────────────────────
with right:
    st.markdown('<div class="eyebrow">// Output</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-heading">Generated Agent</div>', unsafe_allow_html=True)

    status_slot = st.empty()
    output_slot = st.empty()

    if "agent_result" not in st.session_state and not (generate and query):
        output_slot.markdown("""
        <div style="background:#ffffff;border:1.5px solid #e4e4dc;border-radius:14px;
             box-shadow:0 2px 12px rgba(26,26,46,0.05);">
          <div class="empty-wrap">
            <div class="empty-icon">🤖</div>
            <div class="empty-msg">Your agent code and preview will appear here</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

# ── Trigger generation ───────────────────────────────────────────
if generate and query:
    with right:
        status_slot.markdown("""
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:1rem;">
          <div class="status-working">
            <div class="pulse-dot"></div>
            forging — 1–3 min
          </div>
          <span style="font-size:0.78rem;color:#b0b0c0;">
            Building agent.py · .env · ui.html
          </span>
        </div>
        """, unsafe_allow_html=True)
        output_slot.empty()

    try:
        response = requests.post(
            "http://localhost:8000/chat",
            json={"query": query},
            timeout=600,
        )

        if response.status_code == 200:
            data = response.json()

            # The /chat endpoint returns the last AIMessage text — not file contents.
            # The actual files are saved to disk by code_tools. Find the most recently
            # modified agent folder and read the files straight from disk.
            import os, pathlib

            agents_dir = pathlib.Path("generated_agents")
            agent_py = env_file = ui_html = ""

            if agents_dir.exists():
                # Pick the folder most recently touched
                folders = [f for f in agents_dir.iterdir() if f.is_dir()]
                if folders:
                    latest = max(folders, key=lambda f: f.stat().st_mtime)
                    def read_file(p):
                        try:
                            return p.read_text(encoding="utf-8")
                        except Exception:
                            return ""
                    agent_py = read_file(latest / "agent.py")
                    env_file = read_file(latest / ".env")
                    ui_html  = read_file(latest / "ui.html")

            st.session_state["agent_result"] = {
                "agent_py": agent_py,
                "env":      env_file,
                "ui_html":  ui_html,
            }
            st.session_state.pop("loaded_agent_name", None)  # clear library selection
            st.rerun()

        else:
            with right:
                status_slot.empty()
                st.error(f"API error {response.status_code}: {response.text}")

    except requests.exceptions.Timeout:
        with right:
            status_slot.empty()
            st.error("Timed out — check FastAPI terminal. Generation may still be running.")
    except requests.exceptions.ConnectionError:
        with right:
            status_slot.empty()
            st.error("Cannot connect to `localhost:8000` — is FastAPI running?")
    except Exception as e:
        with right:
            status_slot.empty()
            st.error(str(e))

# ── Render results ───────────────────────────────────────────────
if "agent_result" in st.session_state:
    res = st.session_state["agent_result"]
    agent_py = res.get("agent_py", "")
    env_file = res.get("env", "")
    ui_html  = res.get("ui_html", "")

    with right:
        status_slot.markdown("""
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:1rem;">
          <div class="status-ready">
            <div class="green-dot"></div>
            ready
          </div>
          <span style="font-size:0.78rem;color:#b0b0c0;">3 files generated</span>
        </div>
        """, unsafe_allow_html=True)

        output_slot.empty()

        with st.container():
            st.markdown('<div class="output-card">', unsafe_allow_html=True)

            tab_code, tab_preview = st.tabs(["  </> Code  ", "  ◻ Preview  "])

            with tab_code:
                file_tab = st.radio(
                    "file",
                    ["agent.py", ".env", "ui.html"],
                    horizontal=True,
                    label_visibility="collapsed",
                )

                code_map = {
                    "agent.py": (agent_py or "# agent.py not returned", "python"),
                    ".env":     (env_file or "# .env not returned",     "bash"),
                    "ui.html":  (ui_html  or "<!-- ui.html not returned -->", "html"),
                }
                content, lang = code_map[file_tab]
                st.code(content, language=lang)

                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                d1, d2, d3, _ = st.columns([1.3, 1, 1.3, 4])
                with d1:
                    st.download_button("↓ agent.py", agent_py or "", file_name="agent.py", mime="text/plain")
                with d2:
                    st.download_button("↓ .env", env_file or "", file_name=".env", mime="text/plain")
                with d3:
                    st.download_button("↓ ui.html", ui_html or "", file_name="ui.html", mime="text/html")

            with tab_preview:
                if ui_html:
                    st.markdown("""
                    <div class="browser-bar">
                      <div class="bdot" style="background:#ff5f57"></div>
                      <div class="bdot" style="background:#febc2e"></div>
                      <div class="bdot" style="background:#28c840"></div>
                      <div class="browser-url">localhost:8000</div>
                    </div>
                    """, unsafe_allow_html=True)
                    import streamlit.components.v1 as components
                    components.html(ui_html, height=560, scrolling=True)
                else:
                    st.markdown("""
                    <div class="empty-wrap">
                      <div class="empty-icon" style="font-size:1.6rem">📄</div>
                      <div class="empty-msg">No ui.html was returned</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

# ── Agent Library 
st.markdown("<hr style='border:none;border-top:1px solid #e4e4dc;margin:2.5rem 0 1.8rem'>",
            unsafe_allow_html=True)
st.markdown('<div class="eyebrow">// Library</div>', unsafe_allow_html=True)
st.markdown('<div class="section-heading">Saved Agents</div>', unsafe_allow_html=True)

import pathlib
from app.agents.persistence import init_db, list_agents, get_agent, get_active_code_path

init_db()
all_agents = list_agents()

if not all_agents:
    st.markdown("""
    <div style="padding:2rem 1rem;text-align:center;background:#fafaf8;
         border:1.5px dashed #e4e4dc;border-radius:12px;">
      <div style="font-size:1.5rem;opacity:0.2;margin-bottom:0.5rem">🗄️</div>
      <div style="font-size:0.82rem;color:#c0c0d0;">No agents in the database yet — forge one above</div>
    </div>
    """, unsafe_allow_html=True)
else:
    # Category colour map
    CAT_COLOUR = {
        "cricket":        "#22c55e",
        "stocks":         "#3b82f6",
        "weather":        "#f59e0b",
        "news":           "#8b5cf6",
        "sports_general": "#06b6d4",
        "currency":       "#f97316",
        "none":           "#8888a0",
    }

    # Render cards in rows of 3
    cols_per_row = 3
    rows = [all_agents[i:i+cols_per_row] for i in range(0, len(all_agents), cols_per_row)]

    for row in rows:
        cols = st.columns(cols_per_row)
        for col, agent in zip(cols, row):
            cat   = agent.get("category", "none") or "none"
            color = CAT_COLOUR.get(cat, "#8888a0")
            meta  = agent.get("metadata", {})
            api   = meta.get("realtime_api", "")
            tools = meta.get("tools_needed", [])
            ver   = agent.get("current_version", 1)
            created = (agent.get("created_at") or "")[:10]

            with col:
                # Card header
                st.markdown(f"""
                <div style="background:#ffffff;border:1.5px solid #e4e4dc;border-radius:12px;
                     padding:1rem 1.1rem;box-shadow:0 1px 6px rgba(26,26,46,0.05);
                     margin-bottom:0.4rem;">
                  <div style="display:flex;align-items:center;justify-content:space-between;
                       margin-bottom:0.6rem;">
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
                          font-weight:600;color:#1a1a2e;">{agent['canonical_name']}</span>
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;
                          color:#ffffff;background:{color};border-radius:20px;
                          padding:2px 8px;">{cat}</span>
                  </div>
                  <div style="font-size:0.75rem;color:#8888a0;margin-bottom:0.5rem;
                       white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
                       title="{agent.get('original_prompt','')[:120]}">
                    {agent.get('original_prompt','—')[:60]}{'…' if len(agent.get('original_prompt',''))>60 else ''}
                  </div>
                  <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:0.6rem;">
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:0.62rem;
                          color:#8888a0;background:#f0f0f8;border:1px solid #e4e4dc;
                          border-radius:4px;padding:1px 6px;">v{ver}</span>
                    <span style="font-family:'IBM Plex Mono',monospace;font-size:0.62rem;
                          color:#8888a0;background:#f0f0f8;border:1px solid #e4e4dc;
                          border-radius:4px;padding:1px 6px;">{created}</span>
                    {f'<span style="font-family:IBM Plex Mono,monospace;font-size:0.62rem;color:{color};background:#f0f0f8;border:1px solid #e4e4dc;border-radius:4px;padding:1px 6px;">⚡ {api[:20]}</span>' if api else ''}
                  </div>
                </div>
                """, unsafe_allow_html=True)

                # Load button — fills the output panel with this agent's code
                if st.button("Load →", key=f"load_{agent['id']}", use_container_width=True):
                    code_path = get_active_code_path(agent["id"])
                    if code_path and pathlib.Path(code_path).exists():
                        def _read(p):
                            try: return pathlib.Path(p).read_text(encoding="utf-8")
                            except: return ""
                        st.session_state["agent_result"] = {
                            "agent_py": _read(pathlib.Path(code_path) / "agent.py"),
                            "env":      _read(pathlib.Path(code_path) / ".env"),
                            "ui_html":  _read(pathlib.Path(code_path) / "ui.html"),
                        }
                        st.session_state["loaded_agent_name"] = agent["canonical_name"]
                        st.rerun()
                    else:
                        # Fall back to generated_agents/ on disk if registry copy missing
                        fallback = pathlib.Path("generated_agents") / agent["canonical_name"]
                        if fallback.exists():
                            def _read(p):
                                try: return pathlib.Path(p).read_text(encoding="utf-8")
                                except: return ""
                            st.session_state["agent_result"] = {
                                "agent_py": _read(fallback / "agent.py"),
                                "env":      _read(fallback / ".env"),
                                "ui_html":  _read(fallback / "ui.html"),
                            }
                            st.session_state["loaded_agent_name"] = agent["canonical_name"]
                            st.rerun()
                        else:
                            st.warning("Code path not found on disk")

    # Show which agent is currently loaded in the output panel
    if "loaded_agent_name" in st.session_state:
        st.markdown(f"""
        <div style="margin-top:1rem;padding:0.6rem 1rem;background:#f0fdf4;
             border:1px solid #bbf7d0;border-radius:8px;font-size:0.8rem;color:#16a34a;">
          ✓ Viewing saved agent: <strong>{st.session_state['loaded_agent_name']}</strong>
          — loaded from database
        </div>
        """, unsafe_allow_html=True)