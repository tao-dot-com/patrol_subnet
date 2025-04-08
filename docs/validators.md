# Validators

## Hardware requirements
Min spec: 
CPU: 2
Memory: 4 GB
Disk space: 50 GB if running a local database, 20 GB if running an external database.

## Prerequsites

- docker
- bittensor cli (for wallet management)

### 1. Create a wallet
Be sure to create a wallet in advance following instructions from http://docs.bittensor.com

Register your validator with the Patrol subnet using the following command  
`btcli subnet register --netuid <UID> --wallet.name <YOUR_COLDKEY> --wallet.hotkey <YOUR_HOTKEY> --network <your_network>`  
where `<your network>` is either 81 (Mainet) or 275 (Testnet)

### 2. Install docker
See (https://docs.docker.com/engine/install/)

### 3. Configure docker  
The validator requires a SQL database. This can be either a Postgresql database (recommended) or an embedded SQLite database
The database is configured using a URL e.g.  
`postgres+asyncpg://<user>:<password>@<host>:<port>/<db name>` (PostgreSQL)  
The validator is configured using environment variables. Example docker-compose.yml files are given below.  
The following environment variables can be used to configure the validator by including them in the validator environment in the docker compose file.

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

Use any of the following templates. Paste the contents into a file named `docker-compose.yml`.

#### 3.1 External Postgres database server
```
services:
  validator:
    init: true
    image: public.ecr.aws/c9f7n4n0/patrol/validator:latest
    environment:
      DB_URL: "postgresql+asyncpg://<db user>:${DB_PASSWORD:-password}@<db host>:<db port/<db name>"
      WALLET_NAME: <YOUR_COLDKEY>
      HOTKEY_NAME: <YOUR_HOTKEY>
      # ... other environment variables
    volumes:
      - ~/.bittensor/wallets:/root/.bittensor/wallets:ro
```
#### 3.2 Postgres Database im docker (recommended for most validators)
```
volumes:
  data:
  
services:
  db:
    image: postgres:alpine
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD:-password}
      POSTGRES_USER: patrol
    ports:
      - "5432:5432"
   
  validator:
    depends:
      - db
    init: true
    image: public.ecr.aws/c9f7n4n0/patrol/validator:latest
    environment:
      DB_URL: "postgresql+asyncpg://patrol:${DB_PASSWORD:-password}@db:5432/patrol"
      WALLET_NAME: <YOUR_COLDKEY>
      HOTKEY_NAME: <YOUR_HOTKEY>
      # ... other environment variables
    volumes:
      - ~/.bittensor/wallets:/root/.bittensor/wallets:ro
      - data:/var/lib/postgresql/data
```
#### 3.3 Embedded SQLite database (Quick & dirty)
```
volumes:
  data:

services:
  validator:
    init: true
    image: public.ecr.aws/c9f7n4n0/patrol/validator:latest
    environment:
      DB_DIR: "/tmp/sqlite"
      WALLET_NAME: <YOUR_COLDKEY>
      HOTKEY_NAME: <YOUR_HOTKEY>
      # ... other environment variables
    volumes:
      - ~/.bittensor/wallets:/root/.bittensor/wallets:ro
      - data:/tmp/sqlite
```

### 4. Start the validator
`docker compose up`

### 5. Logging
!!TODO

### 6. Automatic updates
!!TODO

### 7. Customization
!!TODO

