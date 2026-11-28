FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/opt/fastembed \
    EMBEDDING_PROVIDER=fastembed

# Runtime dependencies only: Streamlit (old UI) and pytest aren't needed in production.
COPY requirements.txt .
RUN grep -viE "^(streamlit|pytest)\b" requirements.txt > requirements.prod.txt \
    && pip install -r requirements.prod.txt

# Bake the embedding model into the image so containers start without downloading it.
ARG FASTEMBED_MODEL=BAAI/bge-small-en-v1.5
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='${FASTEMBED_MODEL}')"

COPY . .

# Run as a non-root user; the app writes its FAISS index under data/index at startup.
RUN useradd --create-home app && mkdir -p data/index && chown -R app /app /opt/fastembed
USER app

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
