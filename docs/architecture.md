# Architecture

## Components

- **React frontend** (`frontend-react/`): the MarketMind app. A small router
  (`src/router.tsx`) serves the document chatbot at `/` (`src/App.tsx`), the
  marketing modules (`src/intel/pages/`) and the public survey page `/s/<id>`.
  Charts are plain HTML/CSS (`src/intel/charts.tsx`), with no chart library.
  The original Streamlit page (`frontend/app.py`) is no longer used.
- **FastAPI backend** (`backend/main.py`): registers the routers below.
- **Routes** (`backend/routes/`):
  - `qa.py`, `conversations.py`: the document chatbot and chat history.
  - `campaigns.py`: campaigns, import from documents, apply strategy.
  - `intelligence.py`: competitor, research, sentiment and strategy modules;
    saved analyses and their PDF/Markdown reports.
  - `surveys.py`: survey drafting, editing, publishing, public responses,
    results and analysis.
  - `agent.py`: the supervisor agent (streamed).
- **Agents** (`backend/agents/`): `base.py` holds structured Azure OpenAI
  calls and the evidence/citation model; one module per specialist
  (`competitor`, `research`, `survey`, `sentiment`, `strategy`, `campaigns`)
  and `supervisor.py`, which coordinates them through tool calling.
- **Services** (`backend/services/`): PDF loading, chunking and FAISS search;
  Azure OpenAI client (`azure_openai.py`); Brave web search (`web_search.py`);
  `operations.py` (run an agent end to end: read the campaign, call the agent,
  save the result; shared by routes and supervisor); `analyses.py` and
  `insights.py` (persistence and digests); `reports.py` (Markdown and PDF).
- **Database** (`backend/db/`): PostgreSQL via SQLAlchemy. Documents, chunks,
  conversations, messages and the query log, plus `campaigns`, `analyses`
  (every saved AI result, with its input, result JSON, evidence and whether
  live research ran), `surveys` and `survey_responses`.
- **Data** (`data/`): marketing PDFs and the local FAISS index.

## Request flows

**Document chatbot.** The question (rewritten to stand alone if it is a
follow-up) is embedded and searched in FAISS; the top passages and recent
messages go to Azure OpenAI, whose answer streams back with `[n]` citations.

**Module analysis** (e.g. competitor intelligence):

1. The route validates input and reads the linked campaign.
2. The agent gathers evidence, each item with an id: document passages (D#),
   user-supplied details (U#), Brave Search results with URL and retrieval
   date (W#) when configured, or earlier saved analyses (A#) for strategies.
3. Azure OpenAI returns strict JSON-schema output citing evidence ids.
4. Unknown citations are dropped and uncited claims flagged as AI inference;
   counts and percentages are computed in code, not by the model.
5. The result is saved as an `analyses` row linked to the campaign and shown
   in the UI; reports render from the same row.

**Supervisor.** `/agent/chat` gives the model tools for document search,
campaign lookup and each specialist. It answers simple requests directly,
runs independent specialists in parallel threads, feeds their digests back,
and streams each step and the final combined answer to the UI.

**Survey.** Draft (AI) → edit → publish → respondents submit through the
public link (validated against the questions) → statistics computed from real
responses → AI insights plus sentiment of open-ended answers.

## Technologies

Python, FastAPI, PostgreSQL (SQLAlchemy + psycopg), FAISS, fastembed,
LangChain (vector store), PyMuPDF (PDF reading and report generation), pandas
(CSV), httpx (Brave Search), Azure OpenAI (`gpt-4o`, structured outputs and
tool calling), React 18 + TypeScript + Vite.
