import { useEffect, useRef, useState } from "react";
import Nav from "../components/Nav";
import { api } from "../api";
import { useAuth } from "../App";
import type { DialogueTurn } from "../types";
import { colors, typography, radius } from "../design-system";

function Bubble({ turn }: { turn: DialogueTurn }) {
  const isUser = turn.role === "user";
  return (
    <div style={{ display: "flex", justifyContent: isUser ? "flex-end" : "flex-start", marginBottom: 16 }}>
      {!isUser && (
        <span style={{ fontSize: 11, fontWeight: typography.weight.bold, color: colors.muted, marginRight: 10, marginTop: 3, flexShrink: 0, letterSpacing: "0.05em" }}>
          V
        </span>
      )}
      <div style={{
        maxWidth: "68%",
        background: isUser ? "rgba(255,255,255,0.07)" : "transparent",
        border: isUser ? "1px solid rgba(255,255,255,0.1)" : "none",
        borderRadius: isUser ? radius.md : 0,
        padding: isUser ? "10px 14px" : "2px 0",
        fontSize: typography.size.md,
        color: colors.primary,
        lineHeight: typography.lineHeight.loose,
        whiteSpace: "pre-wrap",
      }}>
        {turn.content}
      </div>
    </div>
  );
}

export default function DialoguePage() {
  const { refreshUser }            = useAuth();
  const [history, setHistory]      = useState<DialogueTurn[]>([]);
  const [input, setInput]          = useState("");
  const [sending, setSending]      = useState(false);
  const [streaming, setStreaming]  = useState(false);
  const bottomRef                  = useRef<HTMLDivElement>(null);
  const inputRef                   = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api.dialogue.history().then((h) => {
      setHistory(h as DialogueTurn[]);
      if (h.length === 0) kickOff();
    }).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, streaming]);

  async function kickOff() {
    setSending(true);
    try {
      const res = await api.dialogue.start();
      if (res.message) {
        setHistory([{ role: "assistant", content: res.message, created_at: new Date().toISOString() }]);
      }
    } finally {
      setSending(false);
    }
  }

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");

    const userTurn: DialogueTurn = { role: "user", content: text, created_at: new Date().toISOString() };
    setHistory((h) => [...h, userTurn]);
    setSending(true);
    setStreaming(true);

    try {
      const res = await api.dialogue.send(text);
      const assistantTurn: DialogueTurn = { role: "assistant", content: res.message, created_at: new Date().toISOString() };
      setHistory((h) => [...h, assistantTurn]);
      if (res.onboarding_complete) await refreshUser();
    } catch {
      setHistory((h) => [...h, { role: "assistant", content: "Something went wrong. Please try again.", created_at: new Date().toISOString() }]);
    } finally {
      setSending(false);
      setStreaming(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  }

  function handleInput(e: React.FormEvent<HTMLTextAreaElement>) {
    const el = e.currentTarget;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }

  return (
    <div style={{ minHeight: "100vh", background: colors.bg, display: "flex", flexDirection: "column" }}>
      <Nav />

      <div style={{ maxWidth: 680, margin: "0 auto", width: "100%", flex: 1, display: "flex", flexDirection: "column", padding: "0 24px" }}>

        {/* Header */}
        <div style={{ padding: "36px 0 24px", borderBottom: `1px solid ${colors.border}`, marginBottom: 32 }}>
          <p style={{ margin: "0 0 6px", fontSize: typography.size.xs, color: colors.muted, fontWeight: typography.weight.bold, letterSpacing: "0.12em" }}>VELLO</p>
          <h1 style={{ margin: 0, fontSize: typography.size["2xl"], fontWeight: typography.weight.extrabold, color: colors.white, letterSpacing: "-0.03em" }}>Dialogue</h1>
          <p style={{ margin: "8px 0 0", fontSize: typography.size.base, color: colors.muted, lineHeight: typography.lineHeight.normal }}>
            Talk naturally. Vello listens and builds your profile over time. Everything you share is editable in Life Context.
          </p>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: "auto", paddingBottom: 16 }}>
          {history.map((turn, i) => <Bubble key={i} turn={turn} />)}

          {streaming && (
            <div style={{ display: "flex", marginBottom: 16 }}>
              <span style={{ fontSize: 11, fontWeight: typography.weight.bold, color: colors.muted, marginRight: 10, letterSpacing: "0.05em" }}>V</span>
              <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", background: colors.borderStrong, animation: "pulse 1s infinite" }} />
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={{ borderTop: `1px solid ${colors.border}`, padding: "16px 0 24px" }}>
          <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onInput={handleInput}
              placeholder="Say anything…"
              rows={1}
              disabled={sending}
              style={{
                flex: 1, background: colors.surface, border: `1px solid ${colors.border}`,
                borderRadius: radius.md, padding: "11px 14px", fontSize: typography.size.md,
                color: colors.primary, resize: "none", outline: "none",
                minHeight: 44, maxHeight: 140, transition: "border-color 0.15s",
                fontFamily: "inherit",
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = colors.borderStrong)}
              onBlur={(e)  => (e.currentTarget.style.borderColor = colors.border)}
            />
            <button
              onClick={send}
              disabled={!input.trim() || sending}
              className="btn-primary"
              style={{ fontSize: 13, padding: "10px 18px", flexShrink: 0 }}
            >
              Send
            </button>
          </div>
          <p style={{ margin: "8px 0 0", fontSize: typography.size.xs, color: colors.faint, textAlign: "center" }}>
            Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
}
