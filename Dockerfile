FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py login.py gen_session.py ./

# Tell Python to flush logs immediately so `fly logs` / `docker logs` are live.
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
