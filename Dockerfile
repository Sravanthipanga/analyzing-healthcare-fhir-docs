FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir .

COPY corpus ./corpus
COPY static ./static
COPY scripts ./scripts

# Build the retrieval index (downloads the embedding model) at image build,
# and pre-download the cross-encoder reranker so first request is fast.
RUN python scripts/build_index.py \
 && python -c "from askfhir.reranker import get_reranker; get_reranker()"

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn askfhir.api:app --host 0.0.0.0 --port ${PORT}"]
