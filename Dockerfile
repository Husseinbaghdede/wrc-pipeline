FROM apache/airflow:2.9.1-python3.11

# Install project dependencies at build time (not at startup)
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
