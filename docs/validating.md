# Validators

## Prerequsites

- docker

The database is configured using a URL e.g.
`sqlite+aiosqlite:///<some_path>/validator.db` (SQLite)
`postgres+asyncpg://<user>:<password>@<host>:<port>/<db name>` (PostgreSQL)

The validator is configured using environment variables. An example docker-compose.yml is given:

The following environment variables can be used to configure the validator:

| Variable               | Default                                 | Description                                                      |
|------------------------|-----------------------------------------|------------------------------------------------------------------|
| NETWORK                | finney                                  | a subtensor network                                              |
| NET_UID                | 81                                      | the net UID                                                      | 
| DB_DIR                 | /tmp/sqlite                             | The database directory - only used for SQLite if DB_URL is unset |
| DB_URL                 | sqlite+aiosqlite:///${DB_DIR}/patrol.db | The database URL                                                 |
| WALLET_NAME            | default                                 | your wallet coldkey name                                         |
| HOTKEY_NAME            | default                                 | your wallet hotkey name                                          |                            
| ENABLE_WEIGHT_SETTING  | 1                                       | Enables weight settting                                          |
| ARCHIVE_SUBTENSOR      | wss://archive.chain.opentensor.ai:443   | An archive subtensor node                                        |

#### Embedded SQLite database
services:
# This is optional - any Postgres database, or an embedded SQLite database can be used
validator:
depends:
- db
image: public.ecr.aws/c9f7n4n0/patrol/validator:latest
environment:
DB_DIR: "sqlite+aiosqlite:///<some_path>/validator.db"
WALLET_NAME: <YOUR_COLDKEY>
HOTKEY_NAME: <YOUR_HOTKEY>
volumes:
- ~/.bittensor/wallets:/root/.bittensor/wallets:ro
-
```

db:
image: postgres:alpine
environment:
POSTGRES_USER: patrol
POSTGRES_PASSWORD: ${DB_PASSWORD:-password}


3. Start the validator



- docker

## Options

### Postgresql database



