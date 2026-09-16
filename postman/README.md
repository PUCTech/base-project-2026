# Coleção Postman

Contrato **executável** da API. Escrito na Fase 1, antes da implementação — é normal (e
esperado) que as requisições falhem no começo: elas descrevem o que a API *vai* responder.
A cada fase entregue, mais requisições passam.

| Arquivo | Conteúdo |
|---|---|
| `chat-ia.postman_collection.json` | As requisições e seus testes |
| `chat-ia.postman_environment.json` | Variáveis do ambiente local |

## Como usar

1. No Postman: **Import** → selecione os dois arquivos.
2. Escolha o environment **"Chat com IA — Local"** no seletor do canto superior direito.
3. Rode `Auth / POST /auth/login`. O script de teste salva o JWT em `{{access_token}}`, e
   as rotas protegidas o herdam pelo Bearer configurado no nível da coleção — não é preciso
   colar token em requisição nenhuma.

Pela linha de comando, com [Newman](https://github.com/postmanlabs/newman):

```bash
npx newman run postman/chat-ia.postman_collection.json \
  -e postman/chat-ia.postman_environment.json
```

## O que está versionado aqui

Só valores de exemplo para ambiente local. **Nenhuma senha real, nenhum token, nenhuma
chave de API** entra nestes arquivos — o Postman exporta variáveis marcadas como `secret`
com o valor preenchido, então confira o diff antes de commitar uma reexportação.

Para apontar para produção, crie um environment separado **fora do repositório**, mudando
`baseUrl` para a URL do Render.

## Manutenção

A coleção é documentação viva: mudou a API, muda a coleção **no mesmo Pull Request**. Cada
requisição carrega testes (`pm.test`) que verificam status code e formato da resposta —
incluindo os casos negativos, que são os que de fato pegam regressão: senha errada deve dar
401, rota protegida sem token deve dar 401, mensagem vazia deve dar 422.
