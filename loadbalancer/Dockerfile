FROM python:3.9-slim
WORKDIR /app
RUN pip install flask requests docker
COPY app.py consistent_hash.py .
CMD ["python", "app.py"]
