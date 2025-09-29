FROM python:3.11-slim-bullseye

WORKDIR /app

COPY requirements.txt requirements.txt
RUN apt-get update && apt-get upgrade -y && pip3 install --upgrade pip && pip3 install -r requirements.txt && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["python3", "bfcp.py"]