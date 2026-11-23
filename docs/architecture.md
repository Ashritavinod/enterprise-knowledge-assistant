# Architecture

## Components

- **Streamlit frontend** (`frontend/app.py`): user-facing question interface.
- **FastAPI backend** (`backend/main.py`): HTTP API and health endpoint.
- **Routes** (`backend/routes/`): API endpoint definitions, including the
  question-answering route.
- **Services** (`backend/services/`): PDF loading, retrieval/vector-store, and
  retrieval-augmented generation logic.
- **Database** (`backend/db/`): SQLAlchemy models and the PostgreSQL
  connection. PostgreSQL stores the indexed documents and chunks, chat
  history, and a log of every question asked. FAISS still does vector search.
- **Data** (`data/`): policy PDFs and the local FAISS index.

## Intended request flow

1. An administrator places policy PDFs in `data/policies/`.
2. The backend extracts and chunks document text, then creates or updates a
   local vector index.
3. The frontend submits an employee's question to the FastAPI backend.
4. The backend retrieves relevant passages and uses them as context for answer
   generation.
5. The frontend presents the answer and its supporting document references.

The repository currently contains only the initial app shells and service
placeholders. The end-to-end ingestion and question-answering flow is planned,
not yet implemented.

## Technologies

Python, Streamlit, React, FastAPI, PostgreSQL (SQLAlchemy + psycopg), LangChain, FAISS, PyMuPDF, and an OpenAI-compatible
language model integration are listed or represented in the starter project.
