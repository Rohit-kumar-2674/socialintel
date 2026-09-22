# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS dashboard
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS wheel
WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY backend/ backend/
COPY --from=dashboard /build/frontend/dist/ backend/socialintel/web/
RUN python -m pip wheel --no-deps --wheel-dir /wheels .

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SOCIALINTEL_DATA_DIR=/data SOCIALINTEL_ALLOWED_HOSTS=127.0.0.1,localhost
WORKDIR /app
COPY requirements.lock /app/requirements.lock
RUN python -m pip install --no-cache-dir -r requirements.lock \
    && groupadd --gid 10001 socialintel \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin socialintel \
    && mkdir /data && chown 10001:10001 /data
COPY --from=wheel /wheels/ /wheels/
RUN python -m pip install --no-cache-dir --no-deps /wheels/*.whl && rm -rf /wheels
COPY scripts/healthcheck.py /app/healthcheck.py
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "/app/healthcheck.py"]
CMD ["socialintel", "serve", "--host", "0.0.0.0", "--port", "8000"]
