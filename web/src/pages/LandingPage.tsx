import { useState, useEffect, useRef } from "react";

// ── Design tokens ──────────────────────────────────────────────
const V = {
  bg: "#000000",
  surface: "#0a0907",
  surfaceHi: "#0f0d0a",
  surfaceLo: "#060503",
  border: "rgba(255,255,255,0.06)",
  borderHi: "rgba(255,255,255,0.14)",
  hairline: "rgba(255,255,255,0.04)",
  ink: "#f6f3ee",
  inkDim: "#8c8680",
  inkFaint: "#3a3733",
  amber: "#f59e0b",
  amberSoft: "rgba(245,158,11,0.14)",
  amberGlow: "rgba(245,158,11,0.45)",
  amberMist: "rgba(245,158,11,0.06)",
  obs: "oklch(0.82 0.07 215)",
  obsSoft: "color-mix(in oklch, oklch(0.82 0.07 215) 14%, transparent)",
  obsMist: "color-mix(in oklch, oklch(0.82 0.07 215) 5%, transparent)",
  good: "#7fcaa0",
  serif: '"Instrument Serif", "GT Sectra", Georgia, serif',
  sans: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
  mono: '"JetBrains Mono", "SF Mono", Menlo, ui-monospace, monospace',
};

// ── Atoms ──────────────────────────────────────────────────────

function Dot({ color = V.amber, size = 6, pulse = true }: {
  color?: string; size?: number; pulse?: boolean;
}) {
  return (
    <span style={{
      width: size, height: size, borderRadius: "50%",
      background: color, display: "inline-block",
      boxShadow: `0 0 ${size * 2}px ${color}`,
      animation: pulse ? "velloDot 2.4s ease-in-out infinite" : "none",
      flexShrink: 0,
    }} />
  );
}

function Eyebrow({ children, color, style }: {
  children: React.ReactNode; color?: string; style?: React.CSSProperties;
}) {
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: 10,
      fontFamily: V.mono, fontSize: 11, letterSpacing: "0.18em",
      color: V.inkDim, textTransform: "uppercase",
      ...style,
    }}>
      <Dot color={color || V.amber} />
      <span>{children}</span>
    </div>
  );
}

function Bloom({ color = V.amberGlow, size = 600, x = "50%", y = "50%", opacity = 0.5, blur = 100, animate = true }: {
  color?: string; size?: number; x?: string; y?: string;
  opacity?: number; blur?: number; animate?: boolean;
}) {
  return (
    <div style={{
      position: "absolute", left: x, top: y,
      width: size, height: size,
      borderRadius: "50%",
      background: `radial-gradient(circle, ${color} 0%, transparent 60%)`,
      filter: `blur(${blur}px)`,
      opacity,
      transform: "translate(-50%, -50%)",
      pointerEvents: "none",
      animation: animate ? "velloBloom 8s ease-in-out infinite" : "none",
      mixBlendMode: "screen",
    }} />
  );
}

function Mono({ children, color, size = 11, style }: {
  children: React.ReactNode; color?: string; size?: number; style?: React.CSSProperties;
}) {
  return (
    <span style={{
      fontFamily: V.mono, fontSize: size, color: color || V.inkDim,
      letterSpacing: "0.04em", ...style,
    }}>{children}</span>
  );
}

function PrimaryBtn({ children, onClick, small, glow = true, style, as: Tag = "button", href }: {
  children: React.ReactNode; onClick?: () => void; small?: boolean;
  glow?: boolean; style?: React.CSSProperties; as?: "button" | "a"; href?: string;
}) {
  const [hover, setHover] = useState(false);
  return (
    <Tag
      href={href}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "inline-flex", alignItems: "center", gap: 10,
        padding: small ? "8px 16px" : "12px 22px",
        fontSize: small ? 12 : 13,
        fontFamily: V.sans, fontWeight: 600,
        color: "#100c06",
        background: V.ink,
        border: "none", borderRadius: 999,
        cursor: "pointer", textDecoration: "none",
        transition: "transform .2s ease, box-shadow .25s ease",
        transform: hover ? "translateY(-1px)" : "translateY(0)",
        boxShadow: glow
          ? (hover
            ? "0 8px 40px rgba(245,158,11,0.25), 0 0 0 1px rgba(255,255,255,0.2), inset 0 1px 0 rgba(255,255,255,0.4)"
            : "0 4px 20px rgba(245,158,11,0.12), 0 0 0 1px rgba(255,255,255,0.08), inset 0 1px 0 rgba(255,255,255,0.3)")
          : (hover
            ? "0 6px 24px rgba(255,255,255,0.18)"
            : "0 1px 0 rgba(255,255,255,0.1)"),
        ...style,
      } as React.CSSProperties}>
      {children}
    </Tag>
  );
}

function GhostBtn({ children, onClick, small, style }: {
  children: React.ReactNode; onClick?: () => void; small?: boolean; style?: React.CSSProperties;
}) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "inline-flex", alignItems: "center", gap: 8,
        padding: small ? "8px 16px" : "11px 22px",
        fontSize: small ? 12 : 13,
        fontFamily: V.sans, fontWeight: 500,
        color: V.ink, background: "transparent",
        border: `1px solid ${hover ? V.borderHi : V.border}`,
        borderRadius: 999,
        cursor: "pointer", textDecoration: "none",
        transition: "border-color .2s ease, background .2s ease",
        backgroundColor: hover ? "rgba(255,255,255,0.03)" : "transparent",
        ...style,
      }}>
      {children}
    </button>
  );
}

function VelloMark({ size = 22, glow = false }: { size?: number; glow?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{
      filter: glow ? "drop-shadow(0 0 8px rgba(245,158,11,0.5))" : "none",
    }}>
      <g stroke={V.ink} strokeWidth="1.2" fill="none" strokeLinecap="round">
        <circle cx="12" cy="12" r="3.2" />
        {[0, 60, 120, 180, 240, 300].map(a => {
          const rad = (a * Math.PI) / 180;
          const x1 = 12 + Math.cos(rad) * 5.2;
          const y1 = 12 + Math.sin(rad) * 5.2;
          const x2 = 12 + Math.cos(rad) * 9.8;
          const y2 = 12 + Math.sin(rad) * 9.8;
          return <line key={a} x1={x1} y1={y1} x2={x2} y2={y2} />;
        })}
      </g>
      <circle cx="12" cy="12" r="1" fill={V.amber} />
    </svg>
  );
}

function Wordmark({ size = 13 }: { size?: number }) {
  return (
    <span style={{
      fontFamily: V.sans, fontWeight: 800,
      fontSize: size, letterSpacing: "0.34em",
      color: V.ink,
    }}>VELLO</span>
  );
}

