/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg:      "#000000",
        surface: "#0a0a0a",
        border:  "#1c1c1c",
        primary: "#f5f5f5",
        muted:   "#505050",
        cyan:    "#ffffff",
        warning: "#f59e0b",
        error:   "#ef4444",
        success: "#22c55e",
      },
    },
  },
  plugins: [],
};
