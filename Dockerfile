FROM python:3.9

# Install requirements
COPY requirements.txt /src
RUN pip install -r /src/requirements.txt

# Copy Python script
COPY bfcp.py /src

# Run script
CMD python /src/bfcp.py