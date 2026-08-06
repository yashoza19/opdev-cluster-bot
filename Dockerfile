FROM registry.access.redhat.com/ubi9/python-312:latest

USER 0
WORKDIR /opt/app-root/src

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml README.md ./
COPY src ./src
COPY jobs ./jobs

RUN pip install --no-cache-dir .

USER 1001

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["opdev-cluster-bot"]
