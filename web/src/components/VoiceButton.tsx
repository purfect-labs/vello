/**
 * VoiceButton — microphone toggle with live state feedback.
 *
 * Visual states:
 *   idle       — grey mic icon
 *   listening  — pulsing red glow, waveform animation
 *   processing — spinning
 *   speaking   — green waveform
 *   unsupported — hidden (nothing rendered)
 */

import React from "react";
import type { VoiceState } from "../hooks/useVoice";

interface VoiceButtonProps {
  state: VoiceState;
  isSupported: boolean;
  listening: boolean;
  onToggle: () => void;
  className?: string;
}

const icons: Record<VoiceState, string> = {
  idle: "🎤",
  listening: "🎙️",
  processing: "⏳",
  speaking: "🔊",
};

const labels: Record<VoiceState, string> = {
  idle: "Click to speak",
  listening: "Listening…",
  processing: "Processing…",
  speaking: "Speaking…",
};

const VoiceButton: React.FC<VoiceButtonProps> = ({
  state,
  isSupported,
  listening,
  onToggle,
  className = "",
}) => {
  if (!isSupported) return null;

  return (
    <button
      type="button"
      onClick={onToggle}
      title={labels[state]}
      className={`voice-btn voice-btn--${state} ${className}`}
      aria-label={labels[state]}
      style={{
        width: 40,
        height: 40,
        borderRadius: "50%",
        border: "2px solid",
        borderColor:
          state === "listening"
            ? "#ef4444"
            : state === "speaking"
              ? "#22c55e"
              : state === "processing"
                ? "#f59e0b"
                : "#6b7280",
        background:
          state === "listening"
            ? "rgba(239,68,68,0.1)"
            : state === "speaking"
              ? "rgba(34,197,94,0.1)"
              : state === "processing"
                ? "rgba(245,158,11,0.1)"
                : "transparent",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        cursor: "pointer",
        fontSize: 18,
        transition: "all 0.2s ease",
        animation:
          state === "listening"
            ? "voicePulse 1.5s ease-in-out infinite"
            : state === "processing"
              ? "voiceSpin 1s linear infinite"
              : "none",
        position: "relative",
      }}
    />
  );
};

export default VoiceButton;

// ── Inject keyframes once ──────────────────────────────────────────────────

const styleId = "kortex-voice-styles";
if (typeof document !== "undefined" && !document.getElementById(styleId)) {
  const style = document.createElement("style");
  style.id = styleId;
  style.textContent = `
    @keyframes voicePulse {
      0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.4); }
      50%      { box-shadow: 0 0 0 8px rgba(239,68,68,0); }
    }
    @keyframes voiceSpin {
      from { transform: rotate(0deg); }
      to   { transform: rotate(360deg); }
    }
    .voice-waveform {
      display: flex;
      align-items: center;
      gap: 2px;
      height: 16px;
    }
    .voice-waveform-bar {
      width: 3px;
      background: currentColor;
      border-radius: 2px;
      animation: voiceBounce 0.6s ease-in-out infinite;
    }
    .voice-waveform-bar:nth-child(1) { animation-delay: 0s; height: 6px; }
    .voice-waveform-bar:nth-child(2) { animation-delay: 0.1s; height: 12px; }
    .voice-waveform-bar:nth-child(3) { animation-delay: 0.2s; height: 16px; }
    .voice-waveform-bar:nth-child(4) { animation-delay: 0.3s; height: 12px; }
    .voice-waveform-bar:nth-child(5) { animation-delay: 0.4s; height: 6px; }
    @keyframes voiceBounce {
      0%, 100% { transform: scaleY(0.4); }
      50%      { transform: scaleY(1); }
    }
  `;
  document.head.appendChild(style);
}
