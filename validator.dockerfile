FROM python:3.12-slim AS base

LABEL vendor="Tensora"
LABEL maintainer="richard@tensora.com"
LABEL maintainer="jack@tensora.com"
LABEL bittensor.subnet="81"

WORKDIR /build

RUN apt-get update
RUN pip install --upgrade pip

COPY pyproject.toml .
ARG PSEUDO_VERSION=0.0.0
RUN SETUPTOOLS_SCM_PRETEND_VERSION_FOR_MY_PACKAGE=${PSEUDO_VERSION} pip install -e .

FROM base AS build

WORKDIR /build

COPY src/patrol/validation ./src/patrol/validation
COPY src/patrol/chain_data ./src/patrol/chain_data
COPY src/patrol/constants.py ./src/patrol/constants.py
COPY src/patrol/protocol.py ./src/patrol/protocol.py
COPY src/patrol/__init__.py ./src/patrol/__init__.py
COPY tests/validation ./tests/validation
COPY src/logging.ini ./src

RUN --mount=source=.git,target=.git,type=bind pip install -e '.[test]'
ARG TEST_POSTGRESQL_URL
RUN export TEST_POSTGRESQL_URL=$TEST_POSTGRESQL_URL && pytest ./tests

FROM base AS final

WORKDIR /patrol

COPY --from=build /build/src/ .
COPY src/logging.ini .
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "patrol.validation.validator"]

ENV DB_DIR=/var/patrol/sqlite
ENV DB_URL="sqlite+aiosqlite://${DB_DIR}/patrol.db"
