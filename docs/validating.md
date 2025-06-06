# Validators

## Hardware requirements
Min spec:
CPU: 2
Memory: 6 GB
Disk space: 50 GB if running a local database, 20 GB if running an external database.

## Prerequsites

- docker
- bittensor cli (for wallet management)

### 1. Create a wallet
Be sure to create a wallet in advance following instructions from http://docs.bittensor.com

Register your validator with the Patrol subnet using the following command  
`btcli subnet register --netuid <UID> --wallet.name <YOUR_COLDKEY> --wallet.hotkey <YOUR_HOTKEY> --network <your_network>`  
where `<your network>` is either 81 (Mainnet) or 275 (Testnet)

**Note: running the validator on testnet is not yet supported.**

### 2. Install docker
See (https://docs.docker.com/engine/install/)

### 3. Configure docker
The validator requires a SQL database. Either a local or external Postgresql database is supported. Other database engines may be used but these are not supported.  
The database is configured using a URL e.g.  
`postgres+asyncpg://<user>:<password>@<host>:<port>/<db name>` (PostgreSQL)  
The validator is configured using environment variables. Example docker-compose.yml files are given below.  
The following environment variables can be used to configure the validator by including them in the validator environment in the docker compose file.

| Variable               | Default                                             | Description                |
|------------------------|-----------------------------------------------------|----------------------------|
| NETWORK                | finney                                              | a subtensor network        |
| NET_UID                | 81                                                  | the net UID                | 
| DB_URL                 | postgresql+asyncpg://patrol:password@db:5432/patrol | The database URL           |
| WALLET_NAME            | default                                             | your wallet coldkey name   |
| HOTKEY_NAME            | default                                             | your wallet hotkey name    |                            
| ENABLE_WEIGHT_SETTING  | 1                                                   | Enables weight setting     |
| ARCHIVE_SUBTENSOR      | wss://archive.chain.opentensor.ai:443               | An archive subtensor node  |

Use any of the following templates. Paste the contents into a file named `docker-compose.yml`.

#### 3.1 External Postgres database server
```
services:
  validator:
    init: true
    image: public.ecr.aws/c9f7n4n0/patrol/validator:latest
    pull_policy: always
    restart: unless-stopped
    environment:
      DB_URL: postgresql+asyncpg://${DB_USERNAME:-patrol}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT:-5432}/${DB_NAME:-patrol}
      ENABLE_AUTO_UPDATE: 1
      WALLET_NAME: <my_wallet>
      HOTKEY_NAME: <my_hotkey>
    volumes:
      - ~/.bittensor/wallets:/root/.bittensor/wallets:ro
```
#### 3.2 Postgres Database in docker (recommended for most validators)
```
volumes:
  pg_data:

services:
  db:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: patrol
      POSTGRES_PASSWORD: password
    volumes:
      - pg_data:/var/lib/postgresql/data

  validator:
    init: true
    depends_on:
      - db
    image: public.ecr.aws/c9f7n4n0/patrol/validator:latest
    pull_policy: always
    restart: unless-stopped
    environment:
      DB_URL: postgresql+asyncpg://patrol:password@db:5432/patrol
      ENABLE_AUTO_UPDATE: 1
      WALLET_NAME: <my_wallet>
      HOTKEY_NAME: <my_hotkey>
    volumes:
      - ~/.bittensor/wallets:/root/.bittensor/wallets:ro
```

### 4. Start the validator
`docker compose up --wait`

### 5. Logging
Logs are emitted as JSON strings to aid analysis.
Docker logging may be customized according to your needs.

### 6. Automatic updates
If the environment variable `ENABLE_AUTO_UPDATE` is set to "1", the validator will check for an available update at the start of every validation cycle.

If an updated version is found, the service will terminate, the new imaged pulled and be restarted by docker compose.

Ensure that `pull_policy` is set to `always` in your compose files, and that `restart` is `unless-stopped`.

### 7. Customization hooks (coming soon)
