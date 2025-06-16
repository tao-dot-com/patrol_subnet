#!/bin/bash

set -e

export DB_URL=postgresql+asyncpg://patrol:password@localhost:5433/patrol
export ENABLE_AUTO_UPDATE=0
export ENABLE_WEIGHT_SETTING=0
export ENABLE_HOTKEY_OWNERSHIP_TASK=0
export ENABLE_DASHBOARD_SYNDICATION=0
export ENABLE_ALPHA_SELL_TASK=1
export ALPHA_SELL_PREDICTION_WINDOW_BLOCKS=20

python -m patrol.validation.validator