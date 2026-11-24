# Architecture

## Components

- **React frontend** (`frontend-react/`): the MarketMind document chatbot
  (`src/App.tsx`) and the Customer Reviews page (`src/reviews/`), switched by
  a small router (`src/router.tsx`, `src/Root.tsx`). The original Streamlit page (`frontend/app.py`) is no longer used.
- **FastAPI backend** (`backend/main.py`): registers the routers below.
- **Routes** (`backend/routes/`):
  - `qa.py`, `conversations.py`: the document chatbot and chat history.
  - `reviews.py`: the reviews dataset (browse, filter, CSV export) and the
    Review Insights Agent.
- **Services** (`backend/services/`): PDF loading, chunking and FAISS search;
  Azure OpenAI client (`azure_openai.py`); document registry
  (`document_registry.py`); the sample reviews dataset (`review_dataset.py`)
  and the Review Insights Agent (`review_agent.py`).
- **Database** (`backend/db/`): PostgreSQL via SQLAlchemy. Documents, chunks,
  conversations, messages and the query log, plus `products`, `reviews`,
  `product_sales` and `review_insights`.
- **Data** (`data/`): marketing PDFs and the local FAISS index.

## Request flows

**Document chatbot.** The question (rewritten to stand alone if it is a
follow-up) is embedded and searched in FAISS; the top passages and recent
messages go to Azure OpenAI, whose answer streams back with `[n]` citations.

**Review insights.** New reviews are classified by Azure OpenAI in parallel
batches (sentiment, confidence, topics) and the labels are stored. Ratings,
sentiment shares, demand, growth, seasonality and December share are computed
in Python. The model then writes the marketing report from those figures, the
rankings and real quotes; unknown products and citations are removed before the
report is saved to `review_insights`.

## Technologies

Python, FastAPI, PostgreSQL (SQLAlchemy + psycopg), FAISS, fastembed,
LangChain (vector store), PyMuPDF (PDF reading), Azure OpenAI (`gpt-4o`),
React 18 + TypeScript + Vite.
