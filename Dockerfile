FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mnpd_service.py server.py ./

EXPOSE 5000

CMD ["python", "server.py", "--host", "0.0.0.0"]
