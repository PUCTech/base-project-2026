"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";

/** Rota raiz: manda para as receitas se houver sessão, senão para o login. */
export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // Espera a sessão salva ser restaurada. Redirecionar antes disso mandaria
    // para o login quem já está autenticado, num piscar de tela a cada F5.
    if (loading) return;
    router.replace(user ? "/recipes" : "/login");
  }, [user, loading, router]);

  return (
    <main className="centered">
      <p className="muted">Carregando…</p>
    </main>
  );
}
