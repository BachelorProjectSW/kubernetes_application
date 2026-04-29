from .utils import run_cmd
run_cmd("docker rm -f p6-postgres")
run_cmd("docker run --name p6-postgres -e POSTGRES_USER=strato -e POSTGRES_PASSWORD=strato -e POSTGRES_DB=strato -p 5433:5432 -v p6_pgdata:/var/lib/postgresql/data -d postgres:16")