/**
 * Vello Design System
 *
 * Single source of truth for all visual tokens. Point Claude Design at this file.
 *
 * AESTHETIC LANGUAGE
 * ──────────────────
 * Pure black foundation. Monochromatic — no accent hues. Everything is expressed
 * through luminance contrast (white on black) and subtle translucency. The goal is
 * a tool that feels like a terminal crossed with a premium consumer app: sharp,
 * dense, purposeful. No decorative gradients, no colorful badges, no rounded
 * happy corners. Panels are barely-visible-against-black surfaces. Text has two
 * states: fully visible (white) or recessive (muted grey). Interactions are felt
 * through micro-motion (lift on hover, compress on press) not color change.
 *
 * MOTION PHILOSOPHY
 * ─────────────────
 * Transitions are fast (150ms) and eased. No bouncy spring physics. Elements
 * move in one axis at a time. The only exception is the primary button glow,
 * which uses a soft box-shadow bloom to communicate energy without color.
 *
 * VELLO-SPECIFIC NOTES
 * ────────────────────
 * Vello is a proactive life agent — it surfaces behavioral patterns, flags gaps,
 * and nudges the user. The UI must feel calm and non-intrusive: dense information
 * without visual noise. Signal cards and insight panels use the same surface tokens
 * as Kortex so both apps feel like one system.
 */

// ── Color tokens ──────────────────────────────────────────────────────────────

export const colors = {
  // Backgrounds — three levels of depth
  bg:           "#000000",   // page root — true black
  surface:      "#0a0a0a",   // panels, cards, inputs — barely-lifted black
  surfaceHover: "#0f0f0f",   // hover state for interactive surfaces
  elevated:     "#141414",   // dropdowns, tooltips — one level above surface

  // Borders
  border:       "#1c1c1c",   // default divider / panel outline
  borderSubtle: "#111111",   // very faint separator
  borderStrong: "#2a2a2a",   // active/focused border
  borderHover:  "rgba(255,255,255,0.10)", // border on surface hover

  // Text
  primary:  "#f5f5f5",       // main readable text
  muted:    "#505050",       // secondary labels, timestamps, nav links at rest
  faint:    "#2a2a2a",       // barely-visible text (decorative)
  inverse:  "#000000",       // text on white backgrounds (btn-primary label)

  // Semantic
  warning:  "#f59e0b",       // amber — caution states, gap alerts
  error:    "#ef4444",       // red — destructive actions, errors
  success:  "#22c55e",       // green — confirmation, positive signals

  // White channel (used for btn-primary glow and highlights)
  white:    "#ffffff",
} as const;

// ── Typography ────────────────────────────────────────────────────────────────

export const typography = {
  fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",

  // Brand wordmark
  wordmark: {
    fontSize:    "13px",
    fontWeight:  800,
    letterSpacing: "0.3em",
    color:       colors.white,
  },

  // Scale (px values — convert to rem if needed)
  size: {
    xs:   "11px",   // footnotes, sub-labels
    sm:   "12px",   // nav links, timestamps, badges
    base: "13px",   // body text, button labels
    md:   "14px",   // paragraph text, form labels
    lg:   "16px",   // section headings
    xl:   "20px",   // page headings
    "2xl": "22px",  // modal/hero headings
    "3xl": "28px",  // stats, large numbers
  },

  weight: {
    normal:    400,
    semibold:  600,
    bold:      700,
    extrabold: 800,
  },

  lineHeight: {
    tight:  1.3,
    normal: 1.6,
    loose:  1.8,
  },
} as const;

// ── Spacing ───────────────────────────────────────────────────────────────────
// Base unit: 4px. All spacing is multiples of 4.

export const spacing = {
  "1":  "4px",
  "2":  "8px",
  "3":  "12px",
  "4":  "16px",
  "5":  "20px",
  "6":  "24px",
  "8":  "32px",
  "10": "40px",
  "12": "48px",
  "16": "64px",
} as const;

// ── Border radius ─────────────────────────────────────────────────────────────

export const radius = {
  sm:   "8px",     // small chips, badges
  md:   "12px",    // input fields
  lg:   "16px",    // panels, cards
  xl:   "20px",    // modal containers
  full: "9999px",  // pill buttons, avatars
} as const;

// ── Shadows ───────────────────────────────────────────────────────────────────

export const shadows = {
  // Primary button glow — white light bloom
  btnPrimaryRest:  "0 1px 0 rgba(255,255,255,0.08), 0 4px 20px rgba(255,255,255,0.06)",
  btnPrimaryHover: "0 6px 32px rgba(255,255,255,0.20), 0 0 0 1px rgba(255,255,255,0.18)",
  btnPrimaryPress: "0 1px 8px rgba(255,255,255,0.08)",

  // Panel / card
  panel:       "none",                                    // panels have no shadow — only border
  panelFocus:  "0 0 0 1px rgba(255,255,255,0.10)",       // subtle ring on focus
} as const;

