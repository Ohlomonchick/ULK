FROM python:3.12-slim-bullseye
LABEL authors="Dmitry"

RUN mkdir ./app
COPY ./requirements.txt ./app
COPY . ./app

WORKDIR /app

RUN pip install -r requirements.txt

RUN python manage.py collectstatic --noinput
RUN python manage.py makemigrations --noinput
RUN python manage.py migrate --noinput

EXPOSE 8000

ENV CREATE_ADDRESS="192.0.0.1" CREATE_PORT="5555"

ENTRYPOINT ["python", "manage.py", "runserver", "0.0.0.0:8000"]