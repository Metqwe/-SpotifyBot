# Вибір офіційного образу Python
FROM python:3.10-slim

# Директорія для твого бота
WORKDIR /app

# Копіюємо requirements.txt і ставимо залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо увесь код бота в контейнер
COPY . .

# Команда для запуску бота
CMD ["python", "main.py"]
