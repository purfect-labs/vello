import { useEffect, useRef, useState } from "react";
import Nav from "../components/Nav";
import { api } from "../api";
import { useAuth } from "../App";
import type { DialogueTurn } from "../types";
import { V } from "../vello-tokens";

function Bubble({ turn }: { turn: DialogueTurn }) {
  const isUser = turn.role === "user";
  return (
    <div style={{
      display: "flex",
      justifyContent: isUser ? "flex-end" : "flex-start",
      alignItems: "flex-start",
      gap: 10,
      marginBottom: 20,
    }}>
      {!isUser && (
        <div style={{
          width: 22, height: 22, borderRadius: "50%", flexShrink: 0, marginTop: 2,
          background: `radial-gradient(circle, ${V.amberMist}, ${V.bg})`,
          border: `1px solid ${V.amberSoft}`,
          display: "grid", placeItems: "center",
        }}>
          <span style={{ width: 5, height: 5, borderRadius: "50%", background: V.obs, boxShadow: `0 0 6px ${V.obs}`, display: "block" }} />
        </div>
      )}
      <div style={{
        maxWidth: "68%",
        background: isUser ? "rgba(255,255,255,0.04)" : "transparent",
        border: isUser ? `1px solid ${V.border}` : "none",
        borderRadius: isUser ? 14 : 0,
        padding: isUser ? "10px 16px" : "2px 0",
        fontSize: 15,
        fontFamily: isUser ? V.sans : V.serif,
        fontStyle: isUser ? "normal" : "italic",
        color: V.ink,
        lineHeight: 1.6,
        whiteSpace: "pre-wrap",
      }}>
        {turn.content}
      </div>
    </div>
  );
}

export default function DialoguePage() {
  const { refreshUser }           = useAuth();
  const [history, setHistory]     = useState<DialogueTurn[]>([]);
  const [input, setInput]         = useState("");
  const [sending, setSending]     = useState(false);
  const [streaming, setStreaming] = useState(false);
  const bottomRef                 = useRef<HTMLDivElement>(null);
  const inputRef                  = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api.dialogue.history().then(h => {
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
    setHistory(h => [...h, { role: "user", content: text, created_at: new Date().toISOString() }]);
    setSending(true);
    setStreaming(true);
    try {
      const res = await api.dialogue.send(text);
      setHistory(h => [...h, { role: "assistant", content: res.message, created_at: new Date().toISOString() }]);
      if (res.onboarding_complete) await refreshUser();
    } catch {
      setHistory(h => [...h, { role: "assistant", content: "Something went wrong. Please try again.", created_at: new Date().toISOString() }]);
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

  const [inputFocus, setInputFocus] = useState(false);

  return (
    <div style={{ minHeight: "100vh", background: V.bg, display: "flex", flexDirection: "column" }}>
      <Nav />

      <div style={{ maxWidth: 660, margin: "0 auto", width: "100%", flex: 1, display: "flex", flexDirection: "column", padding: "0 24px" }}>

        {/* Header */}
        <div style={{ padding: "40px 0 28px", borderBottom: `1px solid ${V.hairline}`, marginBottom: 36 }}>
          <span style={{ fontFamily: V.mono, fontSize: 10, letterSpacing: "0.2em", color: V.inkFaint, textTransform: "uppercase" }}>dialogue</span>
          <h1 style={{ margin: "14px 0 10px", fontFamily: V.serif, fontWeight: 400, fontSize: "clamp(32px, 4vw, 44px)", color: V.ink, letterSpacing: "-0.02em", lineHeight: 1 }}>
            talk naturally.
          </h1>
          <p style={{ margin: 0, fontFamily: V.sans, fontSize: 14, color: V.inkDim, lineHeight: 1.55, maxWidth: 480 }}>
            vello listens and builds your profile over time. everything you share is editable in life context.
          </p>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: "auto", paddingBottom: 16 }}>
          {history.map((turn, i) => <Bubble key={i} turn={turn} />)}

          {streaming && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
              <div style={{
                width: 22, height: 22, borderRadius: "50%",
                background: `radial-gradient(circle, ${V.amberMist}, ${V.bg})`,
                border: `1px solid ${V.amberSoft}`,
                display: "grid", placeItems: "center", flexShrink: 0,
              }}>
                <span style={{ width: 5, height: 5, borderRadius: "50%", background: V.obs, display: "block", animation: "velloDot 1s ease-in-out infinite" }} />
              </div>
              <span style={{ fontFamily: V.serif, fontStyle: "italic", fontSize: 14, color: V.inkDim }}>thinking…</span>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={{ borderTop: `1px solid ${V.hairline}`, padding: "16px 0 28px" }}>
          <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onInput={handleInput}
              onFocus={() => setInputFocus(true)}
              onBlur={() => setInputFocus(false)}
              placeholder="say anything…"
              rows={1}
              disabled={sending}
              style={{
                flex: 1,
                background: V.surface,
                border: `1px solid ${inputFocus ? V.borderHi : V.border}`,
                borderRadius: 12, padding: "11px 16px",
                fontSize: 14, color: V.ink,
                resize: "none", outline: "none",
                minHeight: 44, maxHeight: 140,
                transition: "border-color .2s",
                fontFamily: V.sans,
              }}
            />
            <button
              onClick={send}
              disabled={!input.trim() || sending}
              style={{
                fontFamily: V.sans, fontSize: 13, fontWeight: 600,
                color: "#100c06", background: !input.trim() || sending ? V.inkFaint : V.ink,
                border: "none", borderRadius: 999, padding: "10px 20px",
                cursor: !input.trim() || sending ? "default" : "pointer",
                transition: "background .2s", flexShrink: 0,
              }}>
              send
            </button>
          </div>
          <p style={{ margin: "8px 0 0", fontFamily: V.mono, fontSize: 10, color: V.inkFaint, textAlign: "center", letterSpacing: "0.1em" }}>
            ENTER TO SEND · SHIFT+ENTER FOR NEW LINE
          </p>
        </div>
      </div>
    </div>
  );
}
