"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";

import { AppShell } from "@/components/AppShell";
import { BookIcon, ChefHatIcon, SendIcon, SparklesIcon } from "@/components/icons";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { saveRecipeDraft } from "@/lib/draft";
import { errorMessage } from "@/lib/hooks";
import { useToast } from "@/lib/toast";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

const STARTERS = [
  "O que eu faço hoje com o que tenho?",
  "Tem algo na despensa perto de vencer?",
  "Uma sobremesa rápida sem forno",
  "Como substituir ovo em bolo?",
];

export default function ChatPage() {
  return (
    <AppShell wide>
      <Chat />
    </AppShell>
  );
}

function Chat() {
  const { token, logout } = useAuth();
  const router = useRouter();
  const toast = useToast();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [converting, setConverting] = useState<string | null>(null);

  const endOfMessagesRef = useRef<HTMLDivElement>(null);

  // O histórico fica no servidor, então a conversa continua de onde parou —
  // inclusive em outro aparelho. E é o mesmo histórico que o backend envia ao
  // modelo como contexto.
  useEffect(() => {
    if (!token) return;
    api.chat
      .history(token)
      .then(({ messages: saved }) =>
        setMessages(saved.map((m) => ({ id: String(m.id), role: m.role, content: m.content }))),
      )
      .catch(() => {
        // Sem histórico, a conversa começa vazia; o erro de verdade aparece
        // na primeira pergunta, se o servidor estiver mesmo fora.
      })
      .finally(() => setLoadingHistory(false));
  }, [token]);

  // Mantém a última mensagem visível conforme a conversa cresce.
  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || !token || sending) return;

    const outgoing: ChatMessage = { id: `user-${Date.now()}`, role: "user", content: question };

    // A pergunta aparece na hora, antes da resposta chegar. Esperar o servidor
    // para só então mostrar o que o usuário acabou de digitar faz a interface
    // parecer travada.
    setMessages((current) => [...current, outgoing]);
    setDraft("");
    setError(null);
    setSending(true);

    try {
      const { reply } = await api.chat.send(token, question);
      setMessages((current) => [
        ...current,
        { id: `assistant-${Date.now()}`, role: "assistant", content: reply },
      ]);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        logout();
        return;
      }
      setError(errorMessage(caught, "Não foi possível obter a resposta. Tente novamente."));
      // Devolve o texto ao campo para o usuário não perder o que escreveu.
      setDraft(question);
      setMessages((current) => current.filter((message) => message.id !== outgoing.id));
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void send(draft);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter envia; Shift+Enter quebra a linha.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send(draft);
    }
  }

  async function newConversation() {
    if (!token || !window.confirm("Começar uma conversa nova? O histórico atual será apagado.")) return;
    try {
      await api.chat.clear(token);
      setMessages([]);
      setError(null);
    } catch (caught) {
      toast.show(errorMessage(caught), "error");
    }
  }

  /**
   * "Salvar como receita": o texto livre do chat vira um rascunho estruturado
   * (POST /ai/recipe-draft) e abre no formulário de receita, para revisar.
   */
  async function saveAsRecipe(message: ChatMessage) {
    if (!token) return;
    setConverting(message.id);
    try {
      const recipe = await api.ai.recipeDraft(
        token,
        `Transforme o texto abaixo em uma receita estruturada, mantendo ingredientes, quantidades e passos.\n\n${message.content}`,
        false,
      );
      if (!saveRecipeDraft(recipe)) {
        toast.show("Seu navegador bloqueou o armazenamento da sessão; não deu para abrir o rascunho.", "error");
        setConverting(null);
        return;
      }
      router.push("/recipes/new");
    } catch (caught) {
      toast.show(errorMessage(caught), "error");
      setConverting(null);
    }
  }

  return (
    <div className="chat">
      <div className="chat-head">
        <h1>
          <SparklesIcon size={22} /> Chef IA
        </h1>
        {messages.length > 0 && (
          <button type="button" className="btn btn-ghost" onClick={newConversation}>
            Nova conversa
          </button>
        )}
      </div>

      <div className="chat-messages">
        {!loadingHistory && messages.length === 0 && !sending && (
          <div className="chat-welcome">
            <span className="brand-mark">
              <ChefHatIcon size={28} />
            </span>
            <h2>O que vamos cozinhar?</h2>
            <p>
              O Chef conhece sua despensa, sua lista de compras e suas receitas favoritas. Pergunte
              do seu jeito.
            </p>
            <div className="suggestions">
              {STARTERS.map((starter) => (
                <button key={starter} type="button" className="chip" onClick={() => send(starter)}>
                  {starter}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) =>
          message.role === "user" ? (
            <article key={message.id} className="bubble user">
              {message.content}
            </article>
          ) : (
            <article key={message.id} className="bubble assistant">
              {/* react-markdown monta elementos React a partir do Markdown e,
                  por padrão, NÃO interpreta HTML cru: um "<img onerror=...>"
                  na resposta do modelo aparece como texto, não vira marcação.
                  Por isso não há dangerouslySetInnerHTML em lugar nenhum. */}
              <div className="markdown">
                <Markdown>{message.content}</Markdown>
              </div>
              <div className="bubble-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => saveAsRecipe(message)}
                  disabled={converting !== null}
                >
                  <BookIcon size={15} />
                  {converting === message.id ? "Montando a receita…" : "Salvar como receita"}
                </button>
              </div>
            </article>
          ),
        )}

        {sending && (
          <article className="bubble assistant pending" aria-live="polite">
            O Chef está pensando…
          </article>
        )}

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <div ref={endOfMessagesRef} />
      </div>

      <form className="chat-input" onSubmit={handleSubmit}>
        <label htmlFor="message" className="sr-only">
          Sua pergunta
        </label>
        <textarea
          id="message"
          name="message"
          rows={1}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Pergunte ao Chef…"
          maxLength={4000}
          autoComplete="off"
          disabled={sending}
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={sending || !draft.trim()}
          aria-label="Enviar"
        >
          <SendIcon size={18} />
        </button>
      </form>
    </div>
  );
}
