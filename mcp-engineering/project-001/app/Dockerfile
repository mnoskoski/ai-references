# Dockerfile-debug
FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl git gnupg build-essential

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt
RUN cd mcp-servers && npm install && npm run build
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]