// ── Transitions ───────────────────────────────────────────────────────────────

export const transitions = {
  fast:   "0.15s ease",   // colors, borders, opacity
  medium: "0.20s ease",   // border-color, background
  slow:   "0.30s ease",   // layout shifts
} as const;

// ── Component tokens ──────────────────────────────────────────────────────────
// Semantic references into the raw tokens above. Use these in components.

export const components = {
  nav: {
    height:     "56px",
    background: colors.bg,
    border:     `1px solid ${colors.border}`,
    padding:    "0 24px",
    linkColor:  colors.muted,
    linkHover:  colors.primary,
    transition: transitions.fast,
  },

  panel: {
    background:    colors.surface,
    border:        `1px solid ${colors.border}`,
    borderRadius:  radius.lg,
    borderHover:   colors.borderHover,
    transition:    transitions.medium,
  },

  // Signal cards — used heavily in Vello for surfacing patterns and nudges
  signalCard: {
    background:    colors.surface,
    border:        `1px solid ${colors.border}`,
    borderRadius:  radius.md,
    padding:       "16px",
    hoverBorder:   colors.borderHover,
    transition:    transitions.fast,
  },

  // Gap alert — used in gap detection panels
  gapCard: {
    background:    "rgba(245,158,11,0.04)",
    border:        `1px solid rgba(245,158,11,0.12)`,
    borderRadius:  radius.md,
    padding:       "14px 16px",
  },

  input: {
    background:    colors.surface,
    border:        `1px solid ${colors.border}`,
    borderRadius:  radius.md,
    color:         colors.primary,
    placeholder:   colors.muted,
    padding:       "10px 14px",
    fontSize:      typography.size.md,
    focusBorder:   colors.borderStrong,
    transition:    transitions.fast,
  },

  btnPrimary: {
    background:    colors.white,
    color:         colors.inverse,
    fontWeight:    typography.weight.bold,
    borderRadius:  radius.full,
    padding:       "11px 26px",
    fontSize:      typography.size.base,
    shadowRest:    shadows.btnPrimaryRest,
    shadowHover:   shadows.btnPrimaryHover,
    shadowPress:   shadows.btnPrimaryPress,
    hoverTranslateY: "-1px",
  },

  btnGhost: {
    background:    "transparent",
    color:         colors.primary,
    fontWeight:    typography.weight.semibold,
    borderRadius:  radius.full,
    padding:       "10px 24px",
    fontSize:      typography.size.base,
    border:        "1px solid rgba(255,255,255,0.12)",
    borderHover:   "1px solid rgba(255,255,255,0.25)",
    bgHover:       "rgba(255,255,255,0.05)",
  },

  scrollbar: {
    width:       "6px",
    track:       "transparent",
    thumb:       colors.border,
    thumbHover:  colors.borderStrong,
    borderRadius: radius.full,
  },
} as const;

// ── Semantic surface patterns ─────────────────────────────────────────────────
// Common inline-style objects for copy-paste into components.

export const surfaces = {
  // Standard panel — use as the base for cards, sections
  panel: {
    background:   components.panel.background,
    border:       components.panel.border,
    borderRadius: components.panel.borderRadius,
  } as React.CSSProperties,

  // Signal card — Vello-specific surface for proactive insight cards
  signal: {
    background:   components.signalCard.background,
    border:       components.signalCard.border,
    borderRadius: components.signalCard.borderRadius,
    padding:      components.signalCard.padding,
  } as React.CSSProperties,

  // Gap alert (amber tint) — behavioral gap warnings
  gap: {
    background:   components.gapCard.background,
    border:       components.gapCard.border,
    borderRadius: components.gapCard.borderRadius,
    padding:      components.gapCard.padding,
  } as React.CSSProperties,

  // Warning callout (amber tint)
  warning: {
    background:   "rgba(245,158,11,0.06)",
    border:       "1px solid rgba(245,158,11,0.15)",
    borderRadius: radius.md,
  } as React.CSSProperties,

  // Error callout
  error: {
    background:   "rgba(239,68,68,0.06)",
    border:       "1px solid rgba(239,68,68,0.15)",
    borderRadius: radius.md,
  } as React.CSSProperties,

  // Success callout
  success: {
    background:   "rgba(34,197,94,0.06)",
    border:       "1px solid rgba(34,197,94,0.15)",
    borderRadius: radius.md,
  } as React.CSSProperties,
} as const;

// Add React import for CSSProperties typing (tree-shaken in production)
import type React from "react";