function LiveTime({ style }: { style?: React.CSSProperties }) {
  const [t, setT] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setT(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const hh = String(t.getHours()).padStart(2, "0");
  const mm = String(t.getMinutes()).padStart(2, "0");
  const ss = String(t.getSeconds()).padStart(2, "0");
  return (
    <Mono style={style}>
      {hh}:{mm}<span style={{ opacity: 0.45 }}>:{ss}</span>
    </Mono>
  );
}

function Caret({ show = true }: { show?: boolean }) {
  return (
    <span style={{
      display: "inline-block", width: 8, height: "1em",
      background: V.amber, marginLeft: 2, verticalAlign: "-2px",
      opacity: show ? 1 : 0,
      animation: "velloFlicker 1.1s steps(1) infinite",
      boxShadow: "0 0 12px rgba(245,158,11,0.6)",
    }} />
  );
}

function Typewriter({ text, speed = 28, start = 0, style, onDone }: {
  text: string; speed?: number; start?: number;
  style?: React.CSSProperties; onDone?: () => void;
}) {
  const [i, setI] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;
    setI(0);
    const startTimer = setTimeout(() => {
      if (cancelled) return;
      intervalRef.current = setInterval(() => {
        setI(prev => {
          if (prev >= text.length) {
            if (intervalRef.current) clearInterval(intervalRef.current);
            onDone?.();
            return prev;
          }
          return prev + 1;
        });
      }, speed);
    }, start);
    return () => {
      cancelled = true;
      clearTimeout(startTimer);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [text, speed, start]);

  return <span style={style}>{text.slice(0, i)}<Caret show={i < text.length} /></span>;
}

function Hairline({ label, style }: { label?: string; style?: React.CSSProperties }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, ...style }}>
      <span style={{ flex: 1, height: 1, background: V.hairline }} />
      {label && (
        <span style={{
          fontFamily: V.mono, fontSize: 10, letterSpacing: "0.2em",
          color: V.inkFaint, textTransform: "uppercase",
        }}>{label}</span>
      )}
      {label && <span style={{ flex: 1, height: 1, background: V.hairline }} />}
    </div>
  );
}

// ── Section shell ──────────────────────────────────────────────

function Section({ id, eyebrow, title, kicker, children, contained = true }: {
  id?: string; eyebrow?: string; title?: string; kicker?: string;
  children: React.ReactNode; contained?: boolean;
}) {
  return (
    <section id={id} style={{
      position: "relative",
      padding: "140px 40px",
      borderTop: `1px solid ${V.hairline}`,
    }}>
      <div style={{ maxWidth: contained ? 1200 : "100%", margin: "0 auto", position: "relative" }}>
        {(eyebrow || title) && (
          <div style={{ marginBottom: 64, maxWidth: 720 }}>
            {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
            {title && (
              <h2 style={{
                margin: "20px 0 16px",
                fontFamily: V.serif, fontWeight: 400,
                fontSize: "clamp(40px, 5vw, 64px)",
                lineHeight: 1.02, letterSpacing: "-0.02em",
                color: V.ink,
              }}>{title}</h2>
            )}
            {kicker && (
              <p style={{
                margin: 0, fontSize: 18, lineHeight: 1.55,
                color: V.inkDim, fontFamily: V.sans, maxWidth: 580,
              }}>{kicker}</p>
            )}
          </div>
        )}
        {children}
      </div>
    </section>
  );
}

// ── Nav ────────────────────────────────────────────────────────

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const [hover, setHover] = useState(false);
  return (
    <a href={href}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        fontFamily: V.mono, fontSize: 11, letterSpacing: "0.16em",
        textTransform: "uppercase", color: hover ? V.ink : V.inkDim,
        textDecoration: "none", transition: "color .2s",
      }}>{children}</a>
  );
}

function Nav() {
  return (
    <nav style={{
      position: "sticky", top: 0, zIndex: 50,
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "18px 40px",
      background: "rgba(0,0,0,0.6)",
      backdropFilter: "blur(20px) saturate(140%)",
      WebkitBackdropFilter: "blur(20px) saturate(140%)",
      borderBottom: `1px solid ${V.hairline}`,
    }}>
      <a href="#top" style={{ display: "flex", alignItems: "center", gap: 12, textDecoration: "none" }}>
        <VelloMark size={20} />
        <Wordmark size={12} />
      </a>
      <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
        {["notices", "patterns", "gaps", "memory", "privacy"].map(l => (
          <NavLink key={l} href={`#${l}`}>{l}</NavLink>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <Mono size={10} style={{ color: V.inkFaint }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 5, height: 5, borderRadius: "50%", background: V.good, boxShadow: `0 0 6px ${V.good}` }} />
            ONLINE
          </span>
        </Mono>
        <a href="#waitlist" style={{ textDecoration: "none" }}>
          <PrimaryBtn small>request access</PrimaryBtn>
        </a>
      </div>
    </nav>
  );
}

// ── Hero ───────────────────────────────────────────────────────

type BriefingKind = "temporal" | "signal" | "gap" | "inference";

interface BriefingItem {
  kind: BriefingKind;
  label: string;
  body: string;
  meta: string;
}

function BriefingRow({ item }: { item: BriefingItem }) {
  const tones: Record<BriefingKind, { dot: string; tag: string; bg: string }> = {
    temporal:  { dot: V.amber, tag: V.amber, bg: V.amberMist },
    signal:    { dot: V.amber, tag: V.ink,   bg: "transparent" },
    gap:       { dot: V.amber, tag: V.amber, bg: V.amberMist },
    inference: { dot: V.obs,   tag: V.obs,   bg: "transparent" },
  };
  const t = tones[item.kind];
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "14px 1fr auto", gap: 14, alignItems: "start",
      padding: "12px 14px", borderRadius: 10,
      background: t.bg,
      border: `1px solid ${item.kind === "gap" || item.kind === "temporal" ? V.amberSoft : V.border}`,
    }}>
      <div style={{ paddingTop: 5 }}>
        <Dot color={t.dot} size={6} />
      </div>
      <div>
        <Mono size={10} style={{
          color: t.tag, letterSpacing: "0.16em", textTransform: "uppercase",
          display: "block", marginBottom: 4,
        }}>
          {item.label}
        </Mono>
        <div style={{ fontFamily: V.sans, fontSize: 13, color: V.ink, lineHeight: 1.45 }}>
          {item.body}
        </div>
      </div>
      {item.meta && (
        <Mono size={10} style={{ color: V.inkDim, paddingTop: 5 }}>
          {item.meta}
        </Mono>
      )}
    </div>
  );
}

