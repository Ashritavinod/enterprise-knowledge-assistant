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

## Run

Start the API:

```powershell
uvicorn backend.main:app --reload
```

Start the Streamlit frontend in a second terminal:

```powershell
streamlit run frontend/app.py
```

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

To add another embedding provider (for example Azure OpenAI), add an
`Embeddings` class with a unique `model_id` and `default_min_score` in
`backend/services/vector_store.py` and select it in `_create_embedding_model()`.
