/**
 * useVoice — browser-native speech recognition + synthesis.
 *
 * Zero cost. Zero dependencies. Uses the Web Speech API built into Chrome/Edge/Safari.
 *
 * Three modes:
 *   push-to-talk — hold mic button, release to send
 *   wake-word     — "Hey Kortex" activates listening (continuous)
 *   always-on     — mic is always hot (shown as a toggle)
 *
 * SpeechSynthesis voices can be cycled per-speaker for multi-voice debates.
 */

import { useCallback, useEffect, useRef, useState } from "react";

// ── SpeechRecognition Type Declarations (not in default TS DOM lib) ────────

interface SpeechRecognitionEvent extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message?: string;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

declare var SpeechRecognition: {
  new (): SpeechRecognition;
} | undefined;

declare var webkitSpeechRecognition: {
  new (): SpeechRecognition;
} | undefined;

// ── Types ────────────────────────────────────────────────────────────────

export type VoiceMode = "push-to-talk" | "wake-word" | "always-on";
export type VoiceState = "idle" | "listening" | "processing" | "speaking";

export interface VoiceOptions {
  mode?: VoiceMode;
  wakeWord?: string;
  onResult?: (transcript: string, isFinal: boolean) => void;
  onFinalResult?: (transcript: string) => void;
  onError?: (error: string) => void;
  onStateChange?: (state: VoiceState) => void;
  /** Called when wake word detected (mode: wake-word) */
  onWake?: () => void;
  /** Whether to auto-speak AI responses */
  autoSpeak?: boolean;
}

export interface VoiceAPI {
  state: VoiceState;
  isSupported: boolean;
  listening: boolean;
  startListening: () => void;
  stopListening: () => void;
  speak: (text: string, voiceIndex?: number) => void;
  stopSpeaking: () => void;
  setMode: (mode: VoiceMode) => void;
  /** List of available SpeechSynthesis voices */
  voices: SpeechSynthesisVoice[];
}

// ── Helpers ──────────────────────────────────────────────────────────────

