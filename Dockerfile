FROM denoland/deno:bin AS deno
FROM python:3.12-slim
COPY --from=deno /deno /usr/local/bin/deno
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
COPY static ./static
RUN useradd --create-home appuser
USER appuser
ENV PYTHONUNBUFFERED=1 PORT=10000
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn server:create_app --factory --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --proxy-headers --forwarded-allow-ips='*' --no-access-log"]
