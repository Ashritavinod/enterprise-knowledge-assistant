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
