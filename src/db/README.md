## Database Setup

### Postgres

Run postgres:

```bash
docker run --name p6-postgres -e POSTGRES_USER=strato -e POSTGRES_PASSWORD=strato -e POSTGRES_DB=strato -p 5433:5432 -v p6_pgdata:/var/lib/postgresql/data -d postgres:16
```

### pgAdmin

To use pgadmin (GUI) run pgadmin:

```bash
docker run --name pgadmin \
  -p 5050:80 \
  -e PGADMIN_DEFAULT_EMAIL=admin@admin.com \
  -e PGADMIN_DEFAULT_PASSWORD=admin \
  -d dpage/pgadmin4
```

Login details:

- username: `admin@admin.com`
- password: `admin`

After logging in:

1. Right click `Servers` -> `Register` -> `Server`
2. General

- Name: `strato`

3. Connection

- Hostname / address: IP where Postgres is hosted (local or strato ip)
- Port: `5433`
- Username: `admin`
- Password: `admin`
