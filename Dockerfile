FROM python:3.14
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

CMD ["fastapi", "dev", "app/main.py", "--host", "0.0.0.0"]