function BriefingCard() {
  const items: BriefingItem[] = [
    { kind: "temporal",  label: "pattern drift",            body: "gym usually 06:30 weekdays. it's 07:14.", meta: "+44 min" },
    { kind: "signal",    label: "travel planned",           body: "you mentioned a flight to lisbon next thursday.", meta: "high" },
    { kind: "gap",       label: "health · stated vs. observed", body: "you said you walk daily. observed: 3 days in 14.", meta: "" },
    { kind: "inference", label: "vello noticed",            body: "your sleep window has shifted ~40 min later this month.", meta: "" },
  ];

  const [visible, setVisible] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setVisible(v => Math.min(v + 1, items.length)), 700);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{
      position: "relative",
      background: `linear-gradient(180deg, ${V.surfaceHi}, ${V.surfaceLo})`,
      border: `1px solid ${V.border}`,
      borderRadius: 18,
      padding: "24px 24px 20px",
      boxShadow: `
        0 60px 120px -40px rgba(245,158,11,0.18),
        0 0 0 1px rgba(255,255,255,0.04),
        inset 0 1px 0 rgba(255,255,255,0.05)
      `,
      backdropFilter: "blur(20px)",
    }}>
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: 1, overflow: "hidden",
        opacity: 0.6,
      }}>
        <div style={{
          width: "100%", height: 1,
          background: `linear-gradient(90deg, transparent, ${V.amberGlow}, transparent)`,
          animation: "velloScan 4s ease-in-out infinite",
        }} />
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <VelloMark size={16} />
          <Mono size={10} style={{ color: V.inkDim, letterSpacing: "0.2em" }}>BRIEFING · TODAY</Mono>
        </div>
        <Mono size={10} style={{ color: V.inkFaint }}>04:25 · sat</Mono>
      </div>

      <div style={{
        fontFamily: V.serif, fontSize: 22, lineHeight: 1.35,
        color: V.ink, margin: "0 0 18px", letterSpacing: "-0.01em",
      }}>
        4 things to know,<br />
        <span style={{ color: V.inkDim, fontStyle: "italic" }}>none urgent.</span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {items.map((it, i) => (
          <div key={i} style={{
            opacity: i < visible ? 1 : 0,
            transform: i < visible ? "translateY(0)" : "translateY(8px)",
            transition: "opacity .5s ease, transform .5s ease",
          }}>
            <BriefingRow item={it} />
          </div>
        ))}
      </div>
    </div>
  );
}

function Hero() {
  return (
    <section id="top" style={{
      position: "relative", minHeight: "100vh",
      display: "flex", flexDirection: "column", justifyContent: "center",
      padding: "80px 40px 120px",
      overflow: "hidden",
    }}>
      <Bloom color={V.amberGlow} size={900} x="20%" y="60%" opacity={0.35} blur={140} />
      <Bloom color={V.obsSoft}   size={700} x="80%" y="40%" opacity={0.7}  blur={120} />

      <div style={{
        position: "absolute", inset: 0,
        backgroundImage: `linear-gradient(${V.hairline} 1px, transparent 1px), linear-gradient(90deg, ${V.hairline} 1px, transparent 1px)`,
        backgroundSize: "88px 88px",
        maskImage: "radial-gradient(ellipse at center, black 30%, transparent 70%)",
        WebkitMaskImage: "radial-gradient(ellipse at center, black 30%, transparent 70%)",
        pointerEvents: "none",
      }} />

      <div style={{
        position: "relative", zIndex: 2,
        maxWidth: 1200, margin: "0 auto", width: "100%",
        display: "grid", gridTemplateColumns: "1.05fr 1fr", gap: 80, alignItems: "center",
      }}>
        <div>
          <Eyebrow>
            <span style={{ marginRight: 4 }}>v.0426 ·</span>
            <LiveTime />
            <span style={{ marginLeft: 4, color: V.inkFaint }}>· local</span>
          </Eyebrow>

          <h1 style={{
            margin: "32px 0 28px",
            fontFamily: V.serif,
            fontSize: "clamp(56px, 7vw, 96px)",
            fontWeight: 400,
            lineHeight: 0.96,
            letterSpacing: "-0.025em",
            color: V.ink,
          }}>
            i notice<br />
            <span style={{ color: V.inkDim, fontStyle: "italic" }}>so you</span>{" "}
            <span style={{ position: "relative" }}>
              don't have to.
              <span style={{
                position: "absolute", left: 0, right: 0, bottom: "-2px", height: 2,
                background: `linear-gradient(90deg, transparent, ${V.amber} 40%, ${V.amber} 60%, transparent)`,
                boxShadow: `0 0 16px ${V.amber}`,
              }} />
            </span>
          </h1>

          <p style={{
            margin: "0 0 40px", maxWidth: 460,
            fontSize: 17, lineHeight: 1.6,
            color: V.inkDim, fontFamily: V.sans,
          }}>
            vello is a proactive life agent. it learns when you wake, when you work,
            when you're drifting from your own patterns — and surfaces what matters
            before you think to ask. ambient, not transactional.
          </p>

          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <a href="#waitlist" style={{ textDecoration: "none" }}>
              <PrimaryBtn>request access &nbsp;→</PrimaryBtn>
            </a>
            <a href="/dashboard" style={{ textDecoration: "none" }}>
              <GhostBtn>see a briefing</GhostBtn>
            </a>
            <Mono style={{ marginLeft: 8, color: V.inkFaint }}>1,203 on the list</Mono>
          </div>
        </div>

        <BriefingCard />
      </div>

      <div style={{
        position: "absolute", bottom: 32, left: "50%",
        display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
        animation: "velloDrift 2.5s ease-in-out infinite alternate",
      }}>
        <Mono style={{ color: V.inkFaint }}>scroll · vello is listening</Mono>
        <div style={{ width: 1, height: 36, background: `linear-gradient(${V.inkFaint}, transparent)` }} />
      </div>
    </section>
  );
}

// ── Signals ────────────────────────────────────────────────────

interface Signal {
  id: string; label: string; example: string; chains: string[];
}

