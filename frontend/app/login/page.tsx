"use client";

import { type FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Mode = "login" | "register";

export default function LoginPage() {
  const { user, loading: restoringSession, login, register } = useAuth();
  const router = useRouter();

  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Quem já tem sessão não precisa ver a tela de login.
  useEffect(() => {
    if (!restoringSession && user) router.replace("/chat");
  }, [user, restoringSession, router]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      if (mode === "login") {
        await login(username, password);
      } else {
        await register(username, password);
      }
      router.replace("/chat");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Algo deu errado. Tente novamente.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  function switchMode(next: Mode) {
    setMode(next);
    // O erro pertence à tentativa anterior; mantê-lo visível depois de trocar
    // de aba faz o usuário achar que o problema é do formulário novo.
    setError(null);
  }

  if (restoringSession) {
    return (
      <main className="centered">
        <p className="muted">Carregando…</p>
      </main>
    );
  }

  return (
    <main className="centered">
      <div className="card">
        <h1>Chat com IA</h1>

        <div className="tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "login"}
            className={mode === "login" ? "tab active" : "tab"}
            onClick={() => switchMode("login")}
          >
            Entrar
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "register"}
            className={mode === "register" ? "tab active" : "tab"}
            onClick={() => switchMode("register")}
          >
            Criar conta
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <label htmlFor="username">Usuário</label>
          <input
            id="username"
            name="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            required
            minLength={3}
            maxLength={50}
            disabled={submitting}
          />

          <label htmlFor="password">Senha</label>
          <input
            id="password"
            name="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
            minLength={mode === "register" ? 8 : undefined}
            maxLength={128}
            disabled={submitting}
          />
          {mode === "register" && <p className="hint">Ao menos 8 caracteres.</p>}

          {/* role="alert" faz o leitor de tela anunciar o erro assim que ele
              aparece — sem isso, quem não enxerga a tela não fica sabendo que
              o envio falhou. */}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="primary" disabled={submitting}>
            {submitting ? "Enviando…" : mode === "login" ? "Entrar" : "Criar conta"}
          </button>
        </form>
      </div>
    </main>
  );
}
