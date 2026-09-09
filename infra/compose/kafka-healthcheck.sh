#!/bin/sh
set -e
cat > /tmp/client.properties <<EOF
security.protocol=SASL_PLAINTEXT
sasl.mechanism=PLAIN
sasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required username="${KAFKA_CLIENT_USER}" password="${KAFKA_CLIENT_PASSWORD}";
EOF
exec /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:29092 --command-config /tmp/client.properties
