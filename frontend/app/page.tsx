"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import InlineChat from "@/components/InlineChat";
import ThemeToggle from "@/components/ThemeToggle";

/* ── star field (client-only to avoid hydration mismatch) ─────────────── */
interface Star { x: number; y: number; s: number; op: number; d: number; dl: number; }

function StarField() {
  const [stars, setStars] = useState<Star[]>([]);
  useEffect(() => {
    setStars(
      Array.from({ length: 50 }, () => ({
        x:  Math.random() * 100,
        y:  Math.random() * 100,
        s:  Math.random() * 1.4 + 0.4,
        op: Math.random() * 0.35 + 0.08,
        d:  Math.random() * 5 + 4,
        dl: Math.random() * 5,
      }))
    );
  }, []);
  return (
    <div className="fixed inset-0 pointer-events-none" style={{ zIndex: 0 }} aria-hidden>
      {stars.map((s, i) => (
        <span
          key={i}
          className="absolute rounded-full bg-white"
          style={{
            left: `${s.x}%`,
            top:  `${s.y}%`,
            width:  s.s,
            height: s.s,
            "--op": s.op,
            opacity: s.op,
            animation: `twinkle ${s.d}s ${s.dl}s ease-in-out infinite`,
          } as React.CSSProperties}
        />
      ))}
    </div>
  );
}

