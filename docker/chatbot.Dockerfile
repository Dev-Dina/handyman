FROM python:3.11-slim

# httpx is required by chatbot/api_client.py for all API calls.
RUN pip install --no-cache-dir streamlit httpx

WORKDIR /app

# Required so `from chatbot.api_client import ...` resolves when streamlit
# runs chatbot/main.py as a script — streamlit does not add WORKDIR to sys.path.
ENV PYTHONPATH=/app

COPY chatbot/ ./chatbot/

EXPOSE 8501

CMD ["streamlit", "run", "chatbot/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
