import csv
import json
import glob
import time
from kafka import KafkaProducer

KAFKA_BOOTSTRAP = 'localhost:9092'
TOPIC = 'pet_sales'
CSV_DIR = './исходные данные'

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP,
    value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8')
)

files = sorted(glob.glob(f'{CSV_DIR}/MOCK_DATA*.csv'))
total = 0

for filepath in files:
    print(f'Processing {filepath}...')
    with open(filepath, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            producer.send(TOPIC, value=dict(row))
            total += 1
            if total % 100 == 0:
                print(f'Sent {total} messages')
            time.sleep(0.01)

producer.flush()
print(f'Done. Total messages sent: {total}')
