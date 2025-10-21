FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libfreetype6-dev \
    libpng-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
COPY README.md /app/
COPY main.py /app/
COPY config.yaml /app/

RUN pip install --no-cache-dir uv && \
    uv pip install --system .

EXPOSE 9191

CMD ["python", "main.py"]

