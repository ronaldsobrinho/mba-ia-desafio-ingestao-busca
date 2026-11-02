# Ingestão e Busca Semântica com LangChain e Postgres

CLI que lê um PDF, grava os embeddings num PostgreSQL com pgVector e responde perguntas **somente** com base no conteúdo desse PDF. Quando a resposta não está no documento, devolve a frase fixa:

```
Não tenho informações necessárias para responder sua pergunta.
```

Desafio 1 do MBA de IA da Full Cycle, feito a partir do fork de [devfullcycle/mba-ia-desafio-ingestao-busca](https://github.com/devfullcycle/mba-ia-desafio-ingestao-busca).

## Como funciona

**Ingestão (`src/ingest.py`)**

1. `PyPDFLoader` lê o `document.pdf`.
2. `RecursiveCharacterTextSplitter` divide o texto em chunks de 1000 caracteres com overlap de 150.
3. `GoogleGenerativeAIEmbeddings` gera o embedding de cada chunk.
4. `PGVector` grava os vetores no Postgres. A coleção é apagada e recriada a cada execução, então rodar a ingestão de novo não duplica chunks.

**Chat (`src/chat.py` + `src/search.py`)**

1. A pergunta é vetorizada com o mesmo modelo de embeddings da ingestão.
2. `similarity_search_with_score` busca os 10 trechos mais parecidos (k=10).
3. Os trechos entram no `{contexto}` do prompt do enunciado, junto com a pergunta.
4. `ChatGoogleGenerativeAI` (temperatura 0) responde, e a resposta aparece no terminal.

A busca não decide se a resposta existe: ela sempre traz 10 trechos. Quem decide é o LLM, seguindo as regras do prompt — se nenhum trecho responde à pergunta, ele devolve a frase fixa.

## Stack

| Item | Escolha |
|---|---|
| Linguagem | Python 3.12 |
| Framework | LangChain |
| Banco | PostgreSQL 17 + pgVector (`pgvector/pgvector:pg17`), via Docker Compose |
| Provedor | Google Gemini |
| Embeddings | `models/gemini-embedding-001` (3.072 dimensões) |
| LLM | `gemini-3.5-flash-lite` |

## Pré-requisitos

- **Python 3.12.** No Python 3.14 algumas dependências (como o `psycopg-binary`) ainda não instalam.
- **Docker** com Docker Compose.
- **API Key do Google Gemini** ([Google AI Studio](https://aistudio.google.com/apikey)). O plano gratuito é suficiente.

## Como executar

Todos os comandos rodam a partir da raiz do repositório.

### 1. Ambiente virtual e dependências

Linux / macOS:

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Variáveis de ambiente

Copie o `.env.example` para `.env` e preencha a `GOOGLE_API_KEY`:

```bash
cp .env.example .env
```

| Variável | Descrição |
|---|---|
| `GOOGLE_API_KEY` | API Key do Google Gemini |
| `GOOGLE_EMBEDDING_MODEL` | Modelo de embeddings, usado na ingestão e na busca |
| `EMBEDDING_BATCH_SIZE` | Chunks enviados por lote na ingestão (padrão: 20) — ver [Ajuste dos lotes ao modelo de embeddings](#ajuste-dos-lotes-ao-modelo-de-embeddings) |
| `EMBEDDING_BATCH_PAUSE_SECONDS` | Pausa em segundos entre um lote e outro (padrão: 60) |
| `GOOGLE_LLM_MODEL` | Modelo que gera a resposta |
| `DATABASE_URL` | Conexão do Postgres (o valor do exemplo já bate com o `docker-compose.yml`) |
| `PG_VECTOR_COLLECTION_NAME` | Nome da coleção de vetores |
| `PDF_PATH` | Caminho do PDF, relativo à raiz do repositório |

O chat confere as variáveis ao iniciar e avisa se alguma estiver faltando.

### 3. Banco de dados

```bash
docker compose up -d
```

O serviço `bootstrap_vector_ext` cria a extensão `vector` e encerra (o log dele mostra `CREATE EXTENSION`).

### 4. Ingestão do PDF

```bash
python src/ingest.py
```

Com os valores padrão leva cerca de 3 minutos: os chunks são enviados em lotes de 20, com pausa de 60 segundos entre os lotes, por causa do limite de requisições do plano gratuito (ver [Ajuste dos lotes ao modelo de embeddings](#ajuste-dos-lotes-ao-modelo-de-embeddings)).

```
20/67 chunks gravados
40/67 chunks gravados
60/67 chunks gravados
67/67 chunks gravados
67 chunks gravados em 'desafio_ingestao_busca'.
```

### 5. Chat

```bash
python src/chat.py
```

```
Faça sua pergunta (digite 'sair' para encerrar):

PERGUNTA: Qual o faturamento da Empresa SuperTechIABrazil?
RESPOSTA: R$ 10.000.000,00

PERGUNTA: Quantos clientes temos em 2024?
RESPOSTA: Não tenho informações necessárias para responder sua pergunta.
```

Para sair: `sair`, `exit`, `quit` ou Ctrl+C. Linhas vazias são ignoradas, e um erro numa pergunta não encerra o chat.

## Testes

`tests/mainTests.py` roda 18 perguntas contra a chain real e mostra, para cada uma, a resposta esperada, a resposta obtida e se veio a frase fixa. Precisa do banco no ar e da ingestão feita.

```bash
python tests/mainTests.py
```

As respostas esperadas foram tiradas do próprio `document.pdf` (980 empresas com nome, faturamento e ano de fundação):

| Grupo | Casos | Resultado |
|---|---|---|
| Dentro do contexto | Faturamento e ano de empresas no começo, no meio e no fim do PDF, incluindo nomes quase iguais (Alfa Energia S.A. × Alfa Energia Holding) | 6/6 corretas |
| Fora do contexto | Conhecimento geral, dado que o PDF não tem sobre empresa que existe nele (CEO, funcionários), pedido de opinião | 5/5 frase fixa |
| Casos-limite | Nome escrito errado, nome ambíguo, pergunta longa, tentativa de furar a regra ("ignore as instruções..."), cálculo, perguntas que exigem a tabela inteira | Sem nenhuma resposta inventada — ver [Limitações](#limitações) |

No nome ambíguo ("Qual o faturamento da Aurora Educação?", que corresponde a duas empresas), a resposta varia entre execuções: às vezes a frase fixa, às vezes as duas empresas com os respectivos faturamentos. Os dois resultados são aceitáveis, porque os dois valores estão escritos no PDF.

## Decisões técnicas

- **Modelos.** O enunciado não fixa modelos. Os sugeridos no enunciado da plataforma (`models/embedding-001` e `gemini-2.5-flash-lite`) devolveram 404 para contas novas no momento da implementação, então foram usados `models/gemini-embedding-001` e `gemini-3.5-flash-lite`. Os dois vêm do `.env`, e o mesmo modelo de embeddings é usado na ingestão e na busca — vetores de modelos diferentes não são comparáveis.
- **Ingestão em lotes configuráveis.** Enviar todos os chunks de uma vez estourou o limite de requisições do modelo de embeddings (erro 429), então a ingestão manda lotes com pausa entre eles. O tamanho do lote e a pausa vêm do `.env` — ver [Ajuste dos lotes ao modelo de embeddings](#ajuste-dos-lotes-ao-modelo-de-embeddings).
- **Embedding em um lugar só.** `src/embeddings.py` cria o modelo de embeddings (`get_embeddings()`), e a ingestão e a busca usam essa mesma função. Assim as duas pontas sempre usam o mesmo modelo e a mesma configuração.
- **Sem corte por score.** Nos testes, a pergunta fora do contexto teve score parecido com o dos trechos irrelevantes das perguntas válidas, então um limite de score não separaria bem os dois casos. A barreira contra respostas fora do PDF é o prompt.
- **Regra a mais no prompt.** O `PROMPT_TEMPLATE` é o do enunciado com uma regra acrescentada no bloco REGRAS:

  ```
  - Nunca faça cálculos, somas ou comparações: responda apenas valores escritos no CONTEXTO.
  ```

  Sem ela, a pergunta "qual a soma dos faturamentos da Alfa Energia S.A. e da Alfa Energia Holding?" era respondida com um valor calculado pelo LLM, que não está escrito no PDF — contra a regra de não produzir "interpretações além do que está escrito".
- **`transport="rest"` no embedding.** O `GoogleGenerativeAIEmbeddings` cria por padrão um cliente gRPC assíncrono, mesmo em código síncrono. Ao fechar o programa, esse cliente era destruído depois do módulo `grpc` e imprimia um traceback (`'NoneType' object has no attribute 'POLLER'`). Com transporte REST o erro não aparece e as respostas não mudam.
- **Correção no `docker-compose.yml` do template.** O `bootstrap_vector_ext` saía com código 0 sem criar a extensão `vector`: o `command` em várias linhas era quebrado em pedaços separados, e o `sh -c` só executava o primeiro (`PGPASSWORD=postgres`), então o `psql` nunca rodava. Corrigido passando o comando como um item único de lista — testado com o banco criado do zero.

## Ajuste dos lotes ao modelo de embeddings

Os valores padrão (`EMBEDDING_BATCH_SIZE=20`, `EMBEDDING_BATCH_PAUSE_SECONDS=60`) foram calibrados para o `gemini-embedding-001` no **plano gratuito**, que aceita 100 requisições por minuto — e cada chunk conta como uma requisição. Nos testes, com a mesma quantidade por lote e pausa de 15 segundos, o limite estourou (erro 429) no 4º lote.

Ao trocar de modelo de embeddings ou de plano, ajuste os dois valores ao limite do novo modelo, consultando a documentação do provedor:

- **Limite maior** (plano pago, outro modelo): aumente o lote e/ou reduza a pausa para a ingestão terminar mais rápido.
- **Erro 429 durante a ingestão**: reduza o lote ou aumente a pausa e rode a ingestão de novo — a coleção é recriada do zero, então não sobra nada da tentativa anterior.

Tempo aproximado da ingestão: (número de lotes − 1) × pausa. Com o `document.pdf` (67 chunks) e os valores padrão: 4 lotes, 3 pausas de 60 s.

## Limitações

O LLM só vê os 10 trechos que a busca entrega, e a busca compara o sentido do texto, não o valor de uma coluna. Por isso, perguntas como estas recebem a frase fixa mesmo com a resposta estando no PDF:

- "Qual empresa tem o maior faturamento?" — exige olhar as 980 linhas da tabela.
- "Qual empresa foi fundada em 2025?" — o trecho com o ano 2025 não fica entre os 10 mais parecidos com a pergunta.

Não é erro de implementação: é o comportamento esperado de um RAG por similaridade, e o LLM responde corretamente que não tem a informação em vez de inventar.

## Problemas conhecidos

- **Troca do modelo de embeddings.** A tabela de vetores é criada com a dimensão do primeiro modelo usado. Se trocar o `GOOGLE_EMBEDDING_MODEL`, apague o volume (`docker compose down -v`) e refaça a ingestão.

## Estrutura do projeto

```
├── docker-compose.yml
├── requirements.txt
├── .env.example          # Template das variáveis de ambiente
├── src/
│   ├── embeddings.py     # Modelo de embeddings compartilhado (ingestão e busca)
│   ├── ingest.py         # Ingestão do PDF
│   ├── search.py         # Busca e montagem da chain (prompt + LLM)
│   ├── chat.py           # CLI
├── tests/
│   └── mainTests.py      # Bateria de perguntas contra a chain real
├── document.pdf          # PDF para ingestão
└── README.md
```
