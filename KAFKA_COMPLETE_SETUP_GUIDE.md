# Kafka Complete Setup Guide for Trading Application

## Overview

This guide provides step-by-step instructions to set up Apache Kafka locally for development and in production environments for the trading application. Kafka is used for real-time market data streaming, trading signals, and inter-service communication.

## Table of Contents

1. [Local Development Setup](#local-development-setup)
2. [Production Deployment](#production-deployment)
3. [Configuration](#configuration)
4. [Testing](#testing)
5. [Troubleshooting](#troubleshooting)
6. [Best Practices](#best-practices)

---

## Local Development Setup

### Prerequisites

- **Java 8 or higher** (OpenJDK recommended)
- **Windows 10/11** (for this guide)
- **At least 4GB RAM**
- **5GB free disk space**

### Step 1: Verify Java Installation

```bash
java -version
```

If Java is not installed, download from: https://adoptium.net/temurin/releases/

### Step 2: Download and Install Kafka

**Option 1: Use Existing Script (Recommended)**
```bash
# From project root directory
local_kafka_setup.bat
```

**Option 2: Manual Setup**

1. **Create Kafka directory:**
   ```bash
   mkdir C:\kafka
   cd C:\kafka
   ```

2. **Download Kafka:**
   ```bash
   powershell -Command "Invoke-WebRequest -Uri 'https://dlcdn.apache.org/kafka/4.1.0/kafka_2.13-4.1.0.tgz' -OutFile 'kafka.tgz'"
   powershell -Command "tar -xzf kafka.tgz"
   del kafka.tgz
   cd kafka_2.13-4.1.0
   ```

### Step 3: Configure Kafka for KRaft Mode

1. **Update server.properties:**
   ```properties
   # File: C:\kafka\kafka_2.13-4.1.0\config\server.properties

   # Server Basics
   process.roles=broker,controller
   node.id=1
   controller.quorum.voters=1@localhost:9093
   controller.quorum.bootstrap.servers=localhost:9093

   # Socket Settings
   listeners=PLAINTEXT://:9092,CONTROLLER://:9093
   advertised.listeners=PLAINTEXT://localhost:9092,CONTROLLER://localhost:9093
   controller.listener.names=CONTROLLER
   inter.broker.listener.name=PLAINTEXT

   # Log Directory (Windows-friendly)
   log.dirs=logs

   # Security Protocol Map
   listener.security.protocol.map=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,SSL:SSL,SASL_PLAINTEXT:SASL_PLAINTEXT,SASL_SSL:SASL_SSL

   # Replication Settings (for single node)
   offsets.topic.replication.factor=1
   transaction.state.log.replication.factor=1
   transaction.state.log.min.isr=1
   ```

### Step 4: Start Kafka

1. **Generate cluster ID:**
   ```bash
   cd C:\kafka\kafka_2.13-4.1.0
   bin\windows\kafka-storage.bat random-uuid
   ```
   Save the generated UUID (e.g., `OW8LgJuaSrSzj_3d8yGOSw`)

2. **Format storage:**
   ```bash
   bin\windows\kafka-storage.bat format -t YOUR_CLUSTER_ID -c config\server.properties
   ```

3. **Start Kafka server:**
   ```bash
   bin\windows\kafka-server-start.bat config\server.properties
   ```

### Step 5: Create Trading Topics

```bash
# Market data topics
bin\windows\kafka-topics.bat --create --bootstrap-server localhost:9092 --topic trading.market_data.raw --partitions 1 --replication-factor 1

bin\windows\kafka-topics.bat --create --bootstrap-server localhost:9092 --topic trading.market_data.processed --partitions 3 --replication-factor 1

# Trading signal topics
bin\windows\kafka-topics.bat --create --bootstrap-server localhost:9092 --topic trading.signals.breakout --partitions 2 --replication-factor 1

bin\windows\kafka-topics.bat --create --bootstrap-server localhost:9092 --topic trading.signals.gap --partitions 2 --replication-factor 1

bin\windows\kafka-topics.bat --create --bootstrap-server localhost:9092 --topic trading.signals.momentum --partitions 2 --replication-factor 1

# Analytics topics
bin\windows\kafka-topics.bat --create --bootstrap-server localhost:9092 --topic trading.analytics.market --partitions 2 --replication-factor 1

# UI topics
bin\windows\kafka-topics.bat --create --bootstrap-server localhost:9092 --topic trading.ui.price_updates --partitions 3 --replication-factor 1

bin\windows\kafka-topics.bat --create --bootstrap-server localhost:9092 --topic trading.ui.alerts --partitions 1 --replication-factor 1
```

### Step 6: Verify Installation

```bash
# List topics
bin\windows\kafka-topics.bat --bootstrap-server localhost:9092 --list

# Test producer
bin\windows\kafka-console-producer.bat --bootstrap-server localhost:9092 --topic trading.market_data.raw

# Test consumer (in another terminal)
bin\windows\kafka-console-consumer.bat --bootstrap-server localhost:9092 --topic trading.market_data.raw --from-beginning
```

---

## Production Deployment

### Deployment Options

#### Option 1: Cloud Managed Services (Recommended)

**Amazon MSK (Managed Streaming for Apache Kafka)**
- Fully managed service
- Auto-scaling and patching
- Built-in monitoring
- VPC integration

**Confluent Cloud**
- Kafka as a Service
- Global availability
- Schema Registry included
- Advanced monitoring

**Azure Event Hubs**
- Kafka-compatible
- Integrated with Azure ecosystem
- Auto-scaling
- Built-in security

#### Option 2: Self-Managed on Cloud (Advanced)

**AWS EC2 Deployment**

1. **Instance Requirements:**
   ```
   Instance Type: t3.large or larger
   Storage: EBS with at least 100GB SSD
   Security Group: Allow ports 9092, 9093
   ```

2. **Installation Script:**
   ```bash
   #!/bin/bash
   # Update system
   sudo yum update -y

   # Install Java
   sudo yum install -y java-11-openjdk-devel

   # Download Kafka
   cd /opt
   sudo wget https://dlcdn.apache.org/kafka/4.1.0/kafka_2.13-4.1.0.tgz
   sudo tar -xzf kafka_2.13-4.1.0.tgz
   sudo mv kafka_2.13-4.1.0 kafka
   sudo chown -R ec2-user:ec2-user /opt/kafka
   ```

3. **Production Configuration:**
   ```properties
   # /opt/kafka/config/server.properties

   # Server Basics
   process.roles=broker,controller
   node.id=1
   controller.quorum.voters=1@localhost:9093

   # Network Settings
   listeners=PLAINTEXT://:9092,CONTROLLER://:9093
   advertised.listeners=PLAINTEXT://YOUR_EC2_PUBLIC_IP:9092

   # Performance Settings
   num.network.threads=8
   num.io.threads=16
   socket.send.buffer.bytes=102400
   socket.receive.buffer.bytes=102400
   socket.request.max.bytes=104857600

   # Log Settings
   log.dirs=/opt/kafka/logs
   num.partitions=3
   num.recovery.threads.per.data.dir=2

   # Retention Policy
   log.retention.hours=168
   log.segment.bytes=1073741824
   log.retention.check.interval.ms=300000

   # Replication Settings
   offsets.topic.replication.factor=3
   transaction.state.log.replication.factor=3
   transaction.state.log.min.isr=2
   ```

4. **Systemd Service:**
   ```ini
   # /etc/systemd/system/kafka.service
   [Unit]
   Description=Apache Kafka
   After=network.target

   [Service]
   Type=simple
   User=ec2-user
   ExecStart=/opt/kafka/bin/kafka-server-start.sh /opt/kafka/config/server.properties
   ExecStop=/opt/kafka/bin/kafka-server-stop.sh
   Restart=on-failure
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

#### Option 3: Docker Deployment

**Docker Compose Configuration:**

```yaml
# docker-compose.kafka.yml
version: '3.8'

services:
  kafka:
    image: confluentinc/cp-kafka:7.4.0
    container_name: kafka
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:29093
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:29093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_LOG_DIRS: /var/lib/kafka/data
      CLUSTER_ID: OW8LgJuaSrSzj_3d8yGOSw
    ports:
      - "9092:9092"
    volumes:
      - kafka_data:/var/lib/kafka/data
    networks:
      - kafka-network

  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    container_name: kafka-ui
    depends_on:
      - kafka
    environment:
      KAFKA_CLUSTERS_0_NAME: local
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:9092
    ports:
      - "8080:8080"
    networks:
      - kafka-network

volumes:
  kafka_data:

networks:
  kafka-network:
    driver: bridge
```

**Start with Docker:**
```bash
docker-compose -f docker-compose.kafka.yml up -d
```

---

## Configuration

### Application Configuration

**Python Application (FastAPI):**
```python
# config/kafka_config.py
from kafka import KafkaProducer, KafkaConsumer
import json

class KafkaConfig:
    BOOTSTRAP_SERVERS = ['localhost:9092']  # Change for production

    PRODUCER_CONFIG = {
        'bootstrap_servers': BOOTSTRAP_SERVERS,
        'value_serializer': lambda v: json.dumps(v).encode('utf-8'),
        'key_serializer': lambda k: k.encode('utf-8') if k else None,
        'acks': 'all',  # Wait for all replicas
        'retries': 3,
        'batch_size': 16384,
        'linger_ms': 10,
        'buffer_memory': 33554432,
    }

    CONSUMER_CONFIG = {
        'bootstrap_servers': BOOTSTRAP_SERVERS,
        'value_deserializer': lambda m: json.loads(m.decode('utf-8')),
        'key_deserializer': lambda k: k.decode('utf-8') if k else None,
        'auto_offset_reset': 'earliest',
        'enable_auto_commit': True,
        'group_id': 'trading-app-group',
        'session_timeout_ms': 30000,
        'heartbeat_interval_ms': 10000,
    }

# Usage example
producer = KafkaProducer(**KafkaConfig.PRODUCER_CONFIG)
consumer = KafkaConsumer('trading.market_data.raw', **KafkaConfig.CONSUMER_CONFIG)
```

**Environment Variables:**
```bash
# .env
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_SECURITY_PROTOCOL=PLAINTEXT
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=
KAFKA_SASL_PASSWORD=
```

---

## Testing

### Manual Testing

```bash
# Producer test
echo '{"symbol":"RELIANCE","price":2500.50,"timestamp":"2025-09-14T15:30:00Z"}' | bin\windows\kafka-console-producer.bat --bootstrap-server localhost:9092 --topic trading.market_data.raw

# Consumer test
bin\windows\kafka-console-consumer.bat --bootstrap-server localhost:9092 --topic trading.market_data.raw --from-beginning

# List all topics
bin\windows\kafka-topics.bat --bootstrap-server localhost:9092 --list

# Topic details
bin\windows\kafka-topics.bat --bootstrap-server localhost:9092 --describe --topic trading.market_data.raw

# Consumer group status
bin\windows\kafka-consumer-groups.bat --bootstrap-server localhost:9092 --list
```

### Application Testing

**Python Test Script:**
```python
#!/usr/bin/env python3
# test_kafka_connection.py

from kafka import KafkaProducer, KafkaConsumer
import json
import time
import threading

def test_producer():
    producer = KafkaProducer(
        bootstrap_servers=['localhost:9092'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

    test_message = {
        "symbol": "NIFTY50",
        "price": 19500.75,
        "timestamp": time.time(),
        "volume": 1000
    }

    try:
        future = producer.send('trading.market_data.raw', test_message)
        record_metadata = future.get(timeout=10)
        print(f"Message sent to {record_metadata.topic} partition {record_metadata.partition}")
        return True
    except Exception as e:
        print(f"Producer error: {e}")
        return False
    finally:
        producer.close()

def test_consumer():
    consumer = KafkaConsumer(
        'trading.market_data.raw',
        bootstrap_servers=['localhost:9092'],
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        consumer_timeout_ms=5000,
        auto_offset_reset='earliest'
    )

    try:
        for message in consumer:
            print(f"Received: {message.value}")
            break
        return True
    except Exception as e:
        print(f"Consumer error: {e}")
        return False
    finally:
        consumer.close()

if __name__ == "__main__":
    print("Testing Kafka connection...")

    # Test producer
    print("1. Testing producer...")
    if test_producer():
        print("   Producer test: PASSED")
    else:
        print("   Producer test: FAILED")

    # Wait a moment
    time.sleep(2)

    # Test consumer
    print("2. Testing consumer...")
    if test_consumer():
        print("   Consumer test: PASSED")
    else:
        print("   Consumer test: FAILED")

    print("Testing complete.")
```

---

## Troubleshooting

### Common Issues

#### 1. "The input line is too long" Error
**Cause:** Windows command line path length limitation.
**Solution:**
- Move Kafka to `C:\kafka` instead of long nested paths
- Use PowerShell instead of cmd
- Create symbolic link: `mklink /D kafka "C:\long\path\to\kafka"`

#### 2. "controller.quorum.voters is not set" Error
**Cause:** Missing KRaft configuration.
**Solution:**
Add to `server.properties`:
```properties
controller.quorum.voters=1@localhost:9093
```

#### 3. Connection Refused Error
**Cause:** Kafka server not running or wrong port.
**Solution:**
- Verify Kafka is running: Check for "Kafka Server started" in logs
- Check port availability: `netstat -an | findstr 9092`
- Verify listeners configuration

#### 4. Topic Creation Fails
**Cause:** Insufficient permissions or cluster not ready.
**Solution:**
- Wait for cluster to be fully started
- Check logs for errors
- Verify bootstrap servers configuration

#### 5. High Memory Usage
**Cause:** Default JVM heap settings.
**Solution:**
Set environment variables:
```bash
set KAFKA_HEAP_OPTS=-Xmx1G -Xms1G
```

### Log Analysis

**Important log locations:**
- Kafka logs: `C:\kafka\kafka_2.13-4.1.0\logs\`
- Application logs: Check your application's log directory

**Key log messages to monitor:**
- `Kafka Server started` - Successful startup
- `Awaiting socket connections` - Server ready
- `ERROR` level messages - Issues requiring attention

---

## Best Practices

### Development

1. **Resource Management:**
   - Allocate at least 4GB RAM for Kafka
   - Use SSD storage for better performance
   - Monitor disk space usage

2. **Topic Design:**
   - Use descriptive topic names
   - Plan partition strategy based on throughput needs
   - Set appropriate retention policies

3. **Configuration:**
   - Use environment variables for configuration
   - Keep separate configs for dev/staging/prod
   - Enable logging for troubleshooting

### Production

1. **High Availability:**
   - Use at least 3 broker cluster
   - Set replication factor to 3
   - Configure proper ISR (In-Sync Replicas)

2. **Security:**
   - Enable SSL/SASL authentication
   - Use network segmentation
   - Regular security updates

3. **Monitoring:**
   - Monitor broker health
   - Track topic throughput and lag
   - Set up alerts for critical metrics

4. **Backup and Recovery:**
   - Regular topic snapshots
   - Disaster recovery procedures
   - Test restoration processes

### Performance Optimization

1. **Producer Settings:**
   ```properties
   acks=1  # For better throughput (vs acks=all)
   batch.size=16384
   linger.ms=5
   compression.type=snappy
   ```

2. **Consumer Settings:**
   ```properties
   fetch.min.bytes=1024
   fetch.max.wait.ms=500
   max.partition.fetch.bytes=1048576
   ```

3. **Broker Settings:**
   ```properties
   num.network.threads=8
   num.io.threads=16
   socket.send.buffer.bytes=102400
   socket.receive.buffer.bytes=102400
   ```

---

## Integration with Trading Application

### Environment Configuration

**Local Development (.env):**
```env
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_SECURITY_PROTOCOL=PLAINTEXT
KAFKA_AUTO_OFFSET_RESET=earliest
KAFKA_ENABLE_AUTO_COMMIT=true
```

**Production (.env.production):**
```env
KAFKA_BOOTSTRAP_SERVERS=your-kafka-cluster:9092
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=your-username
KAFKA_SASL_PASSWORD=your-password
KAFKA_AUTO_OFFSET_RESET=latest
KAFKA_ENABLE_AUTO_COMMIT=false
```

### Application Startup

The trading application should:
1. Verify Kafka connectivity on startup
2. Create topics if they don't exist
3. Set up producers and consumers
4. Implement proper error handling and retries

---

## Conclusion

This guide provides a complete setup for Kafka in both development and production environments. Choose the deployment option that best fits your infrastructure requirements and follow the best practices for optimal performance and reliability.

For additional support, refer to:
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Confluent Documentation](https://docs.confluent.io/)
- Project-specific troubleshooting in the main README