const SIGNALS: Signal[] = [
  { id: "travel_planned",      label: "travel planned",      example: '"flying to lisbon next thursday"',     chains: ["schedule", "finance"] },
  { id: "job_change",          label: "job change",          example: '"first day at the new place monday"',  chains: ["moving", "finance"] },
  { id: "moving_home",         label: "moving home",         example: '"signed the lease this morning"',      chains: ["large purchase", "schedule"] },
  { id: "relationship_change", label: "relationship change", example: '"we\'re moving in together"',           chains: ["moving", "finance"] },
  { id: "health_event",        label: "health event",        example: '"started a new medication"',            chains: ["schedule"] },
  { id: "financial_shift",     label: "financial shift",     example: '"finally paid off the card"',          chains: ["large purchase"] },
  { id: "schedule_disruption", label: "schedule shift",      example: '"working from home now"',              chains: ["routines"] },
  { id: "large_purchase",      label: "large purchase",      example: '"the new laptop just arrived"',        chains: [] },
];

function SignalTile({ signal }: { signal: Signal }) {
  const [hover, setHover] = useState(false);
  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: hover ? V.surfaceHi : V.surface,
        padding: "24px 22px", minHeight: 140,
        display: "flex", flexDirection: "column", justifyContent: "space-between",
        transition: "background .25s ease",
        position: "relative", overflow: "hidden",
      }}>
      {hover && <Bloom color={V.amberSoft} size={300} x="50%" y="50%" opacity={0.6} blur={60} animate={false} />}
      <div style={{ position: "relative" }}>
        <Eyebrow color={V.amber}>{signal.label}</Eyebrow>
        <p style={{
          margin: "14px 0 0", fontFamily: V.serif, fontSize: 18,
          fontStyle: "italic", color: V.ink, lineHeight: 1.35,
        }}>
          {signal.example}
        </p>
      </div>
      {signal.chains.length > 0 && (
        <div style={{ position: "relative", display: "flex", alignItems: "center", gap: 8, marginTop: 20 }}>
          <Mono size={9} style={{ color: V.inkFaint }}>chains →</Mono>
          {signal.chains.map(c => (
            <Mono key={c} size={9} style={{
              color: V.inkDim, padding: "3px 7px",
              border: `1px solid ${V.border}`, borderRadius: 4,
            }}>{c}</Mono>
          ))}
        </div>
      )}
    </div>
  );
}

interface SignalMatch {
  id: string; conf: number; span: number[]; chained?: boolean;
}

function SignalDemo() {
  const phrases = [
    "we just signed the lease on the new place",
    "flying to lisbon next thursday for work",
    "first day at the new job is monday",
  ];
  const matches: SignalMatch[][] = [
    [{ id: "moving_home", conf: 0.92, span: [16, 27] }, { id: "large_purchase", conf: 0.34, span: [], chained: true }],
    [{ id: "travel_planned", conf: 0.96, span: [11, 17] }, { id: "schedule_disruption", conf: 0.22, span: [], chained: true }],
    [{ id: "job_change", conf: 0.98, span: [13, 25] }, { id: "moving_home", conf: 0.31, span: [], chained: true }, { id: "financial_shift", conf: 0.28, span: [], chained: true }],
  ];

  const [idx, setIdx] = useState(0);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setIdx(i => (i + 1) % phrases.length);
      setTick(t => t + 1);
    }, 6000);
    return () => clearInterval(id);
  }, []);

  return (
    <div style={{
      background: V.surface, border: `1px solid ${V.border}`, borderRadius: 16,
      padding: 28, display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 36, alignItems: "center",
      position: "relative", overflow: "hidden",
    }}>
      <Bloom color={V.amberSoft} size={500} x="0%" y="100%" opacity={0.6} blur={100} />
      <div style={{ position: "relative" }}>
        <Mono size={10} style={{ color: V.inkFaint, letterSpacing: "0.2em" }}>INPUT · DIALOGUE</Mono>
        <div style={{ marginTop: 16, minHeight: 80 }}>
          <span style={{ fontFamily: V.serif, fontSize: 28, color: V.ink, lineHeight: 1.3 }}>
            <Typewriter key={tick} text={phrases[idx]} speed={32} />
          </span>
        </div>
      </div>
      <div style={{ position: "relative" }}>
        <Mono size={10} style={{ color: V.inkFaint, letterSpacing: "0.2em" }}>SIGNALS · DETECTED</Mono>
        <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
          {matches[idx].map((m, i) => (
            <div key={`${tick}-${i}`} style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "10px 14px", borderRadius: 8,
              background: m.chained ? "transparent" : V.amberMist,
              border: `1px solid ${m.chained ? V.border : V.amberSoft}`,
              animation: `velloTypeIn .6s ease ${i * 0.4 + 0.8}s both`,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <Dot color={m.chained ? V.inkDim : V.amber} size={6} pulse={!m.chained} />
                <Mono size={11} style={{ color: m.chained ? V.inkDim : V.ink, letterSpacing: "0.1em" }}>
                  {m.id.replace(/_/g, " ")}
                </Mono>
                {m.chained && <Mono size={9} style={{ color: V.inkFaint }}>· watch</Mono>}
              </div>
              <Mono size={10} style={{ color: m.chained ? V.inkFaint : V.amber }}>
                {m.chained ? "arming" : `${(m.conf * 100).toFixed(0)}%`}
              </Mono>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SignalsSection() {
  return (
    <Section
      id="notices"
      eyebrow="01 · what i notice"
      title="i listen for the phrases that signal a life shift."
      kicker="eight signal classes, compiled as patterns. when one fires, vello quietly activates downstream watches — because life events arrive in cascades, not isolation."
    >
      <SignalDemo />
      <Hairline label="library · 8 classes" style={{ margin: "80px 0 40px" }} />
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 1,
        background: V.border, border: `1px solid ${V.border}`, borderRadius: 12, overflow: "hidden",
      }}>
        {SIGNALS.map(s => <SignalTile key={s.id} signal={s} />)}
      </div>
    </Section>
  );
}

// ── Temporal ───────────────────────────────────────────────────

function Legend({ color, label, sub, solid, dashed }: {
  color: string; label: string; sub: string; solid?: boolean; dashed?: boolean;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{
        width: 14, height: 14, borderRadius: solid ? 3 : "50%",
        background: solid ? color : (dashed ? "transparent" : color),
        border: dashed ? `1.5px dashed ${color}` : "none",
        boxShadow: !solid && !dashed ? `0 0 8px ${color}` : "none",
      }} />
      <div>
        <div style={{ fontFamily: V.sans, fontSize: 12, color: V.ink }}>{label}</div>
        <Mono size={10} style={{ color: V.inkFaint }}>{sub}</Mono>
      </div>
    </div>
  );
}

function PatternViz() {
  const mean = 412;
  const std = 18;
  const today = 444;
  const observations = [
    396, 405, 410, 412, 415, 418, 422, 408, 414, 417, 401, 419, 425, 411, 409, 420, 413, 416, 422, 408,
    490, 498, 502, 488, 495,
  ];
  const minV = 380, maxV = 520;
  const norm = (v: number) => ((v - minV) / (maxV - minV)) * 100;

  return (
    <div style={{
      background: V.surface, border: `1px solid ${V.border}`, borderRadius: 16,
      padding: "36px 40px", position: "relative", overflow: "hidden",
    }}>
      <Bloom color={V.obsSoft} size={400} x="80%" y="0%" opacity={0.7} blur={80} />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 36, position: "relative" }}>
        <div>
          <Mono size={10} style={{ color: V.inkFaint, letterSpacing: "0.2em" }}>PATTERN · GYM</Mono>
          <div style={{ marginTop: 8, fontFamily: V.serif, fontSize: 28, color: V.ink }}>
            mon · wed · fri <span style={{ color: V.inkDim }}>· n=25</span>
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <Mono size={10} style={{ color: V.amber, letterSpacing: "0.2em" }}>● TODAY</Mono>
          <div style={{ marginTop: 8, fontFamily: V.serif, fontSize: 28, color: V.amber }}>+32 min late</div>
        </div>
      </div>

      <div style={{ position: "relative", height: 120, marginBottom: 28 }}>
        <div style={{
          position: "absolute", left: `${norm(mean - std)}%`, width: `${norm(mean + std) - norm(mean - std)}%`,
          top: 0, bottom: 0, background: V.obsMist,
          border: `1px solid ${V.obsSoft}`, borderRadius: 4,
        }} />
        <div style={{
          position: "absolute", left: `${norm(mean)}%`, top: 0, bottom: 0, width: 1,
          background: V.obs, opacity: 0.5,
        }} />
        <div style={{
          position: "absolute", left: `${norm(mean + 1.5 * std)}%`, top: 0, bottom: 0, width: 1,
          background: V.amber, opacity: 0.3,
          backgroundImage: `repeating-linear-gradient(0deg, ${V.amber}, ${V.amber} 3px, transparent 3px, transparent 6px)`,
        }} />

        {observations.map((v, i) => (
          <div key={i} style={{
            position: "absolute", left: `${norm(v)}%`,
            top: `${20 + (i * 17) % 80}px`,
            width: 6, height: 6, borderRadius: "50%",
            background: V.obs, opacity: 0.7,
            boxShadow: `0 0 8px ${V.obs}`,
            transform: "translateX(-50%)",
          }} />
        ))}

        <div style={{
          position: "absolute", left: `${norm(today)}%`, top: "50%",
          transform: "translate(-50%, -50%)",
        }}>
          <div style={{
            width: 14, height: 14, borderRadius: "50%",
            background: V.amber,
            boxShadow: `0 0 24px ${V.amberGlow}, 0 0 0 4px rgba(245,158,11,0.15)`,
            animation: "velloDot 2s ease-in-out infinite",
          }} />
        </div>

        <div style={{ position: "absolute", left: 0, right: 0, bottom: -22, display: "flex", justifyContent: "space-between" }}>
          {["06:20", "06:40", "07:00", "07:20", "07:40", "08:00", "08:20", "08:40"].map(t => (
            <Mono key={t} size={9} style={{ color: V.inkFaint }}>{t}</Mono>
          ))}
        </div>
      </div>

      <div style={{ display: "flex", gap: 32, paddingTop: 24, borderTop: `1px solid ${V.hairline}`, position: "relative" }}>
        <Legend color={V.obs}     label="observations"    sub="n=25" />
        <Legend color={V.obsSoft} label="μ ± 1σ"          sub="06:52 · ±18 min" solid />
        <Legend color={V.amber}   label="+1.5σ threshold" sub="alert at 07:19"  dashed />
        <Legend color={V.amber}   label="today"           sub="07:24" />
      </div>
    </div>
  );
}

