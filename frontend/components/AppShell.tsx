"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import {
  BookIcon,
  CartIcon,
  ChefHatIcon,
  LogOutIcon,
  PantryIcon,
  SparklesIcon,
} from "@/components/icons";
import { useAuth } from "@/lib/auth";

const NAV = [
  { href: "/recipes", label: "Receitas", Icon: BookIcon },
  { href: "/pantry", label: "Despensa", Icon: PantryIcon },
  { href: "/shopping", label: "Compras", Icon: CartIcon },
  { href: "/chat", label: "Chef IA", Icon: SparklesIcon },
];

/**
 * Moldura das telas autenticadas: cabeçalho, navegação e proteção de rota.
 *
 * A proteção aqui é conveniência de navegação, não segurança: quem forçar a
 * URL vê a moldura por um instante, mas toda chamada à API exige o JWT, e sem
 * ele não há dado nenhum para mostrar.
 */
export function AppShell({
  children,
  wide = false,
}: {
  children: React.ReactNode;
  /** Sem largura máxima — para telas que ocupam tudo, como o modo cozinha. */
  wide?: boolean;
}) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <main className="centered">
        <p className="muted">Carregando…</p>
      </main>
    );
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-inner">
          <Link href="/recipes" className="brand">
            <span className="brand-mark">
              <ChefHatIcon size={20} />
            </span>
            <span className="brand-name">Cozinha</span>
          </Link>

          <nav className="topnav" aria-label="Seções">
            {NAV.map(({ href, label, Icon }) => (
              <Link
                key={href}
                href={href}
                className={pathname.startsWith(href) ? "topnav-link active" : "topnav-link"}
                aria-current={pathname.startsWith(href) ? "page" : undefined}
              >
                <Icon size={18} />
                {label}
              </Link>
            ))}
          </nav>

          <div className="topbar-user">
            <span className="muted user-name">{user.username}</span>
            <button type="button" className="icon-button" onClick={logout} aria-label="Sair">
              <LogOutIcon size={18} />
            </button>
          </div>
        </div>
      </header>

      <main className={wide ? "page page-wide" : "page"}>{children}</main>

      {/* No celular a navegação vai para baixo, ao alcance do polegar — na
          cozinha, a outra mão costuma estar ocupada. */}
      <nav className="bottomnav" aria-label="Seções">
        {NAV.map(({ href, label, Icon }) => (
          <Link
            key={href}
            href={href}
            className={pathname.startsWith(href) ? "bottomnav-link active" : "bottomnav-link"}
            aria-current={pathname.startsWith(href) ? "page" : undefined}
          >
            <Icon size={22} />
            <span>{label}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
}

/** Título de página com ações à direita. */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}
