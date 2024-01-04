FROM python:3.12-bookworm

COPY . /app
WORKDIR /app

RUN pip install -r requirements.txt --no-cache-dir

EXPOSE 8000

CMD ["gunicorn","application:app","--bind","0.0.0.0:8000"]