function TemporalSection() {
  return (
    <Section
      id="patterns"
      eyebrow="02 · how patterns emerge"
      title="i don't ask. i observe."
      kicker="every observation lands as minutes-since-midnight on a day-of-week. patterns form. when the gap between clusters exceeds 45 minutes, they split. when today's behavior strays past 1.5σ, you'll hear from me."
    >
      <PatternViz />
    </Section>
  );
}

// ── Gaps ───────────────────────────────────────────────────────

function GapPair({ stated, observed, domain, tone }: {
  stated: string; observed: string; domain: string; tone: string;
}) {
  return (
    <div style={{
      background: V.amberMist, border: `1px solid ${V.amberSoft}`,
      borderRadius: 14, padding: "24px 26px", position: "relative", overflow: "hidden",
    }}>
      <div style={{
        position: "absolute", inset: 0,
        background: `radial-gradient(ellipse at top right, ${V.amberSoft} 0%, transparent 60%)`,
        pointerEvents: "none",
      }} />
      <div style={{ position: "relative" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 18 }}>
          <Eyebrow color={V.amber}>{domain} · {tone}</Eyebrow>
          <Mono size={10} style={{ color: V.amber }}>◎ gap</Mono>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div>
            <Mono size={9} style={{ color: V.inkFaint, letterSpacing: "0.2em" }}>STATED</Mono>
            <p style={{ margin: "4px 0 0", fontFamily: V.serif, fontSize: 18, color: V.ink, fontStyle: "italic" }}>"{stated}"</p>
          </div>
          <div style={{ height: 1, background: V.amberSoft }} />
          <div>
            <Mono size={9} style={{ color: V.amber, letterSpacing: "0.2em" }}>OBSERVED</Mono>
            <p style={{ margin: "4px 0 0", fontFamily: V.mono, fontSize: 13, color: V.ink }}>{observed}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function GapsSection() {
  return (
    <Section
      id="gaps"
      eyebrow="03 · behavioral gaps"
      title="i hold what you say next to what you do."
      kicker="not to judge — to surface drift before it becomes denial. each gap is a small offering: the version of you that you described, beside the version you've been living."
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <GapPair stated="i exercise four times a week." observed="3 sessions in 14 days." domain="health" tone="missing pattern" />
        <GapPair stated="i'm a routine person." observed="work_start has σ = 78 min." domain="schedule" tone="routine variance" />
        <GapPair stated="i'm in bed by 10:30." observed="mean bedtime: 12:48." domain="sleep" tone="sleep mismatch" />
        <GapPair stated="i'm cooking more these days." observed="grocery cadence flat 6 weeks." domain="home" tone="missing pattern" />
      </div>
    </Section>
  );
}

// ── Dashboard Preview ──────────────────────────────────────────

function DSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <Mono size={10} style={{ color: V.inkFaint, letterSpacing: "0.2em", marginBottom: 12, display: "block" }}>{label}</Mono>
      {children}
    </div>
  );
}

