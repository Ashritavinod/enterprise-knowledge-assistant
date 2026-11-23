# Employee Knowledge Assistant

Starter project for a policy-document question-answering application.

See [the problem statement](docs/problem_statement.md), [architecture](docs/architecture.md),
and [project plan](docs/project_plan.md) for project context and implementation
milestones.

## Setup on Windows

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use `venv\Scripts\python.exe` instead of
activating the environment.

## PostgreSQL

The API requires PostgreSQL (tested with 16) and won't start without it.
Create the databases once, entering the `postgres` user's password when
prompted:

```powershell
& "C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U postgres knowledge_assistant
& "C:\Program Files\PostgreSQL\16\bin\createdb.exe" -U postgres knowledge_assistant_test
```

Then set the connection string in `.env` (see `.env.example`):

```
DATABASE_URL=postgresql+psycopg://postgres:<password>@localhost:5432/knowledge_assistant
TEST_DATABASE_URL=postgresql+psycopg://postgres:<password>@localhost:5432/knowledge_assistant_test
```

Alternatively, `docker compose up` starts PostgreSQL and the API together.

The tables are created on startup. FAISS still performs the vector search;
PostgreSQL is the system of record for everything else:

| Table | Contents |
| --- | --- |
| `documents` | Each indexed PDF: title, SHA-256, page and chunk counts, indexed time |
| `chunks` | Each passage's page, section, text, and its id in the FAISS index |
| `conversations`, `messages` | Chat history for the React UI, including each answer's sources |
| `query_logs` | Every `/qa/ask`: question, found, top score and document, latency, embedding model |

The `documents` and `chunks` tables are synced with the FAISS index on every
startup. A document's chunks are rewritten only when the index was rebuilt.
`GET /health` returns 503 with `"database": "unavailable"` when PostgreSQL is
unreachable.

Example: questions that found no answer, to spot gaps in the documents:

```sql
SELECT question, count(*) FROM query_logs WHERE NOT found GROUP BY 1 ORDER BY 2 DESC;
```

## Run

Start the API:

```powershell
uvicorn backend.main:app --reload
```

Start the Streamlit frontend in a second terminal:

```powershell
streamlit run frontend/app.py
```

### React chat frontend (MarketMind)

`frontend-react/` is a React + TypeScript chat UI for the marketing knowledge
base. It needs Node.js 18+ and the API running on port 8000:

```powershell
cd frontend-react
npm install
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api/*` to
`http://127.0.0.1:8000` (set `BACKEND_URL` to change it). For a production
build, run `npm run build` and serve `frontend-react/dist/`, setting
`VITE_API_URL` at build time to the API's public URL.

The UI calls these endpoints:

- `POST /qa/ask/stream` with `{"question": "...", "conversation_id": "<uuid>"}`
  streams the reply as newline-delimited JSON: one `{"type": "sources",
  "sources": [...]}` event (up to three passages: document, page, section,
  excerpt, similarity score), then `{"type": "delta", "text": "..."}` events
  to append as they arrive, then `{"type": "done", "answer", "found", "model",
  "conversation_id"}`. `conversation_id` is optional; when given, the question
  and the full answer are saved to that conversation. The chat UI uses this.
- `POST /qa/ask` takes the same body and returns the whole reply at once as
  `{"answer", "found", "sources", "model", ...}`.
- In both, `found` is false only when no answer could be given: no passage
  cleared the relevance threshold and no chat model replied.
- `GET /qa/documents` lists the indexed PDFs with page and chunk counts.
- `GET /conversations`, `POST /conversations` (`{"title": "..."}`),
  `GET /conversations/{id}` (with its messages) and
  `DELETE /conversations/{id}` manage chat history, which is stored in
  PostgreSQL rather than in the browser.

When Azure OpenAI is configured (below), the assistant works as a chatbot:
every message gets a reply from the chat model, which `model` names. It
answers from the retrieved passages with `[n]` citations, replies to greetings
and thanks, explains what it can help with, rephrases or summarises earlier
answers, and says when the documents don't cover a question instead of
guessing. Facts about the company come only from the documents. Without Azure
OpenAI, or if the call fails, `answer` is the top retrieved passage (or the
not-found message) and `model` is null.

### Azure OpenAI (Microsoft Foundry)

1. In the [Foundry portal](https://ai.azure.com), deploy a chat model (for
   example `gpt-4.1-mini`) and, optionally, an embedding model (for example
   `text-embedding-3-small`).
2. Copy the resource endpoint and key into `.env`, with the deployment names:

   ```
   AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
   AZURE_OPENAI_API_KEY=<key>
   AZURE_OPENAI_CHAT_DEPLOYMENT=<chat deployment name>
   ```

3. Restart the API. Answers are now generated by that deployment, grounded in
   the top three passages and the last six messages of the conversation, with
   `[1]`-style citations that match the order of `sources`. In a conversation,
   a follow-up question ("which one is for buttons?") is first rewritten by the
   same deployment into a standalone question, which is what gets searched.

To embed with Azure as well, set `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` and
`EMBEDDING_PROVIDER=azure`; the FAISS index is rebuilt on the next start.
`LLM_PROVIDER=none` turns generation off; `LLM_PROVIDER=azure` makes missing
settings a startup-time error instead of a silent fallback. The client uses the
Azure OpenAI v1 API, so no `api-version` setting is needed.

The sample knowledge base describes the marketing team of **Honeycrumb
Bakehouse**, a fictional bakery and dessert brand (see
`data/policies/MARKETING_DOCS_INDEX.md`). Its five PDFs are generated from
`scripts/marketing_docs_content.py`; edit that file and run
`python scripts/generate_marketing_docs.py` to rebuild them.

Place policy PDF files in `data/policies/`. Store local configuration in `.env`;
never commit API keys or other secrets. Use `.env.example` as a template.

## Local FAISS retrieval

The backend embeds chunks locally and persists its FAISS index under
`data/index/`. The embedding backend is chosen by `EMBEDDING_PROVIDER`:

- `auto` (default): uses [fastembed](https://github.com/qdrant/fastembed) with
  `BAAI/bge-small-en-v1.5` (a local ONNX model, downloaded once, no API key)
  when the package is installed; otherwise it falls back to lexical hash
  embeddings and logs a warning.
- `fastembed`: requires fastembed and fails if it is unavailable.
- `hash`: deterministic token-hash vectors. They only match shared words, so
  paraphrased questions often miss.

PDFs are chunked by structure, not by character count. The loader reads each
page's layout to find headings (by font size and weight), paragraphs, bullets
and table rows, and drops running headers and footers. The chunker then packs
whole paragraphs into chunks of up to 700 characters that never cross a
section heading, starts every chunk with its section path (for example
`10. Channel Standards › Social media`), keeps each FAQ question with its
answer, and rejoins paragraphs that a page break cut in two.

Retrieval drops chunks whose cosine similarity is below a per-model minimum
(0.60 for fastembed, 0.10 for hash). Set `RETRIEVAL_MIN_SCORE` to override it.

The index is rebuilt automatically when the embedding model, the chunk
settings, or the text of any PDF in `data/policies/` changes; otherwise it is
reused on startup.

To test PDF loading, chunking and retrieval with sample questions, run from
the repository root:

```powershell
python -m unittest discover tests -v
```

The API tests in `tests/test_api.py` use the database in `TEST_DATABASE_URL`
and drop its tables on every run, so never point it at a database whose data
you need. They are skipped when that database is unreachable.

To add another embedding provider (for example Azure OpenAI), add an
`Embeddings` class with a unique `model_id` and `default_min_score` in
`backend/services/vector_store.py` and select it in `_create_embedding_model()`.
