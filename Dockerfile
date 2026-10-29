FROM python:3.11-slim

LABEL org.opencontainers.image.authors="A.Soroko <nerdsav@gmail.com>" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY notify_service.py .
COPY config.yaml config.yaml

RUN addgroup --system --gid 1001 appuser && \
    adduser --system --uid 1001 --gid 1001 appuser

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8448/health', verify=False)" || exit 1

EXPOSE 8448

CMD ["python", "-u", "notify_service.py"]

