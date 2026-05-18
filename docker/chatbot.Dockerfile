FROM python:3.11-slim

RUN pip install --no-cache-dir streamlit

WORKDIR /app

COPY chatbot/ ./chatbot/

EXPOSE 8501

CMD ["streamlit", "run", "chatbot/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
