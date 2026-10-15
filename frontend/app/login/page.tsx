"use client";

import { type FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { CartIcon, ChefHatIcon, PantryIcon, SparklesIcon, TimerIcon } from "@/components/icons";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Mode = "login" | "register";

const FEATURES = [
  { Icon: PantryIcon, text: "Sua despensa organizada, com aviso do que vence" },
  { Icon: SparklesIcon, text: "Um chef com IA que sabe o que você tem em casa" },
  { Icon: CartIcon, text: "Lista de compras com só o que falta" },
  { Icon: TimerIcon, text: "Modo cozinha com passo a passo e timers" },
];

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
    if (!restoringSession && user) router.replace("/recipes");
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
      router.replace("/recipes");
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
    <main className="auth">
      <section className="auth-hero">
        <div className="brand">
          <span className="brand-mark">
            <ChefHatIcon size={20} />
          </span>
          <span className="brand-name">Cozinha</span>
        </div>

        <div>
          <h1>O que tem na sua despensa vira o jantar de hoje.</h1>
          <p>
            Cadastre o que você tem, guarde suas receitas e deixe a IA sugerir o que cozinhar —
            e o que comprar.
          </p>
        </div>

        <ul className="auth-features">
          {FEATURES.map(({ Icon, text }) => (
            <li key={text}>
              <Icon />
              {text}
            </li>
          ))}
        </ul>
      </section>

      <section className="auth-form-side">
        <div className="auth-card">
          <h2>{mode === "login" ? "Bem-vindo de volta" : "Crie sua conta"}</h2>
          <p className="muted" style={{ margin: 0 }}>
            {mode === "login" ? "Entre para ver sua cozinha." : "Leva menos de um minuto."}
          </p>

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
            <div className="field">
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
            </div>

            <div className="field">
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
            </div>

            {/* role="alert" faz o leitor de tela anunciar o erro assim que ele
                aparece — sem isso, quem não enxerga a tela não fica sabendo que
                o envio falhou. */}
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}

            <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={submitting}>
              {submitting ? "Enviando…" : mode === "login" ? "Entrar" : "Criar conta"}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}
