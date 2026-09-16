/**
 * Cliente da API.
 *
 * Todo acesso à rede do frontend passa por aqui. Concentrar isso em um módulo
 * evita que cada tela invente seu próprio tratamento de erro — e é o que
 * garante que o token seja anexado de um jeito só.
 */

// NEXT_PUBLIC_* é embutido no bundle e fica visível no navegador. Por isso aqui
// só entra a URL da API. Nenhuma chave, nenhum segredo: o que chega ao cliente
// é público, independentemente do nome da variável.
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Erro com o status HTTP preservado, para a tela decidir o que mostrar. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface User {
  id: number;
  username: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface ChatResponse {
  reply: string;
  created_at: string;
}

/** Traduz o corpo de erro da API para uma mensagem legível. */
function extractDetail(body: unknown, fallback: string): string {
  if (typeof body !== "object" || body === null) return fallback;

  const detail = (body as { detail?: unknown }).detail;

  if (typeof detail === "string") return detail;

  // Erro de validação do Pydantic: detail é uma lista de problemas por campo.
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string };
    if (typeof first?.msg === "string") {
      return first.msg.replace(/^Value error,\s*/, "");
    }
  }

  return fallback;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  token?: string | null;
  /** O chat pode demorar: o LLM responde devagar e o Render tem cold start. */
  timeoutMs?: number;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, token, timeoutMs = 15_000 } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // Sem timeout, uma requisição pendurada deixa a interface travada em
  // "carregando" para sempre, sem erro e sem resposta.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        "O servidor demorou demais para responder. Em plano gratuito a primeira requisição pode levar até um minuto — tente de novo.",
        408,
      );
    }
    // fetch só rejeita por falha de rede; erro HTTP vem como resposta.
    throw new ApiError("Não foi possível falar com o servidor. Ele está no ar?", 0);
  } finally {
    clearTimeout(timer);
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  const parsed: unknown = text ? JSON.parse(text) : null;

  if (!response.ok) {
    throw new ApiError(
      extractDetail(parsed, `A requisição falhou (HTTP ${response.status}).`),
      response.status,
    );
  }

  return parsed as T;
}

export const api = {
  register: (username: string, password: string) =>
    request<User>("/auth/register", { method: "POST", body: { username, password } }),

  login: (username: string, password: string) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: { username, password } }),

  me: (token: string) => request<User>("/auth/me", { token }),

  // O LLM leva alguns segundos, e no Render adormecido a primeira chamada pode
  // levar bem mais. Daí o timeout maior que o das demais rotas.
  sendMessage: (token: string, message: string) =>
    request<ChatResponse>("/chat", {
      method: "POST",
      body: { message },
      token,
      timeoutMs: 90_000,
    }),
};
