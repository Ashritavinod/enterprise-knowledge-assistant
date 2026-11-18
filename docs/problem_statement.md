# Problem Statement

Employees often need to search multiple policy documents to find accurate
answers about workplace procedures and benefits. Manually locating the relevant
passage takes time and can make it difficult to confirm where an answer came
from.

The Employee Knowledge Assistant is intended to let employees ask questions in
plain language and receive answers grounded in the organization's policy
documents, with source references that make those answers easier to verify.

## Initial scope

- Accept policy PDFs as the initial document format.
- Retrieve relevant passages before generating an answer.
- Show the sources used to answer a question.
- Keep policy files and generated indexes in local project data directories.

This repository is a starter scaffold. Document ingestion, retrieval, answer
generation, and source display still need to be implemented.