function DCardDeviation() {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 18,
      padding: "18px 22px", borderRadius: 12,
      background: V.surface, border: `1px solid ${V.amberSoft}`,
      borderLeft: `2px solid ${V.amber}`,
    }}>
      <div style={{
        width: 36, height: 36, borderRadius: "50%",
        display: "grid", placeItems: "center",
        background: V.amberMist, border: `1px solid ${V.amberSoft}`,
        color: V.amber, fontSize: 18,
      }}>◷</div>
      <div style={{ flex: 1 }}>
        <p style={{ margin: 0, fontSize: 15, color: V.ink, fontFamily: V.sans }}>
          you usually start your gym session by 06:30. it's 07:14.
        </p>
        <Mono size={10} style={{ color: V.inkFaint, marginTop: 4, display: "block" }}>
          +44 min late · pattern · gym (mon/wed/fri, n=25)
        </Mono>
      </div>
    </div>
  );
}

function DCardGap() {
  return (
    <div style={{
      padding: "16px 20px", borderRadius: 12,
      background: V.amberMist, border: `1px solid ${V.amberSoft}`,
      display: "flex", gap: 14, alignItems: "flex-start",
    }}>
      <span style={{ color: V.amber, fontSize: 14, marginTop: 3 }}>◎</span>
      <div>
        <Mono size={10} style={{ color: V.amber, letterSpacing: "0.16em", marginBottom: 4, display: "block" }}>
          HEALTH · MISSING PATTERN
        </Mono>
        <p style={{ margin: 0, fontSize: 15, color: V.ink, lineHeight: 1.5 }}>
          you mentioned exercising four times a week. i've observed three sessions in fourteen days.
        </p>
      </div>
    </div>
  );
}

function DCardSignal() {
  return (
    <div style={{
      padding: "18px 22px", borderRadius: 12,
      background: V.surface, border: `1px solid ${V.border}`,
      display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16,
    }}>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
          <Dot color={V.amber} size={6} />
          <Mono size={10} style={{ color: V.inkDim, letterSpacing: "0.16em" }}>TRAVEL PLANNED</Mono>
        </div>
        <p style={{ margin: 0, fontSize: 15, color: V.ink }}>
          you mentioned a flight to lisbon next thursday. should i monitor itinerary changes?
        </p>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <PrimaryBtn small glow={false}>yes</PrimaryBtn>
        <GhostBtn small>later</GhostBtn>
      </div>
    </div>
  );
}

function DCardInference() {
  return (
    <div style={{
      padding: "18px 22px", borderRadius: 12,
      background: V.surface,
      border: `1px solid ${V.border}`,
      borderTop: `1px solid ${V.obsSoft}`,
      display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16,
    }}>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
          <Dot color={V.obs} size={6} />
          <Mono size={10} style={{ color: V.obs, letterSpacing: "0.16em" }}>VELLO NOTICED</Mono>
        </div>
        <p style={{ margin: 0, fontSize: 15, color: V.ink, fontFamily: V.serif, fontStyle: "italic" }}>
          your sleep window has shifted ~40 min later this month. should i update your schedule?
        </p>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <PrimaryBtn small glow={false}>looks right</PrimaryBtn>
        <GhostBtn small>no</GhostBtn>
      </div>
    </div>
  );
}

function DashboardPreview() {
  return (
    <Section
      id="dashboard"
      eyebrow="04 · the surface"
      title="a briefing, not a feed."
      kicker="when you open vello, you receive what's relevant — ordered by urgency, paused by completion. nothing scrolls forever. nothing demands. when there's nothing to say, i say nothing."
    >
      <div style={{
        position: "relative",
        borderRadius: 20, overflow: "hidden",
        border: `1px solid ${V.border}`,
        boxShadow: "0 80px 160px -60px rgba(245,158,11,0.18)",
      }}>
        <Bloom color={V.amberSoft} size={800} x="50%" y="0%" opacity={0.5} blur={140} />
        <div style={{
          background: `linear-gradient(180deg, ${V.surfaceLo}, #000 80%)`,
          position: "relative",
        }}>
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "16px 28px", borderBottom: `1px solid ${V.hairline}`,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <VelloMark size={16} />
              <Wordmark size={11} />
            </div>
            <div style={{ display: "flex", gap: 24 }}>
              {["briefing", "dialogue", "context", "routines", "settings"].map((l, i) => (
                <Mono key={l} size={10} style={{
                  color: i === 0 ? V.ink : V.inkFaint,
                  letterSpacing: "0.16em", textTransform: "uppercase",
                  paddingBottom: 4,
                  borderBottom: i === 0 ? `1px solid ${V.amber}` : "1px solid transparent",
                }}>{l}</Mono>
              ))}
            </div>
            <Mono size={10} style={{ color: V.inkFaint }}>e.veller@example.com</Mono>
          </div>

          <div style={{ padding: "52px 56px 64px", maxWidth: 760, margin: "0 auto", position: "relative" }}>
            <Mono size={10} style={{ color: V.inkDim, letterSpacing: "0.2em" }}>SATURDAY · APRIL 25</Mono>
            <h3 style={{
              margin: "12px 0 8px", fontFamily: V.serif, fontSize: 56, fontWeight: 400,
              color: V.ink, letterSpacing: "-0.02em", lineHeight: 1,
            }}>
              good morning, evelyn.
            </h3>
            <p style={{ margin: 0, fontSize: 16, color: V.inkDim, fontStyle: "italic", fontFamily: V.serif }}>
              four things to know. none urgent.
            </p>

            <div style={{ marginTop: 44, display: "flex", flexDirection: "column", gap: 28 }}>
              <DSection label="01 · running late"><DCardDeviation /></DSection>
              <DSection label="02 · gaps in your week"><DCardGap /></DSection>
              <DSection label="03 · signal · medium priority"><DCardSignal /></DSection>
              <DSection label="04 · vello noticed"><DCardInference /></DSection>
            </div>
          </div>
        </div>
      </div>

      <div style={{ marginTop: 32, display: "flex", justifyContent: "center", gap: 12 }}>
        <a href="/dashboard" style={{ textDecoration: "none" }}>
          <PrimaryBtn>open the full briefing &nbsp;→</PrimaryBtn>
        </a>
      </div>
    </Section>
  );
}

// ── Kortex ─────────────────────────────────────────────────────

