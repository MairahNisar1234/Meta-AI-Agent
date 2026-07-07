"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import InlineChat from "@/components/InlineChat";
import ThemeToggle from "@/components/ThemeToggle";
import { FaGithub, FaLinkedin } from "react-icons/fa";

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
            " cricket score agent",
            " stock price tracker",
            " weather assistant",
            " news summarizer",
            " mental health chatbot",
          ].map((ex) => (
            <ExChip key={ex} label={ex} />
          ))}
        </div>

      {/* Social Links */}
<div
  className="su"
  style={{
    animationDelay: ".46s",
    display: "flex",
    gap: 14,
    marginTop: 34,
    flexWrap: "wrap",
  }}
>
  <a
    href="https://github.com/MairahNisar1234/meta-ai-agent"
    target="_blank"
    rel="noopener noreferrer"
    style={{ textDecoration: "none" }}
  >
    <button
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "10px 18px",
        borderRadius: 10,
        border: "1px solid rgba(255,255,255,0.12)",
        background: "rgba(255,255,255,0.7)",
        color: "var(--text)",
        cursor: "pointer",
        fontSize: ".9rem",
        fontWeight: 600,
        transition: "all .2s ease",
      }}
    >
      <FaGithub size={18} />
      GitHub
    </button>
  </a>

  <a
    href="https://www.linkedin.com/in/mairah-nisar/"
    target="_blank"
    rel="noopener noreferrer"
    style={{ textDecoration: "none" }}
  >
    <button
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "10px 18px",
        borderRadius: 10,
        border: "1px solid rgba(255,255,255,0.12)",
        background: "rgba(255,255,255,0.7)",
        color: "var(--text)",
        cursor: "pointer",
        fontSize: ".9rem",
        fontWeight: 600,
        transition: "all .2s ease",
      }}
    >
      <FaLinkedin size={18} />
      LinkedIn
    </button>
  </a>
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
