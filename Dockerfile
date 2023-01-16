FROM python:latest

WORKDIR /app

RUN pip3 install --target="/app" pip
COPY requirements.txt /app
RUN pip3 install --target="/app" -r requirements.txt

COPY bfcp.py /app
CMD ["python3", "bfcp.py"]