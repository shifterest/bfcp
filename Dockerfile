FROM python:3.9

RUN mkdir /install /src
WORKDIR /install
RUN pip install --target="/install" --upgrade pip
COPY requirements.txt /install
RUN pip install --target="/install" -r requirements.txt
COPY README.md /src
COPY bfcp.py /src

# Run script
WORKDIR /src
CMD python /src/bfcp.py