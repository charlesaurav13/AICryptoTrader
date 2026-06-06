"use client";

import { useState, FormEvent, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError]   = useState("");
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
        @keyframes orb-drift {
          0%,100% { transform: translate(0,0); }
          50%      { transform: translate(24px,-32px); }
        }
        @keyframes fade-up {
          from { opacity:0; transform:translateY(16px); }
          to   { opacity:1; transform:translateY(0); }
        }
        @keyframes spin {
          to { transform:rotate(360deg); }
        }
        @keyframes shake {
          0%,100%{ transform:translateX(0); }
          25%    { transform:translateX(-5px); }
          75%    { transform:translateX(5px); }
        }
        .orb-a { animation: orb-drift 12s ease-in-out infinite; }
        .orb-b { animation: orb-drift 16s ease-in-out infinite reverse; }
        .card-in { animation: fade-up 0.45s cubic-bezier(0.16,1,0.3,1) both; }
        .spin    { animation: spin 0.75s linear infinite; }
        .shake   { animation: shake 0.35s ease-in-out; }

        .field {
          width:100%;
          background:rgba(255,255,255,0.04);
          border:1px solid rgba(255,255,255,0.08);
          border-radius:10px;
          padding:10px 14px;
          font-size:14px;
          color:#e8f0fe;
          outline:none;
          transition:border-color .18s, box-shadow .18s;
        }
        .field::placeholder { color:#4a5568; }
        .field:focus {
          border-color:#3d8bff;
          box-shadow:0 0 0 3px rgba(61,139,255,.14);
        }

        .grid-bg {
          background-image:
            linear-gradient(rgba(30,45,66,.2) 1px, transparent 1px),
            linear-gradient(90deg, rgba(30,45,66,.2) 1px, transparent 1px);
          background-size:40px 40px;
        }
      `}</style>

      <div className="grid-bg min-h-screen bg-bg flex items-center justify-center px-4 overflow-hidden relative">

        {/* Soft glow orbs */}
        <div className="orb-a pointer-events-none absolute top-[-160px] left-[-120px] w-[500px] h-[500px] rounded-full"
          style={{background:"radial-gradient(circle,rgba(61,139,255,.08) 0%,transparent 70%)"}}/>
        <div className="orb-b pointer-events-none absolute bottom-[-140px] right-[-100px] w-[420px] h-[420px] rounded-full"
          style={{background:"radial-gradient(circle,rgba(167,139,250,.06) 0%,transparent 70%)"}}/>

        {/* Card */}
        <div
          className={`card-in relative z-10 w-full transition-opacity duration-200 ${mounted?"opacity-100":"opacity-0"}`}
          style={{
            maxWidth: 380,
            background:"rgba(13,20,32,.9)",
            backdropFilter:"blur(20px)",
            WebkitBackdropFilter:"blur(20px)",
            border:"1px solid rgba(255,255,255,.07)",
            borderRadius:18,
            boxShadow:"0 24px 80px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.04)",
            padding:"32px 28px 28px",
          }}
        >
          {/* Header */}
          <div className="flex flex-col items-center text-center mb-7">
            {/* Icon */}
            <div className="w-12 h-12 rounded-[14px] flex items-center justify-center mb-4"
              style={{
                background:"linear-gradient(140deg,#3d8bff,#a78bfa)",
                boxShadow:"0 6px 24px rgba(61,139,255,.28)",
              }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                <path d="M2 12h3l3-7 4 14 3-9 2 4h5"
                  stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>

            <h1 className="text-[17px] font-bold text-t1 leading-none">CryptoSwarm</h1>
            <p className="text-[13px] text-t2 mt-1.5">AI Trading Dashboard</p>

            {/* Pill */}
            <div className="flex items-center gap-1.5 mt-3 px-3 py-1 rounded-full text-[11px] font-medium text-t2"
              style={{background:"rgba(0,208,132,.07)",border:"1px solid rgba(0,208,132,.15)"}}>
              <span className="w-1.5 h-1.5 rounded-full bg-gr" style={{boxShadow:"0 0 5px #00d084"}}/>
              Live · Paper Mode
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="shake flex items-center gap-2 rounded-lg px-3 py-2.5 mb-4 text-[13px] text-re"
              style={{background:"rgba(255,71,87,.07)",border:"1px solid rgba(255,71,87,.18)"}}>
              <svg className="shrink-0" width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="7" r="6" stroke="#ff4757" strokeWidth="1.4"/>
                <path d="M7 4.5V7.5M7 9.5h.01" stroke="#ff4757" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={submit} className="space-y-3">
            <div>
              <label className="block text-[11px] font-semibold tracking-widest uppercase text-t2 mb-1.5">
                Username
              </label>
              <input name="username" type="text" required autoFocus
                autoComplete="username" placeholder="your-username" className="field"/>
            </div>

            <div>
              <label className="block text-[11px] font-semibold tracking-widest uppercase text-t2 mb-1.5">
                Password
              </label>
              <input name="password" type="password" required
                autoComplete="current-password" placeholder="••••••••" className="field"/>
            </div>

            <button type="submit" disabled={loading}
              className="w-full py-2.5 rounded-[10px] text-sm font-semibold text-white mt-1 transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                background:"linear-gradient(135deg,#3d8bff,#2563eb)",
                boxShadow:loading?"none":"0 3px 16px rgba(61,139,255,.3)",
              }}>
              {loading
                ? <span className="flex items-center justify-center gap-2">
                    <svg className="spin" width="14" height="14" viewBox="0 0 14 14" fill="none">
                      <circle cx="7" cy="7" r="5.5" stroke="white" strokeWidth="2" strokeOpacity=".25"/>
                      <path d="M12.5 7A5.5 5.5 0 0 0 7 1.5" stroke="white" strokeWidth="2" strokeLinecap="round"/>
                    </svg>
                    Signing in…
                  </span>
                : "Sign In →"
              }
            </button>
          </form>

          <p className="text-center text-[11px] text-t3 mt-5">
            Paper trading · No real funds at risk
          </p>
        </div>
      </div>
    </>
  );
}
