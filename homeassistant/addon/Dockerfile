FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY source/ /app/
RUN pip install --no-cache-dir -r requirements.txt paho-mqtt==2.1.0 \
 && mkdir -p /data/private /data/logs \
 && ln -s /data/private /app/private && ln -s /data/logs /app/logs
COPY run.py /app/addon_run.py
COPY container_run.py /app/container_run.py
CMD ["python", "/app/addon_run.py"]
