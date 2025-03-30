FROM python:3.10-slim

# Встановлюємо необхідні системні пакети
RUN apt-get update && apt-get install -y ffmpeg wget && rm -rf /var/lib/apt/lists/*

# Копіюємо файли
WORKDIR /app
COPY . /app

# Встановлюємо залежності
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
