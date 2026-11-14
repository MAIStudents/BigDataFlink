import csv
import glob
import json
import time

from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import NoBrokersAvailable, TopicAlreadyExistsError

BOOTSTRAP_SERVERS = "kafka:9092"
TOPIC = "mock_data"

admin = None
for _ in range(60):
    try:
        admin = KafkaAdminClient(bootstrap_servers=BOOTSTRAP_SERVERS)
        break
    except NoBrokersAvailable:
        time.sleep(2)
if admin is None:
    raise RuntimeError("kafka is not available")

try:
    admin.create_topics([NewTopic(name=TOPIC, num_partitions=3, replication_factor=1)])
except TopicAlreadyExistsError:
    pass
admin.close()

producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP_SERVERS,
    key_serializer=str.encode,
    value_serializer=lambda row: json.dumps(row, ensure_ascii=False).encode("utf-8"),
    acks="all",
    retries=5,
)

futures = []
for path in sorted(glob.glob("/data/MOCK_DATA*.csv")):
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            futures.append(producer.send(TOPIC, key=str(len(futures)), value=row))

producer.flush()
for future in futures:
    future.get(timeout=60)
print("sent messages: " + str(len(futures)))
