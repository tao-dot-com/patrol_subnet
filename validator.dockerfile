FROM python:3.12-slim AS base

LABEL vendor="Tensora"
LABEL maintainer="richard@tensora.com"
LABEL maintainer="jack@tensora.com"
LABEL bittensor.subnet="81"

WORKDIR /build

RUN apt-get update
RUN pip install --upgrade pip

COPY pyproject.toml .
RUN pip install -e .

FROM base AS build

WORKDIR /build

COPY src/patrol/validation ./src/patrol/validation
COPY src/patrol/chain_data ./src/patrol/chain_data
COPY src/patrol/constants.py ./src/patrol/constants.py
COPY src/patrol/protocol.py ./src/patrol/protocol.py
COPY tests/validation ./tests/validation

RUN pip install -e '.[test]'
ARG TEST_POSTGRESQL_URL
RUN export TEST_POSTGRESQL_URL=$TEST_POSTGRESQL_URL && pytest ./tests

FROM base AS final

WORKDIR /patrol

COPY --from=build /build/src/ .

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "patrol.validation.validator"]

ENV LOGGING_INI="logging.ini"
ENV DB_DIR=/var/patrol/sqlite
ENV DB_URL="sqlite+aiosqlite://${DB_DIR}/patrol.db"