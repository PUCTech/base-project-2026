"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface Resource<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  /** Busca de novo — depois de uma escrita que mudou o que está na tela. */
  reload: () => Promise<void>;
  /** Atualiza a tela na hora com a resposta de uma escrita, sem refazer o GET. */
  setData: React.Dispatch<React.SetStateAction<T | null>>;
}

/**
 * Carrega um recurso da API com o token da sessão.
 *
 * Todas as telas precisam do mesmo trio carregando/erro/dados e da mesma regra
 * para 401 (token expirou: sai da conta). Repetir isso em cada página seria a
 * receita para uma delas esquecer o 401 e ficar mostrando "erro" para sempre.
 *
 * `loader` precisa ser estável (useCallback ou função de módulo), senão o
 * efeito rodaria a cada renderização.
 */
export function useResource<T>(loader: (token: string) => Promise<T>): Resource<T> {
  const { token, logout } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // Descarta respostas que chegam depois de uma mais nova (busca digitada
  // rápido): sem isso, uma resposta lenta e antiga sobrescreveria a atual.
  const latest = useRef(0);

  const reload = useCallback(async () => {
    if (!token) return;
    const call = ++latest.current;
    setLoading(true);
    try {
      const result = await loader(token);
      if (call !== latest.current) return;
      setData(result);
      setError(null);
    } catch (caught) {
      if (call !== latest.current) return;
      if (caught instanceof ApiError && caught.status === 401) {
        logout();
        return;
      }
      setError(caught instanceof ApiError ? caught.message : "Não foi possível carregar.");
    } finally {
      if (call === latest.current) setLoading(false);
    }
  }, [token, loader, logout]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}

/** Mensagem legível para qualquer erro de uma ação da tela. */
export function errorMessage(caught: unknown, fallback = "Algo deu errado. Tente novamente.") {
  return caught instanceof ApiError ? caught.message : fallback;
}
