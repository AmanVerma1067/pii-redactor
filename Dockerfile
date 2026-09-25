FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin fonts-dejavu-core libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=10000
EXPOSE 10000
CMD sh -c "streamlit run app.py --server.port=${PORT:-10000} --server.address=0.0.0.0 --server.enableCORS=false --server.enableXsrfProtection=false"
