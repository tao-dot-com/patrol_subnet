#!/bin/bash

set -e

docker compose up --wait

pytest ./tests

docker build \
  -t tensora/patrol-validator \
  -f validator.dockerfile \
  --build-arg TEST_POSTGRESQL_URL="postgresql+asyncpg://patrol:password@172.17.0.1:5432/patrol" \
  .

docker build \
  -t tensora/patrol-validator:rds \
  -f validator_aws_iam.dockerfile \
  --build-arg TEST_POSTGRESQL_URL="postgresql+asyncpg://patrol:password@172.17.0.1:5432/patrol" \
  .
