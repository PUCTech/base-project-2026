/**
 * Passagem de um rascunho de receita entre telas.
 *
 * O chat gera o rascunho ("Salvar como receita") e o formulário de receita
 * nova o abre preenchido. O meio de transporte é o sessionStorage: ele é da
 * aba atual, some quando ela fecha e não vai para o servidor — o rascunho só
 * vira dado de verdade quando a pessoa salva.
 *
 * O acesso é embrulhado em try/catch porque o storage lança exceção em
 * navegação privada e quando o usuário bloqueia dados do site.
 */

import type { RecipeInput } from "@/lib/api";

const KEY = "cozinha.recipe-draft";

export function saveRecipeDraft(draft: RecipeInput): boolean {
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(draft));
    return true;
  } catch {
    return false;
  }
}

/** Lê e apaga: o rascunho abre uma vez, e não reaparece na próxima receita nova. */
export function takeRecipeDraft(): RecipeInput | null {
  try {
    const saved = window.sessionStorage.getItem(KEY);
    if (!saved) return null;
    window.sessionStorage.removeItem(KEY);
    return JSON.parse(saved) as RecipeInput;
  } catch {
    return null;
  }
}
