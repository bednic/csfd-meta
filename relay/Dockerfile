FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY anubis.py fetcher.py app.py ./
ENV PORT=9753
EXPOSE 9753
CMD ["python", "app.py"]
