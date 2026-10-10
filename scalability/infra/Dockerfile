FROM python:3.12.11-slim
RUN pip install --no-cache-dir pika==1.3.2
COPY sink.py producer.py trusted_worker.py /infra/
ENTRYPOINT ["python"]
