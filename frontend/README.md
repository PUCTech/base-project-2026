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
├── layout.tsx                 # fontes (next/font), AuthProvider e ToastProvider
├── page.tsx                   # raiz: redireciona para /recipes ou /login
├── login/page.tsx             # entrar e criar conta
├── recipes/
│   ├── page.tsx               # listagem, busca e filtros
│   ├── new/page.tsx           # receita nova (com "Gerar com IA")
│   └── [id]/
│       ├── page.tsx           # detalhe, avaliação, comentários, "o que falta"
│       ├── edit/page.tsx      # edição (só o autor)
│       └── cook/page.tsx      # modo cozinha: passo a passo e timers
├── pantry/page.tsx            # despensa e cadastro rápido por IA
├── shopping/page.tsx          # lista de compras e sugestões da IA
├── chat/page.tsx              # Chef IA
└── globals.css                # tema claro em custom properties
components/
├── AppShell.tsx               # moldura das telas autenticadas e navegação
├── RecipeForm.tsx             # formulário de receita (criar e editar)
├── recipe-bits.tsx            # foto, estrelas, barra "você tem X de Y"
└── icons.tsx                  # ícones SVG inline
lib/
├── api.ts                     # cliente HTTP: todo acesso à rede passa por aqui
├── auth.tsx                   # estado de autenticação (Context API)
├── hooks.ts                   # useResource: carregando/erro/dados + regra do 401
├── timers.ts                  # timers, alarme e Wake Lock do modo cozinha
├── draft.ts                   # rascunho de receita entre o chat e o formulário
├── format.ts                  # rótulos e formatação em pt-BR
└── toast.tsx                  # avisos curtos
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

## Decisões do assistente de cozinha

**Tema claro único.** Cores, raios e sombras são custom properties em `globals.css`; nenhuma
regra usa cor literal. Trocar a identidade visual é editar um bloco.

**`useResource` em vez de uma biblioteca de *data fetching*.** Toda tela precisa do mesmo trio
carregando/erro/dados e da mesma regra para `401`. O hook tem poucas linhas, e ainda descarta
respostas que chegam fora de ordem — a busca digitada rápido não mostra o resultado antigo.

**Atualização otimista onde a espera atrapalha.** Favoritar e marcar item da lista mudam a
tela na hora e desfazem se a API recusar. No mercado, com sinal fraco, esperar a rede para
riscar um item tornaria a lista inutilizável.

**A IA propõe, a pessoa revisa.** O rascunho de receita preenche o formulário; o cadastro
rápido mostra os itens marcados antes de gravar; as sugestões de compra vêm com checkbox.
Nada que a IA gera é salvo sem um clique de quem usa.

**Markdown do modelo sem HTML cru.** A resposta do Chef é renderizada com `react-markdown`, que
monta elementos React e, por padrão, não interpreta HTML: um `<img onerror=...>` na resposta
aparece como texto. Não há `dangerouslySetInnerHTML` no projeto.

**Timers pelo instante final.** O navegador desacelera o `setInterval` de abas em segundo
plano; um contador decrescente atrasaria. Cada timer guarda quando termina, e cada tick só
recalcula a diferença. O alarme usa a Web Audio API, destravada no clique que inicia o timer —
navegadores só tocam áudio depois de um gesto do usuário.

**`<img>` e não `next/image` nas fotos.** O backend já entrega as fotos redimensionadas e em
WebP; o otimizador do Next seria só um salto a mais.
