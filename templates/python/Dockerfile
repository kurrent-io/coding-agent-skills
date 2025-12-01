FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .

# Use environment variable for connection string
ENV KURRENTDB_CONNECTION_STRING=kurrentdb://localhost:2113?tls=false

CMD ["python", "example.py"]
