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
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Erro com o status HTTP preservado, para a tela decidir o que mostrar. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    /** Segundos até poder tentar de novo, quando a API informa (429). */
    readonly retryAfter: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ---------- Tipos do domínio (espelham os schemas do backend) ----------

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

export const CATEGORIES = [
  "hortifruti",
  "carnes",
  "laticinios",
  "graos",
  "padaria",
  "temperos",
  "doces",
  "bebidas",
  "congelados",
  "outros",
] as const;
export type Category = (typeof CATEGORIES)[number];

export type Difficulty = "facil" | "media" | "dificil";

export interface PantryItem {
  id: number;
  name: string;
  quantity: number | null;
  unit: string | null;
  category: Category;
  expires_on: string | null;
  created_at: string;
  updated_at: string;
}

export interface PantryItemInput {
  name: string;
  quantity?: number | null;
  unit?: string | null;
  category?: Category;
  expires_on?: string | null;
}

export interface Author {
  id: number;
  username: string;
}

export interface IngredientInput {
  name: string;
  quantity: number | null;
  unit: string | null;
  note: string | null;
}

export interface StepInput {
  instruction: string;
  timer_minutes: number | null;
}

/** O conteúdo de uma receita — também o formato do rascunho gerado pela IA. */
export interface RecipeInput {
  title: string;
  description: string;
  servings: number;
  prep_minutes: number | null;
  difficulty: Difficulty;
  ingredients: IngredientInput[];
  steps: StepInput[];
  created_by_ai?: boolean;
}

export interface RecipeSummary {
  id: number;
  title: string;
  description: string;
  servings: number;
  prep_minutes: number | null;
  difficulty: Difficulty;
  image_url: string | null;
  created_by_ai: boolean;
  author: Author;
  ingredient_count: number;
  pantry_have: number;
  avg_rating: number | null;
  rating_count: number;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
}

export interface Ingredient extends IngredientInput {
  id: number;
  in_pantry: boolean;
}

export interface Step extends StepInput {
  id: number;
  position: number;
}

export interface RecipeDetail extends RecipeSummary {
  ingredients: Ingredient[];
  steps: Step[];
  my_rating: number | null;
}

export type RecipeScope = "all" | "mine" | "favorites";

export interface RatingSummary {
  avg_rating: number | null;
  rating_count: number;
  my_rating: number | null;
}

export interface Comment {
  id: number;
  content: string;
  author: Author;
  created_at: string;
}

export interface ShoppingItem {
  id: number;
  name: string;
  quantity: number | null;
  unit: string | null;
  category: Category;
  checked: boolean;
  source: "manual" | "receita" | "ia";
  recipe_id: number | null;
  created_at: string;
}

export interface ShoppingItemInput {
  name: string;
  quantity?: number | null;
  unit?: string | null;
  category?: Category;
}

export interface ShoppingSuggestion extends ShoppingItemInput {
  reason: string;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

// ---------- Transporte ----------

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
  /** Objeto vira JSON; FormData segue como multipart (upload de foto). */
  body?: unknown;
  token?: string | null;
  /** As rotas de IA podem demorar: o LLM responde devagar e o Render tem cold start. */
  timeoutMs?: number;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, token, timeoutMs = 15_000 } = options;

  const headers: Record<string, string> = {};
  const isForm = body instanceof FormData;
  // No FormData o Content-Type fica de fora de propósito: o navegador o monta
  // sozinho, com o "boundary" que separa as partes do multipart.
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
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
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
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
    // Só legível porque o backend o lista em expose_headers do CORS.
    const retryAfter = Number(response.headers.get("Retry-After")) || null;
    throw new ApiError(
      extractDetail(parsed, `A requisição falhou (HTTP ${response.status}).`),
      response.status,
      retryAfter,
    );
  }

  return parsed as T;
}

/** URL absoluta de uma foto: a API devolve o caminho relativo a ela. */
export function mediaUrl(path: string | null): string | null {
  return path ? `${API_URL}${path}` : null;
}

// Timeout das rotas que chamam o LLM. Maior que o das demais porque o modelo
// leva alguns segundos — e o backend ainda pode retentar.
const AI_TIMEOUT = 90_000;

