FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/uploads /app/instance && useradd -m jolscan && chown -R jolscan:jolscan /app
USER jolscan
EXPOSE 5000
CMD ["python", "run.py"]
