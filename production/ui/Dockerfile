FROM python:3.11-slim
RUN groupadd --gid 1000 sazon && \
    useradd --uid 1000 --gid sazon --create-home --shell /bin/bash sazon
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
USER sazon
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
