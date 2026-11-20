FROM python:3.11-slim
WORKDIR /app
COPY . .
ENV PORT=10000 DB_PATH=/app/data/app.db
EXPOSE 10000
CMD ["python", "server.py"]
