# Database

The application uses PostgreSQL to persist test configurations, structured logs, and test results. The schema is managed automatically by SQLModel on startup — no manual migration step is required.

## Tables

| Table | Description |
|-------|-------------|
| `configs` | Saved test configuration snapshots, keyed by `config_id` |
| `app_logs` | Structured log entries and terminal debug messages, grouped by `config_id` |

## Running PostgreSQL

Start a PostgreSQL container with the default credentials:

```bash
docker run --name p6-postgres \
  -e POSTGRES_USER=strato \
  -e POSTGRES_PASSWORD=strato \
  -e POSTGRES_DB=strato \
  -p 5433:5432 \
  -v p6_pgdata:/var/lib/postgresql/data \
  -d postgres:16
```

The database is reachable at `localhost:5433` with the following credentials:

| Field | Value |
|-------|-------|
| Host | `localhost` |
| Port | `5433` |
| Database | `strato` |
| Username | `strato` |
| Password | `strato` |

## Environment variables

The database connection can be configured via environment variables. Set `DATABASE_URL` to override all individual settings:

```env
DATABASE_URL=postgresql+psycopg://strato:strato@<HOST>:5433/strato
```

Alternatively, set the individual variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | `100.109.95.2` | Database host (Tailscale IP of the server) |
| `POSTGRES_PORT` | `5433` | Database port |
| `POSTGRES_USER` | `strato` | Database user |
| `POSTGRES_PASSWORD` | `strato` | Database password |
| `POSTGRES_DB` | `strato` | Database name |

## pgAdmin (optional GUI)

To inspect the database with a graphical interface, run pgAdmin:

```bash
docker run --name pgadmin \
  -p 5050:80 \
  -e PGADMIN_DEFAULT_EMAIL=admin@admin.com \
  -e PGADMIN_DEFAULT_PASSWORD=admin \
  -d dpage/pgadmin4
```

Open `http://localhost:5050` and log in with:

- **Email:** `admin@admin.com`
- **Password:** `admin`

Then register the server:

1. Right-click **Servers** → **Register** → **Server**
2. **General** tab — Name: `strato`
3. **Connection** tab:
   - Host: IP address where PostgreSQL is running
   - Port: `5433`
   - Username: `strato`
   - Password: `strato`
