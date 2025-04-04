#!/bin/bash

set -e

docker compose up --wait

pytest ./tests