function KortexFlow() {
  return (
    <div style={{
      position: "relative",
      background: V.surface, border: `1px solid ${V.border}`, borderRadius: 16,
      padding: 36, height: 360, overflow: "hidden",
    }}>
      <Bloom color={V.amberSoft} size={400} x="50%" y="50%" opacity={0.5} blur={100} />

      <div style={{
        position: "absolute", top: "50%", left: "70%", transform: "translate(-50%, -50%)",
        width: 92, height: 92, borderRadius: "50%",
        display: "grid", placeItems: "center",
        background: "radial-gradient(circle, #1a1611, #000)",
        border: `1px solid ${V.amberSoft}`,
        boxShadow: `0 0 60px ${V.amberGlow}, inset 0 0 30px rgba(245,158,11,0.15)`,
      }}>
        <VelloMark size={36} glow />
      </div>

      <div style={{
        position: "absolute", top: "50%", left: "20%", transform: "translate(-50%, -50%)",
        width: 70, height: 70, borderRadius: 12,
        display: "grid", placeItems: "center",
        background: V.surfaceHi, border: `1px solid ${V.borderHi}`,
        fontFamily: V.mono, fontSize: 9, color: V.inkDim,
        letterSpacing: "0.18em",
      }}>
        KORTEX
      </div>

      <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{
        position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none",
      }}>
        <defs>
          <linearGradient id="velloKortexLine" x1="0" x2="1">
            <stop offset="0" stopColor={V.amber} stopOpacity="0" />
            <stop offset="0.5" stopColor={V.amber} stopOpacity="0.6" />
            <stop offset="1" stopColor={V.amber} stopOpacity="0" />
          </linearGradient>
        </defs>
        <line x1="20" y1="50" x2="70" y2="50" stroke="url(#velloKortexLine)" strokeWidth="0.4" />
      </svg>

      {[0, 1.2, 2.4].map((d, i) => (
        <div key={i} style={{
          position: "absolute", top: "50%", left: "20%",
          width: 4, height: 4, borderRadius: "50%",
          background: V.amber, boxShadow: `0 0 10px ${V.amber}`,
          animation: `velloPacket 3.6s linear infinite ${d}s`,
          transform: "translate(-50%, -50%)",
        }} />
      ))}

      <Mono size={10} style={{ position: "absolute", top: "70%", left: "20%", transform: "translateX(-50%)", color: V.inkDim }}>
        external memory
      </Mono>
      <Mono size={10} style={{ position: "absolute", top: "70%", left: "70%", transform: "translateX(-50%)", color: V.amber }}>
        vello
      </Mono>
    </div>
  );
}

function KortexSection() {
  return (
    <Section
      id="memory"
      eyebrow="05 · connected memory"
      title="i can read your other selves."
      kicker="if you've been keeping memory in kortex, vello can ingest it: facts, structured triples, even the contradictions between what you've claimed at different points in time. one connection, one token."
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32, alignItems: "center" }}>
        <KortexFlow />
        <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 24 }}>
          {[
            { tag: "life_context",   body: "domain · key · value entries upserted directly to your profile." },
            { tag: "facts",          body: "freeform sentences scanned for any of the eight signal classes." },
            { tag: "triples",        body: "structured subject/predicate/object assertions become inferences." },
            { tag: "contradictions", body: "when claims conflict across time, you confirm the truer one." },
          ].map(it => (
            <li key={it.tag} style={{ borderLeft: `1px solid ${V.amberSoft}`, paddingLeft: 18 }}>
              <Mono size={10} style={{ color: V.amber, letterSpacing: "0.18em" }}>{it.tag.toUpperCase()}</Mono>
              <p style={{ margin: "6px 0 0", fontSize: 15, color: V.ink, lineHeight: 1.55 }}>{it.body}</p>
            </li>
          ))}
        </ul>
      </div>
    </Section>
  );
}

// ── Privacy ────────────────────────────────────────────────────

