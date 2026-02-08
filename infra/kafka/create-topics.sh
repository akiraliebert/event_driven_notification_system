#!/bin/bash
set -e

KAFKA_BROKER="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
PARTITIONS="${KAFKA_TOPIC_PARTITIONS:-3}"
REPLICATION="${KAFKA_TOPIC_REPLICATION:-1}"

echo "Waiting for Kafka to be ready at ${KAFKA_BROKER}..."

# Wait until Kafka broker is reachable
until kafka-topics --bootstrap-server "$KAFKA_BROKER" --list > /dev/null 2>&1; do
    echo "Kafka not ready yet, retrying in 2s..."
    sleep 2
done

echo "Kafka is ready. Creating topics..."

create_topic() {
    local topic="$1"
    if kafka-topics --bootstrap-server "$KAFKA_BROKER" --describe --topic "$topic" > /dev/null 2>&1; then
        echo "Topic '${topic}' already exists, skipping."
    else
        kafka-topics --bootstrap-server "$KAFKA_BROKER" \
            --create \
            --topic "$topic" \
            --partitions "$PARTITIONS" \
            --replication-factor "$REPLICATION"
        echo "Topic '${topic}' created (partitions=${PARTITIONS}, replication=${REPLICATION})."
    fi
}

create_topic "domain.events"
create_topic "notification.delivery"

echo "All topics ready:"
kafka-topics --bootstrap-server "$KAFKA_BROKER" --list
