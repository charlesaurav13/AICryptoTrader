"use client";

import { useState, FormEvent, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setLoading(true);
    const fd = new FormData(e.currentTarget);
    try {
      await api.login(fd.get("username") as string, fd.get("password") as string);
      router.push("/overview");
    } catch {
      setError("Invalid credentials. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <style>{`
        @keyframes float-orb {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33%       { transform: translate(30px, -40px) scale(1.05); }
          66%       { transform: translate(-20px, 20px) scale(0.97); }
        }
        @keyframes fade-up {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          20%      { transform: translateX(-6px); }
          40%      { transform: translateX(6px); }
          60%      { transform: translateX(-4px); }
          80%      { transform: translateX(4px); }
        }
        .orb-1 { animation: float-orb 14s ease-in-out infinite; }
        .orb-2 { animation: float-orb 18s ease-in-out infinite reverse; }
        .orb-3 { animation: float-orb 10s ease-in-out infinite 4s; }
        .card-enter { animation: fade-up 0.55s cubic-bezier(0.16, 1, 0.3, 1) both; }
        .spinner    { animation: spin 0.75s linear infinite; }
        .shake      { animation: shake 0.4s ease-in-out; }
        .input-field {
          width: 100%;
          background: rgba(17, 25, 39, 0.7);
          border: 1px solid rgba(36, 51, 80, 0.9);
          border-radius: 12px;
          padding: 12px 16px;
          font-size: 14px;
          color: #e8f0fe;
          transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
          outline: none;
        }
        .input-field::placeholder { color: #4a5568; }
        .input-field:focus {
          border-color: #3d8bff;
          background: rgba(17, 25, 39, 0.95);
          box-shadow: 0 0 0 3px rgba(61, 139, 255, 0.12);
        }
        .sign-in-btn {
          width: 100%;
          border: none;
          border-radius: 12px;
          padding: 13px;
          font-size: 14px;
          font-weight: 600;
          color: white;
          cursor: pointer;
          background: linear-gradient(135deg, #3d8bff 0%, #2563eb 100%);
          box-shadow: 0 4px 24px rgba(61, 139, 255, 0.28);
          transition: opacity 0.2s, transform 0.15s, box-shadow 0.2s;
        }
        .sign-in-btn:hover:not(:disabled) {
          opacity: 0.92;
          transform: translateY(-1px);
          box-shadow: 0 6px 28px rgba(61, 139, 255, 0.38);
        }
        .sign-in-btn:active:not(:disabled) { transform: translateY(0); }
        .sign-in-btn:disabled {
          opacity: 0.55;
          cursor: not-allowed;
          box-shadow: none;
        }
        .grid-overlay {
          background-image:
            linear-gradient(rgba(30, 45, 66, 0.25) 1px, transparent 1px),
            linear-gradient(90deg, rgba(30, 45, 66, 0.25) 1px, transparent 1px);
          background-size: 44px 44px;
        }
      `}</style>

      {/* Page */}
      <div className="min-h-screen bg-bg grid-overlay relative flex items-center justify-center overflow-hidden px-4">

        {/* Ambient glow orbs */}
        <div className="orb-1 pointer-events-none absolute -top-40 -left-40 w-[700px] h-[700px] rounded-full"
          style={{ background: "radial-gradient(circle, rgba(61,139,255,0.09) 0%, transparent 65%)" }} />
        <div className="orb-2 pointer-events-none absolute -bottom-48 -right-32 w-[600px] h-[600px] rounded-full"
          style={{ background: "radial-gradient(circle, rgba(167,139,250,0.07) 0%, transparent 65%)" }} />
        <div className="orb-3 pointer-events-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] rounded-full"
          style={{ background: "radial-gradient(circle, rgba(0,208,132,0.03) 0%, transparent 70%)" }} />

        {/* Card */}
        <div
          className={`card-enter relative z-10 w-full max-w-[360px] transition-opacity duration-300 ${mounted ? "opacity-100" : "opacity-0"}`}
          style={{
            background: "rgba(13, 20, 32, 0.88)",
            backdropFilter: "blur(24px)",
            WebkitBackdropFilter: "blur(24px)",
            border: "1px solid rgba(36, 51, 80, 0.55)",
            borderRadius: "22px",
            boxShadow: "0 40px 100px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.03)",
            padding: "40px 36px 36px",
          }}
        >
          {/* Status pill */}
          <div className="flex justify-end mb-6">
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-medium text-t2"
              style={{ background: "rgba(0,208,132,0.08)", border: "1px solid rgba(0,208,132,0.15)" }}>
              <span className="w-1.5 h-1.5 rounded-full bg-gr" style={{ boxShadow: "0 0 5px #00d084" }} />
              Live · Paper Mode
            </div>
          </div>

          {/* Logo mark */}
          <div className="flex flex-col items-center mb-9">
            <div
              className="w-[60px] h-[60px] rounded-[18px] flex items-center justify-center mb-4"
              style={{
                background: "linear-gradient(140deg, #3d8bff 0%, #a78bfa 100%)",
                boxShadow: "0 8px 32px rgba(61,139,255,0.3)",
              }}
            >
              {/* Waveform / signal icon */}
              <svg width="30" height="30" viewBox="0 0 30 30" fill="none">
                <path d="M3 15h4l3-8 4 16 3-11 3 6 3-3h4" stroke="white" strokeWidth="2.2"
                  strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <h1 className="text-[22px] font-bold text-t1 tracking-tight">CryptoSwarm</h1>
            <p className="text-sm text-t2 mt-1.5">AI Trading Dashboard</p>
          </div>

          {/* Error message */}
          {error && (
            <div
              className="shake flex items-start gap-2.5 rounded-xl px-3.5 py-3 mb-5 text-[13px] text-re"
              style={{ background: "rgba(255,71,87,0.07)", border: "1px solid rgba(255,71,87,0.18)" }}
            >
              <svg className="shrink-0 mt-0.5" width="15" height="15" viewBox="0 0 15 15" fill="none">
                <circle cx="7.5" cy="7.5" r="6.5" stroke="#ff4757" strokeWidth="1.4" />
                <path d="M7.5 4.5V8M7.5 10.5h.01" stroke="#ff4757" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={submit}>
            <div className="space-y-4">
              {/* Username */}
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-t2 mb-2">
                  Username
                </label>
                <input
                  name="username"
                  type="text"
                  required
                  autoFocus
                  autoComplete="username"
                  placeholder="your-username"
                  className="input-field"
                />
              </div>

              {/* Password */}
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-t2 mb-2">
                  Password
                </label>
                <input
                  name="password"
                  type="password"
                  required
                  autoComplete="current-password"
                  placeholder="••••••••"
                  className="input-field"
                />
              </div>

              {/* Submit */}
              <div className="pt-1">
                <button type="submit" disabled={loading} className="sign-in-btn">
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <svg className="spinner" width="15" height="15" viewBox="0 0 15 15" fill="none">
                        <circle cx="7.5" cy="7.5" r="5.5" stroke="white" strokeWidth="2" strokeOpacity="0.25" />
                        <path d="M13 7.5a5.5 5.5 0 0 0-5.5-5.5" stroke="white" strokeWidth="2" strokeLinecap="round" />
                      </svg>
                      Signing in…
                    </span>
                  ) : "Sign In →"}
                </button>
              </div>
            </div>
          </form>

          {/* Footer */}
          <p className="text-center text-[11px] text-t3 mt-7 leading-relaxed">
            Paper trading only · No real funds at risk
          </p>
        </div>
      </div>
    </>
  );
}
