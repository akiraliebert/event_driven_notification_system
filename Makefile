.PHONY: up down logs ps restart clean up-app build kafka-topics migrate psql redis-cli

# Infrastructure only (default)
up:
	docker compose up -d

# Infrastructure + application services
up-app:
	docker compose --profile app up -d

# Build application service images
build:
	docker compose --profile app build

down:
	docker compose --profile app down

logs:
	docker compose logs -f $(SVC)

ps:
	docker compose --profile app ps -a

restart:
	docker compose restart $(SVC)

# Remove all containers and volumes (data will be lost)
clean:
	docker compose --profile app down -v

# Run database migrations
migrate:
	docker compose --profile app run --rm db-migrate

# Re-run Kafka topic creation
kafka-topics:
	docker compose run --rm kafka-init

# Connect to PostgreSQL
psql:
	docker compose exec postgres psql -U $${POSTGRES_USER:-postgres} -d $${POSTGRES_DATABASE:-notifications}

# Connect to Redis
redis-cli:
	docker compose exec redis redis-cli
