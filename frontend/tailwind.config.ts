import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg:  "#090e14", s1: "#0d1420", s2: "#111927", s3: "#172033",
        b1:  "#1e2d42", b2: "#243350",
        t1:  "#e8f0fe", t2: "#94a3b8", t3: "#4a5568",
        gr:  "#00d084", re: "#ff4757", bl: "#3d8bff",
        ye:  "#ffc832", pu: "#a78bfa", or: "#ff8c42",
      },
    },
  },
  plugins: [],
} satisfies Config;
