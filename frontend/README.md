# Frontend — Next.js

## Rodar localmente

O backend precisa estar no ar (`docker compose up` na raiz).

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

<http://localhost:3000>

```bash
npm run lint       # ESLint
npx tsc --noEmit   # checagem de tipos
npm run build      # build de produção
```

## Organização

```
app/
├── layout.tsx       # AuthProvider envolvendo a aplicação
├── page.tsx         # raiz: redireciona para /chat ou /login
├── login/page.tsx   # entrar e criar conta
├── chat/page.tsx    # tela de chat
└── globals.css      # tema em custom properties, claro e escuro
lib/
├── api.ts           # cliente HTTP: todo acesso à rede passa por aqui
└── auth.tsx         # estado de autenticação (Context API)
```

## Decisões que não são óbvias no código

**Context API, não Zustand nem Redux.** O estado é pequeno — um token e um usuário — e muda
pouco. As alternativas resolveriam o mesmo problema trazendo uma dependência e um conceito a
mais; isso passa a valer quando o estado cresce, não antes.

**Todo acesso à rede passa por `lib/api.ts`.** Concentrar isso em um módulo evita que cada
tela invente seu próprio tratamento de erro, e é o que garante que o token seja anexado de
um jeito só. O `ApiError` preserva o status HTTP para a tela decidir o que mostrar — é assim
que o chat sabe que um `401` significa "token expirou, desloga" e não "mostra um aviso".

**Toda requisição tem timeout.** Sem ele, uma requisição pendurada deixa a interface travada
em "carregando" para sempre, sem erro e sem resposta. O `/chat` usa 90 s porque o LLM demora
e o Render dorme depois de 15 min ociosos — a primeira requisição pode levar quase um minuto
só para o container subir.

**O token guardado é validado contra `GET /auth/me` antes de valer como sessão.** Ele pode
ter expirado ou a conta pode ter sido apagada. Confiar no que está no navegador sem
verificar levaria o usuário a uma tela de chat que falha na primeira mensagem.

**Falha de rede não apaga o token; `401` apaga.** Um servidor dormindo não é motivo para
deslogar o usuário.

**O redirecionamento de `/chat` para `/login` é conveniência, não segurança.** A proteção
real está no backend, que exige o JWT em toda rota. Quem forçar a URL do chat vê a tela por
um instante e não consegue dado nenhum.

**A pergunta aparece na tela antes da resposta chegar** e é removida se o envio falhar, com
o texto devolvido ao campo — o usuário não perde o que escreveu.

## O token fica no `localStorage`

Escolha com custo conhecido: qualquer script injetado na página (XSS) consegue ler o
`localStorage` e roubar o token. Um cookie `httpOnly` seria inacessível ao JavaScript e,
portanto, mais seguro — mas exigiria que o backend emitisse cookie em vez de `Bearer`, com
proteção contra CSRF junto.

Para o escopo deste projeto vale o `Bearer`. Num sistema com dados sensíveis de verdade, a
escolha seria a outra — e é por isso que ela está escrita aqui em vez de ficar implícita.

O acesso é sempre embrulhado em `try/catch`: o `localStorage` lança exceção em navegação
privada e quando o usuário bloqueia dados do site.

## `NEXT_PUBLIC_*` é público

Variáveis com esse prefixo são embutidas no bundle JavaScript e ficam legíveis para qualquer
pessoa que abra o DevTools. Só `NEXT_PUBLIC_API_URL` existe aqui, e é só uma URL.

A chave da Gemini nunca passa pelo frontend: o navegador chama `POST /chat` e é o backend que
fala com o provedor.

## Vulnerabilidades conhecidas do `npm audit`

`npm audit` reporta duas vulnerabilidades vindas de `next` → `postcss`. O `npm audit fix
--force` "resolveria" instalando **Next.js 9.3.3** — um remédio pior que a doença. A correção
real é o Next 16, que exige **Node 20+**; este ambiente roda Node 18, então o projeto está
fixado no Next 15.

O impacto é limitado: a falha do `postcss` é de carregamento de source map em tempo de build,
não um vetor de ataque para a aplicação em produção. Atualizar para Node 20 e Next 16 é o
próximo passo natural.
