FROM python:3.12-bookworm

ARG PORT=8000
ENV PORT=$PORT

COPY . /app
WORKDIR /app

RUN pip install -r requirements.txt --no-cache-dir

EXPOSE $PORT

CMD gunicorn application:app --bind 0.0.0.0:$PORT
