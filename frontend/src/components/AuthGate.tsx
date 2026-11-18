"use client";

import { createContext, FormEvent, ReactNode, useContext, useEffect, useState } from "react";
import { KeyRound, Loader2, LogOut, UserRound } from "lucide-react";
import { api } from "@/lib/api";
import type { AuthUser } from "@/types/api";

type AuthContextValue = {
  authEnabled: boolean;
  user: AuthUser | null;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue>({
  authEnabled: false,
  user: null,
  logout: () => undefined,
});

export function useClipGenAuth() {
  return useContext(AuthContext);
}

export function AuthGate({ children }: { children: ReactNode }) {
  const [authEnabled, setAuthEnabled] = useState<boolean | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [displayName, setDisplayName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    api.getAuthConfig()
      .then(async (config) => {
        if (!mounted) return;
        setAuthEnabled(config.enabled);
        if (!config.enabled) return;
        try {
          const currentUser = await api.getCurrentUser();
          if (mounted) setUser(currentUser);
        } catch {
          // A missing/expired local token simply opens the sign-in form.
        }
      })
      .catch(() => {
        if (mounted) setAuthEnabled(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const logout = () => {
    api.logout();
    setUser(null);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const session = mode === "login"
        ? await api.login(username, password)
        : await api.register(displayName, username, password);
      setUser(session.user);
      setPassword("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Autentikasi gagal");
    } finally {
      setSubmitting(false);
    }
  };

  if (authEnabled === null) {
    return <div className="min-h-screen" aria-busy="true" />;
  }

  if (authEnabled && !user) {
    return (
      <main className="mx-auto flex min-h-screen max-w-md items-center p-5">
        <section className="clipgen-panel w-full overflow-hidden">
          <div className="border-b border-slate-800 bg-slate-950 p-6 text-white">
            <div className="flex h-11 w-11 items-center justify-center border border-cyan-300/50 bg-cyan-300/10 text-cyan-200">
              <KeyRound className="h-5 w-5" />
            </div>
            <h1 className="mt-5 text-2xl font-semibold">ClipGen</h1>
            <p className="mt-1 text-sm text-slate-300">Workspace video lokal</p>
          </div>
          <form className="space-y-4 p-5" onSubmit={submit}>
            {mode === "register" && (
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">
                Nama tampilan
                <input
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  required
                  className="mt-1.5 w-full border border-slate-300 bg-white px-3 py-2.5 outline-none focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-950"
                />
              </label>
            )}
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">
              Username
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                required
                className="mt-1.5 w-full border border-slate-300 bg-white px-3 py-2.5 outline-none focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-950"
              />
            </label>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                minLength={mode === "register" ? 10 : 1}
                required
                className="mt-1.5 w-full border border-slate-300 bg-white px-3 py-2.5 outline-none focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-950"
              />
            </label>
            {error && <p className="cg-alert">{error}</p>}
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex w-full items-center justify-center gap-2 bg-brand-strong hover:bg-brand px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {mode === "login" ? "Masuk" : "Buat akun"}
            </button>
            <button
              type="button"
              onClick={() => {
                setMode((current) => current === "login" ? "register" : "login");
                setError(null);
              }}
              className="w-full text-sm text-slate-600 hover:text-slate-950 dark:text-slate-300 dark:hover:text-cyan-200"
            >
              {mode === "login" ? "Buat akun lokal" : "Saya sudah punya akun"}
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <AuthContext.Provider value={{ authEnabled, user, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function AccountControl() {
  const { authEnabled, user, logout } = useClipGenAuth();
  if (!authEnabled || !user) return null;
  return (
    <div className="flex min-h-10 items-center gap-2 rounded-lg border border-line-strong bg-canvas px-3 text-sm text-ink">
      <UserRound className="h-4 w-4 text-accent" />
      <span className="min-w-0 flex-1 truncate">{user.display_name}</span>
      <button type="button" onClick={logout} className="p-2 hover:text-rose-600" title="Keluar">
        <LogOut className="h-4 w-4" />
      </button>
    </div>
  );
}