/* ── page ─────────────────────────────────────────────────────────────── */
export default function HomePage() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  return (
    /* root: normal document flow — no overflow hidden, scrolls naturally */
    <div style={{ minHeight: "100dvh", display: "flex", flexDirection: "column" }}>

      {/* ── decorative bg (z-0, fixed, pointer-events none) ─────────── */}
      <div className="blob-1" aria-hidden />
      <div className="blob-2" aria-hidden />
      <div className="grid-bg" aria-hidden />
      <StarField />

      {/* ── NAVBAR ──────────────────────────────────────────────────── */}
      <header
        style={{
          position: "sticky",
          top: 0,
          zIndex: 50,
          transition: "background .3s, border-color .3s",
          /* Always have a background so content never shows through */
          background: scrolled ? "var(--nav-bg)" : "var(--nav-bg)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          borderBottom: "1px solid var(--nav-border)",
        }}
      >
        <div
          style={{
            maxWidth: 1080,
            width: "100%",
            margin: "0 auto",
            padding: "0 clamp(16px, 4vw, 32px)",
            height: 58,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          {/* logo */}
          <span style={{
            fontWeight: 700,
            fontSize: "1rem",
            letterSpacing: "-.02em",
            color: "var(--text)",
            whiteSpace: "nowrap",
            flexShrink: 0,
          }}>
            AgentBuilder
          </span>

          {/* centre nav — hidden on small screens */}
          <nav
            style={{
              display: "flex",
              alignItems: "center",
              gap: 2,
              flex: 1,
              justifyContent: "center",
            }}
            className="hidden sm:flex"
          >
            <Link href="/how-it-works" style={{ textDecoration: "none" }}>
              <span className="nav-link">How it works</span>
            </Link>
            <Link href="/examples" style={{ textDecoration: "none" }}>
              <span className="nav-link">Examples</span>
            </Link>
           
          </nav>

          {/* right side */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
            <ThemeToggle />
            
          </div>
        </div>
      </header>

      {/* ── HERO ────────────────────────────────────────────────────── */}
      <main
        style={{
          position: "relative",
          zIndex: 1,
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          width: "100%",
          padding: "clamp(40px,6vw,72px) clamp(16px,4vw,32px) clamp(40px,6vw,72px)",
        }}
      >
        {/* live badge */}
        <div
          className="su"
          style={{
            animationDelay: ".05s",
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "5px 16px",
            borderRadius: 999,
            fontSize: ".76rem",
            fontWeight: 500,
            color: "var(--dim)",
            background: "rgba(130,80,255,.1)",
            border: "1px solid rgba(130,80,255,.28)",
            marginBottom: 28,
          }}
        >
          <span className="dot-live" />
          LangGraph + OpenRouter — live
        </div>

        {/* headline */}
        <h1
          className="su"
          style={{
            animationDelay: ".1s",
            textAlign: "center",
            fontWeight: 700,
            fontSize: "clamp(2rem, 5.5vw, 3.8rem)",
            lineHeight: 1.14,
            letterSpacing: "-.034em",
            color: "var(--text)",
            marginBottom: 18,
            maxWidth: 680,
          }}
        >
          Build AI&nbsp;agents<br />
          <span className="g-text">from a single prompt</span>
        </h1>

        {/* sub-headline */}
        <p
          className="su"
          style={{
            animationDelay: ".18s",
            textAlign: "center",
            fontSize: "clamp(.9rem, 2vw, 1rem)",
            lineHeight: 1.72,
            color: "var(--dim)",
            maxWidth: 500,
            marginBottom: 36,
          }}
        >
          Describe any agent in plain English and get a full{" "}
          <code style={{ color: "var(--accent2)", fontSize: ".88em" }}>agent.py</code>,{" "}
          <code style={{ color: "#60a5fa", fontSize: ".88em" }}>.env</code> and{" "}
          <code style={{ color: "#34d399", fontSize: ".88em" }}>ui.html</code> in seconds.
        </p>

        {/* ── INLINE CHAT — centered, full width capped ───────────── */}
        <div
          className="su"
          style={{
            animationDelay: ".26s",
            width: "100%",
            maxWidth: 680,
          }}
        >
          <InlineChat />
        </div>

        {/* example chips */}
        <div
          className="su"
          style={{
            animationDelay: ".38s",
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            alignItems: "center",
            gap: 8,
            marginTop: 22,
          }}
        >
          <span style={{ fontSize: ".74rem", color: "var(--muted)" }}>Try:</span>
          {[
            "🏏 cricket score agent",
            "📈 stock price tracker",
            "🌤 weather assistant",
            "📰 news summarizer",
            "💬 mental health chatbot",
          ].map((ex) => (
            <ExChip key={ex} label={ex} />
          ))}
        </div>

        {/* social icons */}
        <div
          className="su"
          style={{
            animationDelay: ".46s",
            display: "flex",
            gap: 10,
            marginTop: 34,
          }}
        >
          {[
            <svg key="x" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.74l7.73-8.835L1.254 2.25H8.08l4.253 5.622zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
            </svg>,
            <svg key="tg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.248-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L6.166 13.9l-2.97-.924c-.645-.204-.657-.645.136-.953l11.57-4.461c.537-.194 1.006.131.66.686z"/>
            </svg>,
            <svg key="dc" width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128c.126-.094.252-.192.372-.292a.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.1.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
            </svg>,
          ].map((icon, i) => (
            <IconBtn key={i}>{icon}</IconBtn>
          ))}
        </div>
      </main>

      {/* ── FOOTER ──────────────────────────────────────────────────── */}
      <footer
        style={{
          position: "relative",
          zIndex: 1,
          textAlign: "center",
          padding: "14px clamp(16px,4vw,32px)",
          fontSize: ".74rem",
          color: "var(--muted)",
          borderTop: "1px solid var(--divider)",
        }}
      >
        © 2026 AgentBuilder · Powered by LangGraph &amp; OpenRouter
      </footer>
    </div>
  );
}

/* ── small sub-components ───────────────────────────────────────────────── */
function ExChip({ label }: { label: string }) {
  return (
    <button
      onClick={() =>
        window.dispatchEvent(
          new CustomEvent("agent-example", { detail: label.replace(/^\S+\s/, "") })
        )
      }
      style={{
        padding: "5px 13px",
        borderRadius: 999,
        fontSize: ".74rem",
        fontWeight: 500,
        color: "var(--dim)",
        background: "rgba(130,80,255,.09)",
        border: "1px solid rgba(130,80,255,.22)",
        cursor: "pointer",
        transition: "background .2s, border-color .2s, transform .18s, color .2s",
        fontFamily: "inherit",
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLElement;
        el.style.background = "rgba(130,80,255,.18)";
        el.style.borderColor = "rgba(150,90,255,.5)";
        el.style.transform = "translateY(-1px)";
        el.style.color = "var(--text)";
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLElement;
        el.style.background = "rgba(130,80,255,.09)";
        el.style.borderColor = "rgba(130,80,255,.22)";
        el.style.transform = "translateY(0)";
        el.style.color = "var(--dim)";
      }}
    >
      {label}
    </button>
  );
}

function IconBtn({ children }: { children: React.ReactNode }) {
  return (
    <button
      style={{
        width: 34, height: 34,
        borderRadius: "50%",
        display: "flex", alignItems: "center", justifyContent: "center",
        background: "var(--icon-bg)",
        border: "1px solid var(--icon-border)",
        color: "var(--dim)",
        cursor: "pointer",
        transition: "transform .18s, background .2s, color .2s",
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLElement;
        el.style.transform = "scale(1.1)";
        el.style.background = "var(--icon-hover)";
        el.style.color = "var(--text)";
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLElement;
        el.style.transform = "scale(1)";
        el.style.background = "var(--icon-bg)";
        el.style.color = "var(--dim)";
      }}
    >
      {children}
    </button>
  );
}
