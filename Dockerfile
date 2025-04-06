FROM python:3.13-slim

WORKDIR  /usr/src/app
COPY . /usr/src/app

CMD [ "python", "scr/main.py" ]