function PrivacySection() {
  return (
    <Section
      id="privacy"
      eyebrow="06 · privacy posture"
      title="ambient does not mean accessible."
      kicker="vello is for an audience of one. your patterns belong to you. nothing leaves your account except what you ask to leave."
    >
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 1,
        background: V.border, border: `1px solid ${V.border}`, borderRadius: 12, overflow: "hidden",
      }}>
        {[
          { glyph: "⌖", title: "local-first by default", body: "observations live in your sqlite. cloud sync is opt-in and end-to-end keyed." },
          { glyph: "⌬", title: "no behavioral exhaust",  body: "no analytics on your usage. no telemetry. the agent watches you — and only you." },
          { glyph: "◇", title: "forget on request",      body: "every observation, signal, and inference can be expired or wiped, individually or whole." },
        ].map(c => (
          <div key={c.title} style={{ background: V.surface, padding: "36px 28px" }}>
            <div style={{ fontSize: 36, color: V.amber, marginBottom: 18, fontFamily: V.serif }}>{c.glyph}</div>
            <h4 style={{ margin: 0, fontSize: 18, fontFamily: V.serif, color: V.ink, fontWeight: 400 }}>{c.title}</h4>
            <p style={{ margin: "10px 0 0", fontSize: 14, color: V.inkDim, lineHeight: 1.55 }}>{c.body}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}

// ── Roadmap ────────────────────────────────────────────────────

type RoadmapState = "active" | "building" | "planned";

function StatePill({ state }: { state: RoadmapState }) {
  const map: Record<RoadmapState, { color: string; label: string }> = {
    active:   { color: V.amber,  label: "● LIVE"      },
    building: { color: V.obs,    label: "◔ BUILDING"  },
    planned:  { color: V.inkDim, label: "○ PLANNED"   },
  };
  const m = map[state];
  return (
    <Mono size={10} style={{
      color: m.color, letterSpacing: "0.16em",
      padding: "5px 11px", borderRadius: 999,
      border: `1px solid ${state === "active" ? V.amberSoft : V.border}`,
    }}>
      {m.label}
    </Mono>
  );
}

function RoadmapSection() {
  const items: { phase: string; title: string; body: string; state: RoadmapState }[] = [
    { phase: "now",  title: "the briefing surface",  body: "temporal deviations · behavioral gaps · signal triggers · pending inferences.", state: "active" },
    { phase: "q3",   title: "mobile · android first", body: "real geofencing. zone enter/exit feeds the temporal engine natively.", state: "building" },
    { phase: "q4",   title: "values layer",           body: "stop asking what you value. observe it from how you spend your time.", state: "planned" },
    { phase: "2027", title: "trajectory modeling",    body: "not where you are — the vector of where you're going. inflection points surfaced.", state: "planned" },
    { phase: "2027", title: "partner sync",           body: "opt-in shared context for households. notify_mode + relationship-aware routing.", state: "planned" },
    { phase: "soon", title: "desktop hub",            body: "a quiet background presence on macos · windows · linux. calendar & app context.", state: "planned" },
  ];
  return (
    <Section
      id="roadmap"
      eyebrow="07 · what's next"
      title="i'm building toward an agent that watches your trajectory, not your clock."
      kicker="time is the only currency. vello's job is to spend less of yours on knowing where you are and more on where you're going."
    >
      <div style={{ display: "flex", flexDirection: "column" }}>
        {items.map((it, i) => (
          <div key={i} style={{
            display: "grid", gridTemplateColumns: "120px 1fr auto",
            gap: 32, alignItems: "baseline",
            padding: "28px 0", borderTop: i === 0 ? "none" : `1px solid ${V.hairline}`,
          }}>
            <Mono size={11} style={{ color: it.state === "active" ? V.amber : V.inkDim, letterSpacing: "0.18em" }}>
              {it.phase.toUpperCase()}
            </Mono>
            <div>
              <h4 style={{
                margin: 0, fontFamily: V.serif, fontSize: 28, fontWeight: 400,
                color: V.ink, letterSpacing: "-0.01em", lineHeight: 1.15,
              }}>{it.title}</h4>
              <p style={{ margin: "8px 0 0", fontSize: 15, color: V.inkDim, lineHeight: 1.5, maxWidth: 560 }}>{it.body}</p>
            </div>
            <StatePill state={it.state} />
          </div>
        ))}
      </div>
    </Section>
  );
}

// ── Waitlist ───────────────────────────────────────────────────

function WaitlistSection() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);
  return (
    <section id="waitlist" style={{
      position: "relative", padding: "180px 40px",
      borderTop: `1px solid ${V.hairline}`, overflow: "hidden",
    }}>
      <Bloom color={V.amberGlow} size={1200} x="50%" y="50%" opacity={0.35} blur={160} />
      <Bloom color={V.obsSoft} size={500} x="20%" y="80%" opacity={0.6} blur={80} />

      <div style={{ maxWidth: 720, margin: "0 auto", textAlign: "center", position: "relative" }}>
        <Eyebrow>08 · request access</Eyebrow>
        <h2 style={{
          margin: "24px 0 18px",
          fontFamily: V.serif, fontWeight: 400,
          fontSize: "clamp(48px, 6vw, 80px)",
          lineHeight: 1, letterSpacing: "-0.025em",
          color: V.ink,
        }}>
          let me start watching.
        </h2>
        <p style={{
          margin: "0 auto 44px", maxWidth: 480,
          fontSize: 17, color: V.inkDim, lineHeight: 1.55,
        }}>
          vello is in private beta. one personal license, one device, one quiet agent — for the rest of the year, free.
        </p>

        {!done ? (
          <form
            onSubmit={e => { e.preventDefault(); if (email.trim()) setDone(true); }}
            style={{
              display: "flex", gap: 8, padding: 7,
              background: V.surface, border: `1px solid ${V.border}`,
              borderRadius: 999, maxWidth: 480, margin: "0 auto",
              boxShadow: "0 0 40px rgba(245,158,11,0.08)",
            }}>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@somewhere.com"
              style={{
                flex: 1, background: "transparent", border: "none", outline: "none",
                color: V.ink, fontFamily: V.sans, fontSize: 14,
                padding: "10px 18px",
              }}
            />
            <PrimaryBtn>request &nbsp;→</PrimaryBtn>
          </form>
        ) : (
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 14,
            padding: "14px 28px", borderRadius: 999,
            background: V.amberMist, border: `1px solid ${V.amberSoft}`,
            color: V.ink,
          }}>
            <Dot color={V.amber} size={7} />
            <span style={{ fontFamily: V.serif, fontSize: 17, fontStyle: "italic" }}>
              noted. you'll hear from vello soon.
            </span>
          </div>
        )}

        <div style={{ marginTop: 36, display: "inline-flex", gap: 24 }}>
          <Mono style={{ color: V.inkFaint }}>1,203 already on the list</Mono>
          <Mono style={{ color: V.inkFaint }}>·</Mono>
          <Mono style={{ color: V.inkFaint }}>founding pricing locked through 2027</Mono>
        </div>
      </div>
    </section>
  );
}

// ── Footer ─────────────────────────────────────────────────────

function FootLink({ children }: { children: React.ReactNode }) {
  const [hover, setHover] = useState(false);
  return (
    <a href="#"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        fontFamily: V.sans, fontSize: 13, color: hover ? V.ink : V.inkDim,
        textDecoration: "none", transition: "color .2s",
      }}>{children}</a>
  );
}

function FootCol({ title, links }: { title: string; links: string[] }) {
  return (
    <div>
      <Mono size={10} style={{ color: V.inkFaint, letterSpacing: "0.2em", marginBottom: 16, display: "block" }}>
        {title.toUpperCase()}
      </Mono>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
        {links.map(l => <li key={l}><FootLink>{l}</FootLink></li>)}
      </ul>
    </div>
  );
}

function Footer() {
  return (
    <footer style={{ padding: "64px 40px 48px", borderTop: `1px solid ${V.hairline}` }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr 1fr 1fr", gap: 48, marginBottom: 64 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 18 }}>
              <VelloMark size={20} />
              <Wordmark size={12} />
            </div>
            <p style={{ margin: 0, maxWidth: 320, fontSize: 14, color: V.inkDim, lineHeight: 1.55, fontFamily: V.serif, fontStyle: "italic" }}>
              the agent that watches your patterns, not your screen.
            </p>
          </div>
          <FootCol title="product"   links={["briefing", "dialogue", "context", "routines"]} />
          <FootCol title="thinking"  links={["privacy posture", "changelog", "philosophy", "roadmap"]} />
          <FootCol title="elsewhere" links={["kortex", "github", "press kit", "contact"]} />
        </div>

        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          paddingTop: 28, borderTop: `1px solid ${V.hairline}`,
        }}>
          <Mono style={{ color: V.inkFaint }}>
            v.0426 · running locally · last sync <LiveTime />
          </Mono>
          <Mono style={{ color: V.inkFaint }}>© 2026 vello — for an audience of one</Mono>
        </div>
      </div>
    </footer>
  );
}

// ── Landing page root ──────────────────────────────────────────

export default function LandingPage() {
  return (
    <div style={{ background: V.bg, minHeight: "100vh", color: V.ink }}>
      <Nav />
      <Hero />
      <SignalsSection />
      <TemporalSection />
      <GapsSection />
      <DashboardPreview />
      <KortexSection />
      <PrivacySection />
      <RoadmapSection />
      <WaitlistSection />
      <Footer />
    </div>
  );
}
