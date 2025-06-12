#!/bin/bash

set -e

docker compose -f ./docker-compose-local-postgres.yml up db --wait

#flake8 ./src --count --select=E9,F63,F7,F82 --show-source --statistics
# exit-zero treats all errors as warnings. The GitHub editor is 127 chars wide
#flake8 ./src --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

pip install -e ../common
pip install -e '.[test]'
pytest ./tests

cd ..
docker build \
  -t patrol/validator \
  -f ./validator/Dockerfile \
  --build-arg TEST_POSTGRESQL_URL="postgresql+asyncpg://patrol:password@172.17.0.1:5432/patrol" \
  --build-arg ARCHIVE_NODE="$ARCHIVE_NODE" \
  --progress plain \
  .

