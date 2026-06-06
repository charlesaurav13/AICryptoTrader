"use client";
import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(""); setLoading(true);
    const fd = new FormData(e.currentTarget);
    try {
      await api.login(fd.get("username") as string, fd.get("password") as string);
      router.push("/overview");
    } catch {
      setError("Invalid username or password");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center">
      <div className="bg-s1 border border-b1 rounded-2xl p-10 w-[380px] shadow-2xl">
        <div className="text-center mb-8">
          <div className="w-14 h-14 bg-gradient-to-br from-bl to-pu rounded-xl flex items-center justify-center text-3xl mx-auto mb-3">⚡</div>
          <h1 className="text-xl font-bold text-t1">CryptoSwarm</h1>
          <p className="text-sm text-t2 mt-1">AI Trading Dashboard</p>
        </div>
        {error && <div className="bg-red-900/20 border border-re/30 rounded-lg p-3 text-sm text-re mb-4">{error}</div>}
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-t2 uppercase tracking-wider mb-1">Username</label>
            <input name="username" type="text" required autoFocus
              className="w-full bg-s2 border border-b1 rounded-lg px-3 py-2.5 text-sm text-t1 focus:outline-none focus:border-bl transition-colors"
              placeholder="Enter username" />
          </div>
          <div>
            <label className="block text-xs font-medium text-t2 uppercase tracking-wider mb-1">Password</label>
            <input name="password" type="password" required
              className="w-full bg-s2 border border-b1 rounded-lg px-3 py-2.5 text-sm text-t1 focus:outline-none focus:border-bl transition-colors"
              placeholder="Enter password" />
          </div>
          <button type="submit" disabled={loading}
            className="w-full bg-bl hover:bg-blue-600 text-white rounded-lg py-2.5 text-sm font-semibold transition-colors disabled:opacity-50 mt-2">
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>
        <p className="text-center text-xs text-t3 mt-6">Paper Trading Mode · No real funds at risk</p>
      </div>
    </div>
  );
}