export const api = {
  // ---- Autenticação ----
  register: (username: string, password: string) =>
    request<User>("/auth/register", { method: "POST", body: { username, password } }),

  login: (username: string, password: string) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: { username, password } }),

  me: (token: string) => request<User>("/auth/me", { token }),

  // ---- Despensa ----
  pantry: {
    list: (token: string) => request<PantryItem[]>("/pantry", { token }),
    add: (token: string, item: PantryItemInput) =>
      request<PantryItem>("/pantry", { method: "POST", body: item, token }),
    addMany: (token: string, items: PantryItemInput[]) =>
      request<PantryItem[]>("/pantry/batch", { method: "POST", body: { items }, token }),
    update: (token: string, id: number, changes: Partial<PantryItemInput>) =>
      request<PantryItem>(`/pantry/${id}`, { method: "PATCH", body: changes, token }),
    remove: (token: string, id: number) =>
      request<void>(`/pantry/${id}`, { method: "DELETE", token }),
  },

  // ---- Receitas ----
  recipes: {
    list: (token: string, params: { scope?: RecipeScope; q?: string } = {}) => {
      const query = new URLSearchParams();
      if (params.scope && params.scope !== "all") query.set("scope", params.scope);
      if (params.q) query.set("q", params.q);
      const suffix = query.toString() ? `?${query}` : "";
      return request<RecipeSummary[]>(`/recipes${suffix}`, { token });
    },
    get: (token: string, id: number) => request<RecipeDetail>(`/recipes/${id}`, { token }),
    create: (token: string, recipe: RecipeInput) =>
      request<RecipeDetail>("/recipes", { method: "POST", body: recipe, token }),
    replace: (token: string, id: number, recipe: RecipeInput) =>
      request<RecipeDetail>(`/recipes/${id}`, { method: "PUT", body: recipe, token }),
    remove: (token: string, id: number) =>
      request<void>(`/recipes/${id}`, { method: "DELETE", token }),

    uploadImage: (token: string, id: number, file: File) => {
      const form = new FormData();
      form.append("file", file);
      return request<RecipeDetail>(`/recipes/${id}/image`, {
        method: "PUT",
        body: form,
        token,
        timeoutMs: 60_000,
      });
    },
    removeImage: (token: string, id: number) =>
      request<RecipeDetail>(`/recipes/${id}/image`, { method: "DELETE", token }),

    favorite: (token: string, id: number, on: boolean) =>
      request<void>(`/recipes/${id}/favorite`, { method: on ? "PUT" : "DELETE", token }),
    rate: (token: string, id: number, stars: number) =>
      request<RatingSummary>(`/recipes/${id}/rating`, { method: "PUT", body: { stars }, token }),
    unrate: (token: string, id: number) =>
      request<RatingSummary>(`/recipes/${id}/rating`, { method: "DELETE", token }),

    comments: (token: string, id: number) =>
      request<Comment[]>(`/recipes/${id}/comments`, { token }),
    comment: (token: string, id: number, content: string) =>
      request<Comment>(`/recipes/${id}/comments`, { method: "POST", body: { content }, token }),
    removeComment: (token: string, id: number, commentId: number) =>
      request<void>(`/recipes/${id}/comments/${commentId}`, { method: "DELETE", token }),
  },

  // ---- Lista de compras ----
  shopping: {
    list: (token: string) => request<ShoppingItem[]>("/shopping-list", { token }),
    add: (token: string, items: ShoppingItemInput[], source: "manual" | "ia" = "manual") =>
      request<ShoppingItem[]>("/shopping-list", {
        method: "POST",
        body: { items, source },
        token,
      }),
    fromRecipe: (token: string, recipeId: number, servings?: number) =>
      request<{ added: number; items: ShoppingItem[] }>(
        `/shopping-list/from-recipe/${recipeId}${servings ? `?servings=${servings}` : ""}`,
        { method: "POST", token },
      ),
    update: (token: string, id: number, changes: Partial<ShoppingItem>) =>
      request<ShoppingItem>(`/shopping-list/${id}`, { method: "PATCH", body: changes, token }),
    remove: (token: string, id: number) =>
      request<void>(`/shopping-list/${id}`, { method: "DELETE", token }),
    clearChecked: (token: string) =>
      request<void>("/shopping-list/checked", { method: "DELETE", token }),
    checkout: (token: string) =>
      request<{ moved: number; pantry: PantryItem[] }>("/shopping-list/checkout", {
        method: "POST",
        token,
      }),
  },

  // ---- IA ----
  ai: {
    recipeDraft: (token: string, prompt: string, usePantry: boolean) =>
      request<RecipeInput>("/ai/recipe-draft", {
        method: "POST",
        body: { request: prompt, use_pantry: usePantry },
        token,
        timeoutMs: AI_TIMEOUT,
      }),
    parsePantry: (token: string, text: string) =>
      request<{ items: PantryItemInput[] }>("/ai/pantry-parse", {
        method: "POST",
        body: { text },
        token,
        timeoutMs: AI_TIMEOUT,
      }),
    suggestShopping: (token: string, goal: string | null) =>
      request<{ suggestions: ShoppingSuggestion[] }>("/ai/shopping-suggestions", {
        method: "POST",
        body: { goal },
        token,
        timeoutMs: AI_TIMEOUT,
      }),
  },

  // ---- Chat ----
  chat: {
    send: (token: string, message: string) =>
      request<{ reply: string; created_at: string }>("/chat", {
        method: "POST",
        body: { message },
        token,
        timeoutMs: AI_TIMEOUT,
      }),
    history: (token: string) =>
      request<{ messages: ChatMessage[] }>("/chat/history?limit=100", { token }),
    clear: (token: string) => request<void>("/chat/history", { method: "DELETE", token }),
  },
};
