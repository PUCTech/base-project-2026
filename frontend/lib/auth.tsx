"use client";

/**
 * Estado de autenticação, via Context API.
 *
 * Context basta aqui: o estado é pequeno (um token e um usuário) e muda pouco.
 * Zustand ou Redux resolveriam o mesmo problema trazendo uma dependência e um
 * conceito a mais — vale quando o estado cresce, não antes.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, api, type User } from "@/lib/api";

const TOKEN_STORAGE_KEY = "chatia.token";

interface AuthState {
  user: User | null;
  token: string | null;
  /** True enquanto a sessão salva ainda está sendo restaurada. */
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // Restaura a sessão ao carregar a página.
  //
  // O token guardado é conferido contra GET /auth/me antes de valer como
  // sessão: ele pode ter expirado ou a conta pode ter sido apagada. Confiar no
  // que está no navegador sem validar levaria o usuário a uma tela de chat que
  // falha na primeira mensagem.
  useEffect(() => {
    const saved = readToken();
    if (!saved) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    api
      .me(saved)
      .then((profile) => {
        if (cancelled) return;
        setUser(profile);
        setToken(saved);
      })
      .catch((error) => {
        // 401 é token inválido ou expirado: descarta e segue como deslogado.
        // Falha de rede (status 0) não é motivo para apagar o token — o
        // servidor pode estar apenas dormindo.
        if (error instanceof ApiError && error.status === 401) {
          clearToken();
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const { access_token } = await api.login(username, password);
    const profile = await api.me(access_token);

    saveToken(access_token);
    setToken(access_token);
    setUser(profile);
  }, []);

  const register = useCallback(
    async (username: string, password: string) => {
      await api.register(username, password);
      // Cadastrou, já entra: pedir para digitar de novo o que acabou de digitar
      // é atrito sem ganho nenhum.
      await login(username, password);
    },
    [login],
  );

  const logout = useCallback(() => {
    // Sessão sem estado no servidor: sair é descartar o token. Ele continua
    // válido até expirar, o que está documentado em docs/contrato-api.md.
    clearToken();
    setToken(null);
    setUser(null);
    router.push("/login");
  }, [router]);

  const value = useMemo(
    () => ({ user, token, loading, login, register, logout }),
    [user, token, loading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth precisa estar dentro de <AuthProvider>.");
  }
  return context;
}

/**
 * O token fica no localStorage.
 *
 * Isso é uma escolha com custo conhecido: qualquer script injetado na página
 * (XSS) consegue ler o localStorage e roubar o token. Um cookie httpOnly seria
 * inacessível ao JavaScript e, portanto, mais seguro — mas exigiria que o
 * backend passasse a emitir cookie em vez de Bearer, com proteção contra CSRF
 * junto. Para o escopo deste projeto vale o Bearer; num sistema com dados
 * sensíveis de verdade, a escolha seria a outra.
 *
 * O acesso é embrulhado em try/catch porque o localStorage lança exceção em
 * navegação privada e quando o usuário bloqueia dados do site.
 */
function readToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

function saveToken(value: string): void {
  try {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, value);
  } catch {
    // Sem persistência, a sessão vale só enquanto a aba estiver aberta.
  }
}

function clearToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // Nada a fazer.
  }
}
