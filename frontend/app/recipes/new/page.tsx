"use client";

import Link from "next/link";

import { AppShell, PageHeader } from "@/components/AppShell";
import { ChevronLeftIcon } from "@/components/icons";
import { RecipeForm } from "@/components/RecipeForm";

export default function NewRecipePage() {
  return (
    <AppShell>
      <Link href="/recipes" className="back-link">
        <ChevronLeftIcon size={18} /> Receitas
      </Link>
      <PageHeader title="Nova receita" subtitle="Escreva do zero ou peça um rascunho ao Chef IA." />
      <RecipeForm />
    </AppShell>
  );
}
