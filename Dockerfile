FROM python:3.12-slim

WORKDIR /app

# Instala dependências
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Cria pasta de dados
RUN mkdir -p /app/data

WORKDIR /app/backend

EXPOSE 8090

CMD ["python", "main.py"]
