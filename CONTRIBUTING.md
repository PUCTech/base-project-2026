# Fluxo de trabalho

Este projeto é desenvolvido em fluxo solo, mas segue deliberadamente o processo de um time.
O histórico do Git é parte da entrega: ele é o exemplo que os alunos vão ler depois.

## Branches

| Branch | Papel |
|---|---|
| `main` | Sempre estável. Protegida contra push direto; só recebe merge via Pull Request. |
| `feature/<tarefa>` | Uma branch por fase do plano. Nasce da `main` atualizada e morre no merge. |
| `hotfix/<descricao>` | Correção pontual fora do fluxo de fases — ilustra a diferença entre trabalho planejado e correção emergencial. |

Regras de nomenclatura: kebab-case, curto e descritivo. Nada de `teste`, `ajustes`,
`nova-branch` ou `wip`.

Branches deste projeto, uma por fase:

```
feature/setup-contrato-api      (Fase 1)
feature/backend-core            (Fase 2)
feature/auth-jwt                (Fase 3)
feature/docker-setup            (Fase 4)
feature/frontend-next           (Fase 5)
feature/chat-llm                (Fase 6)
feature/ci-cd-deploy            (Fase 7)
feature/revisao-final           (Fase 8)
```

Ciclo de cada fase:

```bash
git checkout main && git pull            # sempre partir da main atualizada
git checkout -b feature/<tarefa>
# ...commits pequenos...
git push -u origin feature/<tarefa>
gh pr create                             # descrição referencia a fase do plano
# merge só depois que a "Saída" da fase estiver funcionando de verdade
```

## Commits

[Conventional Commits](https://www.conventionalcommits.org/pt-br/v1.0.0/):

```
<tipo>(<escopo opcional>): <descrição no imperativo, minúscula, sem ponto final>
```

| Tipo | Uso |
|---|---|
| `feat` | nova funcionalidade |
| `fix` | correção de bug |
| `docs` | apenas documentação |
| `test` | apenas testes |
| `refactor` | muda a estrutura sem mudar o comportamento |
| `chore` | build, dependências, configuração |
| `ci` | pipeline de CI/CD |

```
feat(auth): adiciona login com JWT
fix(chat): trata timeout da Gemini API como 504
docs(readme): documenta variáveis de ambiente
```

Commits pequenos e com um propósito só. `feat: várias coisas` não é um commit, é um
despejo — e num material didático isso aparece.

## Pull Requests

Um PR por fase, mesmo sem outro revisor. A descrição:

1. referencia a fase correspondente em [`docs/projeto-chat-ia-liga.md`](docs/projeto-chat-ia-liga.md);
2. resume o que foi entregue;
3. diz **como verificar** que a "Saída" da fase funciona.

O merge só acontece com a "Saída" da fase efetivamente funcionando — não com "deve
funcionar". Merge em `squash` ou `rebase`, para manter o histórico da `main` linear.

## Segredos

`.env` está no `.gitignore` desde o commit inicial. Nenhuma chave de API, senha ou string
de conexão entra no repositório — nem em código, nem em teste, nem em comentário, nem numa
coleção do Postman. Chave vazada em commit continua no histórico mesmo depois de removida
do arquivo; a única resposta correta é **rotacionar a chave**.

Ao adicionar uma variável de ambiente nova, atualize [`.env.example`](.env.example) no mesmo
commit, com um valor de exemplo — nunca com o valor real.
