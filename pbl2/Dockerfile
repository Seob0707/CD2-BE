FROM python:3.12.8-bookworm

ENV PYTHONUNBUFFERED=1

WORKDIR /src

RUN pip install "poetry==1.8.4"

COPY pyproject.toml ./
COPY poetry.lock ./
COPY api ./api
COPY migrations ./migrations
RUN mkdir -p /src/certs && \
    wget https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -O /src/certs/rds-ca-2019-root.pem


ENV PYTHONUNBUFFERED=1
RUN poetry config virtualenvs.in-project true
RUN if [ -f pyproject.toml ]; then poetry install --no-root; fi

ENV TZ=Asia/Seoul



#실행 명령
ENTRYPOINT ["poetry", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--reload", "--log-level", "debug"]

