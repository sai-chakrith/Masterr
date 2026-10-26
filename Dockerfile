FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MASTRR_ENV=production
WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend ./backend
COPY content ./content
COPY reference ./reference
COPY scripts ./scripts
COPY migrations ./migrations
COPY deploy ./deploy
COPY alembic.ini pyproject.toml ./
RUN useradd --create-home --uid 10001 mastrr
USER mastrr
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--log-config", "deploy/logging.json"]
