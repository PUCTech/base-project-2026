"use client";

/**
 * Avisos curtos no canto da tela ("3 itens foram para a lista").
 *
 * Ação que dá certo sem mudar nada visível — mandar itens para outra tela,
 * por exemplo — precisa de confirmação, senão a pessoa clica de novo achando
 * que não funcionou.
 */

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

type Tone = "success" | "error" | "info";

interface Toast {
  id: number;
  message: string;
  tone: Tone;
}

interface ToastApi {
  show: (message: string, tone?: Tone) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const DURATION_MS = 4_000;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(0);

  const show = useCallback((message: string, tone: Tone = "success") => {
    const id = ++nextId.current;
    setToasts((current) => [...current, { id, message, tone }]);
    setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), DURATION_MS);
  }, []);

  const value = useMemo(() => ({ show }), [show]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* aria-live: o leitor de tela anuncia o aviso sem roubar o foco. */}
      <div className="toasts" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.tone}`} role="status">
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const context = useContext(ToastContext);
  if (context === null) throw new Error("useToast precisa estar dentro de <ToastProvider>.");
  return context;
}
