FROM python:latest

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt -t .

COPY . .

CMD ["python3", "bfcp.py"]