const SpeechRecognitionAPI: typeof SpeechRecognition | undefined =
  (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

function getVoices(): SpeechSynthesisVoice[] {
  return window.speechSynthesis?.getVoices() ?? [];
}

/** Pick distinct voices from different "families" for multi-speaker debate */
export function getDistinctVoices(count: number): SpeechSynthesisVoice[] {
  const all = getVoices();
  if (all.length === 0) return [];
  // Prefer English voices, group by name root
  const en = all.filter((v) => v.lang.startsWith("en"));
  const pool = en.length >= count ? en : all;
  // Dedupe by voiceURI root
  const seen = new Set<string>();
  const distinct: SpeechSynthesisVoice[] = [];
  for (const v of pool) {
    const root = v.voiceURI.replace(/[^a-zA-Z]/g, "").toLowerCase();
    if (!seen.has(root)) {
      seen.add(root);
      distinct.push(v);
      if (distinct.length >= count) break;
    }
  }
  return distinct;
}

// ── Hook ──────────────────────────────────────────────────────────────────

export function useVoice(options: VoiceOptions = {}): VoiceAPI {
  const {
    mode: initialMode = "push-to-talk",
    wakeWord = "hey cortex",
    onResult,
    onFinalResult,
    onError,
    onStateChange,
    onWake,
    autoSpeak = true,
  } = options;

  const [state, setState] = useState<VoiceState>("idle");
  const [listening, setListening] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>(getVoices());
  const [mode, setModeState] = useState<VoiceMode>(initialMode);

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const stateRef = useRef<VoiceState>("idle");
  const modeRef = useRef<VoiceMode>(initialMode);
  const wakeWordRef = useRef(wakeWord.toLowerCase());
  const transcriptRef = useRef("");

  const isSupported = !!SpeechRecognitionAPI;

  // ── Voice list ──────────────────────────────────────────────────

  useEffect(() => {
    const update = () => setVoices(getVoices());
    update();
    window.speechSynthesis?.addEventListener("voiceschanged", update);
    return () => {
      window.speechSynthesis?.removeEventListener("voiceschanged", update);
    };
  }, []);

  // ── State tracking ──────────────────────────────────────────────

  const setVoiceState = useCallback(
    (s: VoiceState) => {
      stateRef.current = s;
      setState(s);
      onStateChange?.(s);
    },
    [onStateChange],
  );

  // ── Speech Recognition ──────────────────────────────────────────

  const createRecognition = useCallback((): SpeechRecognition => {
    const rec = new SpeechRecognitionAPI!();
    rec.continuous = modeRef.current === "wake-word" || modeRef.current === "always-on";
    rec.interimResults = true;
    rec.lang = "en-US";
    rec.maxAlternatives = 1;

    rec.onresult = (event: SpeechRecognitionEvent) => {
      let interim = "";
      let final = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const text = result[0].transcript.trim();
        if (result.isFinal) {
          final += " " + text;
        } else {
          interim += " " + text;
        }
      }

      const combined = (final || interim).trim();
      transcriptRef.current = combined;

      // Wake-word mode: check if wake word was spoken
      if (modeRef.current === "wake-word" && combined.toLowerCase().includes(wakeWordRef.current)) {
        // Extract what comes after the wake word
        const idx = combined.toLowerCase().indexOf(wakeWordRef.current);
        const after = combined.slice(idx + wakeWordRef.current.length).trim();
        onWake?.();
        if (after && final) {
          onFinalResult?.(after);
          transcriptRef.current = "";
          stopRecognition();
        }
        return;
      }

      onResult?.(combined, !!final);

      if (final) {
        onFinalResult?.(combined);
        transcriptRef.current = "";

        // Push-to-talk: auto-stop after final result
        if (modeRef.current === "push-to-talk") {
          stopRecognition();
        }
      }
    };

    rec.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === "aborted" || event.error === "no-speech") {
        // Harmless — don't treat as error
        if (modeRef.current === "push-to-talk") {
          setVoiceState("idle");
          setListening(false);
        }
        return;
      }
      const msg = event.error === "not-allowed"
        ? "Microphone access denied. Check browser permissions."
        : event.error === "network"
          ? "Speech recognition requires a network connection."
          : `Speech error: ${event.error}`;
      onError?.(msg);
      setVoiceState("idle");
      setListening(false);
    };

    rec.onend = () => {
      // Continuous modes: restart if still in listening state
      if (
        (modeRef.current === "wake-word" || modeRef.current === "always-on") &&
        stateRef.current === "listening"
      ) {
        try {
          rec.start();
        } catch {
          setVoiceState("idle");
          setListening(false);
        }
        return;
      }
      setListening(false);
      if (stateRef.current === "listening") {
        setVoiceState("idle");
      }
    };

    return rec;
  }, [onResult, onFinalResult, onError, onWake, setVoiceState]);

  const startRecognition = useCallback(() => {
    if (!isSupported) return;
    try {
      // Clean up any existing
      if (recognitionRef.current) {
        try { recognitionRef.current.abort(); } catch { /* ok */ }
      }
      const rec = createRecognition();
      recognitionRef.current = rec;
      rec.start();
      setVoiceState("listening");
      setListening(true);
    } catch (err: any) {
      onError?.(err?.message ?? "Failed to start speech recognition");
      setVoiceState("idle");
      setListening(false);
    }
  }, [isSupported, createRecognition, onError, setVoiceState]);

  const stopRecognition = useCallback(() => {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch { /* ok */ }
      recognitionRef.current = null;
    }
    setListening(false);
    if (stateRef.current === "listening") {
      setVoiceState("idle");
    }
  }, [setVoiceState]);

  const startListening = useCallback(() => {
    startRecognition();
  }, [startRecognition]);

  const stopListening = useCallback(() => {
    stopRecognition();
  }, [stopRecognition]);

  // Wake-word mode: start continuous background listening
  useEffect(() => {
    if (mode === "wake-word" && isSupported) {
      startRecognition();
    }
    return () => {
      if (mode === "wake-word") {
        stopRecognition();
      }
    };
  }, [mode, isSupported]); // Only on mode change

  // ── Speech Synthesis ────────────────────────────────────────────

  const speak = useCallback(
    (text: string, voiceIndex?: number) => {
      if (!window.speechSynthesis) return;

      // Cancel any ongoing speech
      window.speechSynthesis.cancel();

      // Sanitize: remove markdown artifacts for speech
      const clean = text
        .replace(/[*_~`#]/g, "")
        .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
        .replace(/\n{2,}/g, ". ")
        .replace(/\n/g, " ")
        .trim();

      if (!clean) return;

      const utterance = new SpeechSynthesisUtterance(clean);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;

      // Assign a voice if requested
      if (voiceIndex !== undefined) {
        const distinct = getDistinctVoices(voiceIndex + 1);
        if (distinct[voiceIndex]) {
          utterance.voice = distinct[voiceIndex];
        }
      } else {
        // Default: pick first English voice with decent quality
        const all = getVoices();
        const en = all.filter((v) => v.lang.startsWith("en"));
        // Prefer voices with "premium" or "enhanced" in the name (macOS/iOS)
        const premium = en.filter((v) =>
          v.name.toLowerCase().includes("premium") ||
          v.name.toLowerCase().includes("enhanced") ||
          v.name.toLowerCase().includes("samantha") ||
          v.name.toLowerCase().includes("daniel"),
        );
        if (premium.length > 0) {
          utterance.voice = premium[0];
        } else if (en.length > 0) {
          utterance.voice = en[0];
        }
      }

      utterance.onstart = () => setVoiceState("speaking");
      utterance.onend = () => setVoiceState("idle");
      utterance.onerror = () => setVoiceState("idle");

      window.speechSynthesis.speak(utterance);
    },
    [setVoiceState],
  );

  const stopSpeaking = useCallback(() => {
    window.speechSynthesis?.cancel();
    if (stateRef.current === "speaking") {
      setVoiceState("idle");
    }
  }, [setVoiceState]);

  // ── Mode ────────────────────────────────────────────────────────

  const setMode = useCallback(
    (m: VoiceMode) => {
      // Stop anything running
      stopRecognition();
      stopSpeaking();
      modeRef.current = m;
      setModeState(m);
      setVoiceState("idle");
    },
    [stopRecognition, stopSpeaking, setVoiceState],
  );

  // ── Cleanup on unmount ──────────────────────────────────────────

  useEffect(() => {
    return () => {
      stopRecognition();
      window.speechSynthesis?.cancel();
    };
  }, [stopRecognition]);

  // ── Update refs when options change ─────────────────────────────

  useEffect(() => {
    wakeWordRef.current = wakeWord.toLowerCase();
  }, [wakeWord]);

  useEffect(() => {
    modeRef.current = mode;
    setModeState(mode);
  }, [mode]);

  return {
    state,
    isSupported,
    listening,
    startListening,
    stopListening,
    speak,
    stopSpeaking,
    setMode,
    voices,
  };
}
