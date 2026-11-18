# Project Plan

## Milestones

1. **Foundation** — establish the repository structure, configuration template,
   health endpoint, and project documentation.
2. **Document ingestion** — load policy PDFs, split their text into useful
   passages, and report actionable errors for invalid or unreadable files.
3. **Retrieval** — build and persist a local vector index, then retrieve
   relevant passages for a question.
4. **Question answering** — connect retrieval to the language model and return
   answers grounded in retrieved passages with source metadata.
5. **User interface** — connect the Streamlit app to the API and display
   answers, sources, and useful error states.
6. **Quality and release** — add unit and integration tests, document setup and
   operations, and review data and credential handling before release.

## Current status

The project is at the foundation stage. The folders, app shells, health
endpoint, and initial documentation are present. The ingestion, retrieval, and
question-answering workflow remains to be implemented.

## Initial acceptance goals

- The API health endpoint returns a successful status.
- Policy PDFs can be indexed and searched with their source metadata retained.
- Answers are based on retrieved policy content and clearly identify sources.
- Missing configuration or unusable documents produce clear errors.
- Tests cover core document processing, retrieval, API, and UI integration.
