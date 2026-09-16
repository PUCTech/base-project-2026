"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export default function ChatPage() {
  const { user, token, loading: restoringSession, logout } = useAuth();
  const router = useRouter();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const endOfMessagesRef = useRef<HTMLDivElement>(null);

  // Rota protegida: sem sessão, volta para o login.
  //
  // Isto é conveniência de navegação, não segurança. A proteção real está no
  // backend, que exige o JWT em toda rota — um usuário que force a URL do chat
  // não consegue nada sem token válido.
  useEffect(() => {
    if (!restoringSession && !user) router.replace("/login");
  }, [user, restoringSession, router]);

  // Mantém a última mensagem visível conforme a conversa cresce.
  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    const question = draft.trim();
    if (!question || !token || sending) return;

    const outgoing: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: question,
    };

    // A pergunta aparece na hora, antes da resposta chegar. Esperar o servidor
    // para só então mostrar o que o usuário acabou de digitar faz a interface
    // parecer travada.
    setMessages((current) => [...current, outgoing]);
    setDraft("");
    setError(null);
    setSending(true);

    try {
      const { reply } = await api.sendMessage(token, question);
      setMessages((current) => [
        ...current,
        { id: `assistant-${Date.now()}`, role: "assistant", content: reply },
      ]);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        // Token expirou durante a conversa.
        logout();
        return;
      }

      setError(
        caught instanceof ApiError
          ? caught.message
          : "Não foi possível obter a resposta. Tente novamente.",
      );
      // Devolve o texto ao campo para o usuário não perder o que escreveu.
      setDraft(question);
      setMessages((current) => current.filter((message) => message.id !== outgoing.id));
    } finally {
      setSending(false);
    }
  }

  if (restoringSession || !user) {
    return (
      <main className="centered">
        <p className="muted">Carregando…</p>
      </main>
    );
  }

  return (
    <div className="chat-shell">
      <header className="chat-header">
        <div>
          <strong>Chat com IA</strong>
          <span className="muted"> · {user.username}</span>
        </div>
        <button type="button" className="ghost" onClick={logout}>
          Sair
        </button>
      </header>

      <main className="chat-messages">
        {messages.length === 0 && !sending && (
          <p className="muted empty">Faça uma pergunta para começar.</p>
        )}

        {messages.map((message) => (
          <article key={message.id} className={`bubble ${message.role}`}>
            {/* O conteúdo entra como texto, não como HTML. React escapa
                automaticamente, então uma resposta do modelo contendo tags não
                vira marcação executável na página. */}
            {message.content}
          </article>
        ))}

        {sending && (
          <article className="bubble assistant pending" aria-live="polite">
            Pensando…
          </article>
        )}

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <div ref={endOfMessagesRef} />
      </main>

      <form className="chat-input" onSubmit={handleSubmit}>
        <label htmlFor="message" className="sr-only">
          Sua pergunta
        </label>
        <input
          id="message"
          name="message"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Escreva sua pergunta…"
          maxLength={4000}
          autoComplete="off"
          disabled={sending}
        />
        <button type="submit" className="primary" disabled={sending || !draft.trim()}>
          {sending ? "Enviando…" : "Enviar"}
        </button>
      </form>
    </div>
  );
}
