#!/bin/bash

set -e

export DB_URL=postgresql+asyncpg://patrol:password@localhost:5432/patrol
export ENABLE_WEIGHT_SETTING=0

python -m patrol.validation.validator