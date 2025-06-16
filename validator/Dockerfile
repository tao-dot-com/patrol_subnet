FROM python:3.12-slim AS base

LABEL vendor="Tensora"
LABEL maintainer="richard@tensora.com"
LABEL maintainer="jack@tensora.com"
LABEL bittensor.subnet="81"

WORKDIR /build/validator


RUN apt-get update
RUN pip install --upgrade pip

COPY common/ ../common/
RUN ls -al ../common

ARG PSEUDO_VERSION="0.0.0"
RUN SETUPTOOLS_SCM_PRETEND_VERSION=${PSEUDO_VERSION} pip install -e ../common

COPY validator/pyproject.toml .
RUN SETUPTOOLS_SCM_PRETEND_VERSION=${PSEUDO_VERSION} pip install -e .

FROM base AS build


COPY validator/src/ ./src/

#COPY src/patrol/chain_data ./src/patrol/chain_data
#COPY src/patrol/constants.py ./src/patrol/constants.py
#COPY src/patrol/protocol.py ./src/patrol/protocol.py
#COPY src/patrol/__init__.py ./src/patrol/__init__.py
COPY validator/tests/ ./tests/
#COPY src/patrol/logging.ini ./src/patrol/logging.ini

ARG SETUPTOOLS_SCM_PRETEND_VERSION="0.0.0"
RUN SETUPTOOLS_SCM_PRETEND_VERSION=${SETUPTOOLS_SCM_PRETEND_VERSION} pip install -e '.[test]'
ARG TEST_POSTGRESQL_URL
ARG ARCHIVE_NODE
RUN export TEST_POSTGRESQL_URL=$TEST_POSTGRESQL_URL ARCHIVE_NODE=$ARCHIVE_NODE && pytest ./tests

FROM base AS final

WORKDIR /patrol

COPY --from=build /build/validator/src/ .
#COPY src/patrol/logging.ini .
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "patrol.validation.validator"]

ENV DB_DIR=/var/patrol/sqlite
ENV DB_URL="sqlite+aiosqlite:///${DB_DIR}/patrol.db"
