import type { Metadata, Viewport } from "next";
import { Fraunces, Inter } from "next/font/google";

import { AuthProvider } from "@/lib/auth";
import { ToastProvider } from "@/lib/toast";

import "./globals.css";

// next/font baixa as fontes no build e as serve do próprio domínio: nenhuma
// requisição ao Google em tempo de uso, e nada de texto "piscando" enquanto a
// fonte carrega.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const fraunces = Fraunces({ subsets: ["latin"], variable: "--font-fraunces", display: "swap" });

export const metadata: Metadata = {
  title: "Cozinha — assistente de cozinha com IA",
  description: "Despensa, receitas, lista de compras e um chef com IA que sabe o que você tem em casa.",
};

export const viewport: Viewport = {
  themeColor: "#fbf7f2",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${inter.variable} ${fraunces.variable}`}>
      <body>
        <AuthProvider>
          <ToastProvider>{children}</ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
