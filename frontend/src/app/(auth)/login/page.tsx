"use client";

import { useState, FormEvent, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

/* ── tiny reusable stat card for the left panel ─────────────────── */
function StatCard({ label, value, change, up }: { label: string; value: string; change: string; up: boolean }) {
  return (
    <div style={{
      background: "rgba(255,255,255,0.05)",
      border: "1px solid rgba(255,255,255,0.08)",
      borderRadius: 12,
      padding: "12px 16px",
      backdropFilter: "blur(8px)",
    }}>
      <p style={{ fontSize: 11, color: "#64748b", marginBottom: 4, letterSpacing: "0.04em" }}>{label}</p>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontSize: 18, fontWeight: 700, color: "#f1f5f9" }}>{value}</span>
        <span style={{ fontSize: 12, fontWeight: 500, color: up ? "#00d084" : "#ff4757" }}>{change}</span>
      </div>
    </div>
  );
}

/* ── main page ───────────────────────────────────────────────────── */
export default function LoginPage() {
  const router = useRouter();
  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);
  const [showPw, setShowPw]   = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(""); setLoading(true);
    const fd = new FormData(e.currentTarget);
    try {
      await api.login(fd.get("username") as string, fd.get("password") as string);
      router.push("/overview");
    } catch {
      setError("Invalid username or password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <style>{`
        * { box-sizing: border-box; margin: 0; padding: 0; }

        @keyframes slide-in {
          from { opacity: 0; transform: translateX(20px); }
          to   { opacity: 1; transform: translateX(0); }
        }
        @keyframes fade-in {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50%       { transform: translateY(-8px); }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes shake {
          0%,100% { transform: translateX(0); }
          25%     { transform: translateX(-4px); }
          75%     { transform: translateX(4px); }
        }

        .page-enter { animation: fade-in 0.3s ease both; }
        .form-enter { animation: slide-in 0.45s cubic-bezier(0.16,1,0.3,1) both 0.1s; }
        .float-1    { animation: float 6s ease-in-out infinite; }
        .float-2    { animation: float 8s ease-in-out infinite 1.5s; }
        .float-3    { animation: float 7s ease-in-out infinite 3s; }
        .spinner    { animation: spin 0.7s linear infinite; }
        .shake      { animation: shake 0.35s ease-in-out; }

        .inp {
          width: 100%;
          background: #0d1420;
          border: 1px solid #1e2d42;
          border-radius: 8px;
          padding: 11px 14px;
          font-size: 14px;
          color: #e2e8f0;
          outline: none;
          transition: border-color 0.15s, box-shadow 0.15s;
        }
        .inp::placeholder { color: #334155; }
        .inp:focus {
          border-color: #3d8bff;
          box-shadow: 0 0 0 3px rgba(61,139,255,0.12);
        }

        .btn-primary {
          width: 100%;
          padding: 11px;
          border: none;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 600;
          color: #fff;
          cursor: pointer;
          background: #3d8bff;
          transition: background 0.15s, transform 0.1s, box-shadow 0.15s;
          box-shadow: 0 1px 3px rgba(0,0,0,0.3), 0 4px 16px rgba(61,139,255,0.25);
        }
        .btn-primary:hover:not(:disabled) {
          background: #2979f5;
          box-shadow: 0 1px 3px rgba(0,0,0,0.3), 0 6px 20px rgba(61,139,255,0.35);
        }
        .btn-primary:active:not(:disabled) { transform: scale(0.99); }
        .btn-primary:disabled { opacity: 0.55; cursor: not-allowed; }

        .pw-toggle {
          position: absolute;
          right: 12px;
          top: 50%;
          transform: translateY(-50%);
          background: none;
          border: none;
          cursor: pointer;
          color: #475569;
          padding: 4px;
          display: flex;
          align-items: center;
          transition: color 0.15s;
        }
        .pw-toggle:hover { color: #94a3b8; }

        /* left panel grid */
        .grid-left {
          background-image:
            linear-gradient(rgba(30,45,66,0.3) 1px, transparent 1px),
            linear-gradient(90deg, rgba(30,45,66,0.3) 1px, transparent 1px);
          background-size: 36px 36px;
        }
      `}</style>

      <div
        className={`page-enter ${mounted ? "" : "opacity-0"}`}
        style={{ display: "flex", minHeight: "100vh", background: "#090e14" }}
      >

        {/* ── LEFT PANEL — brand + visual ──────────────────────────── */}
        <div
          className="grid-left"
          style={{
            flex: "0 0 52%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            padding: "40px 48px",
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* glow blob */}
          <div style={{
            position: "absolute", inset: 0, pointerEvents: "none",
            background: "radial-gradient(ellipse 60% 50% at 30% 60%, rgba(61,139,255,0.07) 0%, transparent 70%)",
          }}/>

          {/* wordmark */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, position: "relative" }}>
            <div style={{
              width: 34, height: 34, borderRadius: 9,
              background: "linear-gradient(140deg,#3d8bff,#a78bfa)",
              display: "flex", alignItems: "center", justifyContent: "center",
              boxShadow: "0 4px 16px rgba(61,139,255,0.3)",
            }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <path d="M2 12h3l3-7 4 14 3-9 2 4h5" stroke="white" strokeWidth="2.2"
                  strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <span style={{ fontWeight: 700, fontSize: 15, color: "#f1f5f9", letterSpacing: "-0.01em" }}>
              CryptoSwarm
            </span>
          </div>

          {/* hero text */}
          <div style={{ position: "relative" }}>
            <div style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              background: "rgba(0,208,132,0.08)",
              border: "1px solid rgba(0,208,132,0.18)",
              borderRadius: 20, padding: "4px 12px",
              marginBottom: 20,
            }}>
              <span style={{
                width: 6, height: 6, borderRadius: "50%",
                background: "#00d084", boxShadow: "0 0 6px #00d084",
                display: "inline-block",
              }}/>
              <span style={{ fontSize: 11, fontWeight: 600, color: "#00d084", letterSpacing: "0.05em" }}>
                LIVE · PAPER MODE
              </span>
            </div>

            <h1 style={{
              fontSize: 36, fontWeight: 800, color: "#f1f5f9",
              lineHeight: 1.15, letterSpacing: "-0.03em", marginBottom: 14,
            }}>
              Multi-agent<br/>AI trading,<br/>
              <span style={{ color: "#3d8bff" }}>on autopilot.</span>
            </h1>

            <p style={{ fontSize: 14, color: "#64748b", lineHeight: 1.65, maxWidth: 320 }}>
              Five AI agents analyze the market from independent angles
              and synthesize decisions in real time.
            </p>
          </div>

          {/* floating stat cards */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10, position: "relative" }}>
            <div className="float-1"><StatCard label="BTC / USDT" value="$67,420" change="+2.4%" up={true}/></div>
            <div className="float-2"><StatCard label="Portfolio P&L (today)" value="+$1,284" change="+3.8%" up={true}/></div>
            <div className="float-3"><StatCard label="Win Rate (7d)" value="68%" change="+5% vs avg" up={true}/></div>

            <p style={{ fontSize: 11, color: "#334155", marginTop: 4 }}>
              Simulated data · No real funds at risk
            </p>
          </div>
        </div>

        {/* ── RIGHT PANEL — form ───────────────────────────────────── */}
        <div
          className="form-enter"
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "48px 40px",
            background: "#0b1118",
            borderLeft: "1px solid #1a2535",
          }}
        >
          <div style={{ width: "100%", maxWidth: 340 }}>

            {/* heading */}
            <div style={{ marginBottom: 32 }}>
              <h2 style={{ fontSize: 22, fontWeight: 700, color: "#f1f5f9", letterSpacing: "-0.02em", marginBottom: 6 }}>
                Welcome back
              </h2>
              <p style={{ fontSize: 13, color: "#475569" }}>
                Sign in to your dashboard
              </p>
            </div>

            {/* error */}
            {error && (
              <div className="shake" style={{
                display: "flex", alignItems: "center", gap: 8,
                background: "rgba(255,71,87,0.07)",
                border: "1px solid rgba(255,71,87,0.2)",
                borderRadius: 8, padding: "10px 12px",
                marginBottom: 20, fontSize: 13, color: "#ff4757",
              }}>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0 }}>
                  <circle cx="7" cy="7" r="6" stroke="#ff4757" strokeWidth="1.4"/>
                  <path d="M7 4v3M7 9.5h.01" stroke="#ff4757" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
                {error}
              </div>
            )}

            {/* form */}
            <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>

              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 500, color: "#64748b", marginBottom: 6 }}>
                  Username
                </label>
                <input className="inp" name="username" type="text" required
                  autoFocus autoComplete="username" placeholder="your-username"/>
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 500, color: "#64748b", marginBottom: 6 }}>
                  Password
                </label>
                <div style={{ position: "relative" }}>
                  <input className="inp" name="password" type={showPw ? "text" : "password"}
                    required autoComplete="current-password" placeholder="••••••••"
                    style={{ paddingRight: 42 }}/>
                  <button type="button" className="pw-toggle" onClick={() => setShowPw(p => !p)}
                    aria-label={showPw ? "Hide password" : "Show password"}>
                    {showPw
                      ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                          <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                          <line x1="1" y1="1" x2="23" y2="23"/>
                        </svg>
                      : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                          <circle cx="12" cy="12" r="3"/>
                        </svg>
                    }
                  </button>
                </div>
              </div>

              <button type="submit" disabled={loading} className="btn-primary" style={{ marginTop: 4 }}>
                {loading
                  ? <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                      <svg className="spinner" width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <circle cx="7" cy="7" r="5.5" stroke="white" strokeWidth="2" strokeOpacity="0.25"/>
                        <path d="M12.5 7A5.5 5.5 0 0 0 7 1.5" stroke="white" strokeWidth="2" strokeLinecap="round"/>
                      </svg>
                      Signing in…
                    </span>
                  : "Sign in"
                }
              </button>
            </form>

            {/* footer */}
            <p style={{ marginTop: 28, fontSize: 12, color: "#334155", textAlign: "center", lineHeight: 1.6 }}>
              Paper trading only &mdash; no real funds at risk
            </p>

          </div>
        </div>
      </div>
    </>
  );
}
