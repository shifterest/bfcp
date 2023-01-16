FROM python:3.9

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
RUN pip3 install discord.py environs

COPY . .

CMD ["python3", "bfcp.py"]