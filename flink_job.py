import json
import psycopg2
from datetime import datetime
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import KafkaSource, KafkaOffsetsInitializer
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common import WatermarkStrategy
from pyflink.datastream.functions import MapFunction, RichMapFunction
from pyflink.common.typeinfo import Types

KAFKA_BOOTSTRAP = 'kafka:29092'
TOPIC = 'pet_sales'
PG_CONN = {
    'host': 'postgres',
    'port': 5432,
    'dbname': 'petstore',
    'user': 'flink',
    'password': 'flink123'
}


def parse_date(date_str):
    if not date_str:
        return None
    for fmt in ('%m/%d/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


class StarSchemaWriter(RichMapFunction):
    def __init__(self):
        self.conn = None

    def open(self, runtime_context):
        self.conn = psycopg2.connect(**PG_CONN)
        self.conn.autocommit = False

    def close(self):
        if self.conn:
            self.conn.close()

    def _upsert_customer(self, cur, row):
        cur.execute("""
            INSERT INTO dim_customer (customer_id, first_name, last_name, age, email, country, postal_code, pet_type, pet_name, pet_breed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (customer_id) DO NOTHING
            RETURNING customer_id
        """, (
            int(row['sale_customer_id']),
            row.get('customer_first_name'), row.get('customer_last_name'),
            int(row['customer_age']) if row.get('customer_age') else None,
            row.get('customer_email'), row.get('customer_country'),
            row.get('customer_postal_code'), row.get('customer_pet_type'),
            row.get('customer_pet_name'), row.get('customer_pet_breed')
        ))
        result = cur.fetchone()
        return int(row['sale_customer_id'])

    def _upsert_seller(self, cur, row):
        cur.execute("""
            INSERT INTO dim_seller (seller_id, first_name, last_name, email, country, postal_code)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (seller_id) DO NOTHING
        """, (
            int(row['sale_seller_id']),
            row.get('seller_first_name'), row.get('seller_last_name'),
            row.get('seller_email'), row.get('seller_country'),
            row.get('seller_postal_code')
        ))
        return int(row['sale_seller_id'])

    def _upsert_product(self, cur, row):
        cur.execute("""
            INSERT INTO dim_product (product_id, name, category, price, quantity, weight, color, size, brand, material,
                description, rating, reviews, release_date, expiry_date, pet_category,
                supplier_name, supplier_contact, supplier_email, supplier_phone,
                supplier_address, supplier_city, supplier_country)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (product_id) DO NOTHING
        """, (
            int(row['sale_product_id']),
            row.get('product_name'), row.get('product_category'),
            float(row['product_price']) if row.get('product_price') else None,
            int(row['product_quantity']) if row.get('product_quantity') else None,
            float(row['product_weight']) if row.get('product_weight') else None,
            row.get('product_color'), row.get('product_size'),
            row.get('product_brand'), row.get('product_material'),
            row.get('product_description'),
            float(row['product_rating']) if row.get('product_rating') else None,
            int(row['product_reviews']) if row.get('product_reviews') else None,
            parse_date(row.get('product_release_date')),
            parse_date(row.get('product_expiry_date')),
            row.get('pet_category'),
            row.get('supplier_name'), row.get('supplier_contact'),
            row.get('supplier_email'), row.get('supplier_phone'),
            row.get('supplier_address'), row.get('supplier_city'),
            row.get('supplier_country')
        ))
        return int(row['sale_product_id'])

    def _upsert_store(self, cur, row):
        cur.execute("""
            INSERT INTO dim_store (store_id, name, location, city, state, country, phone, email)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (store_id) DO NOTHING
        """, (
            int(row['id']),
            row.get('store_name'), row.get('store_location'),
            row.get('store_city'), row.get('store_state'),
            row.get('store_country'), row.get('store_phone'),
            row.get('store_email')
        ))
        return int(row['id'])

    def _upsert_date(self, cur, date_str):
        d = parse_date(date_str)
        if not d:
            return None
        cur.execute("""
            INSERT INTO dim_date (full_date, day, month, year, quarter)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (full_date) DO NOTHING
        """, (d, d.day, d.month, d.year, (d.month - 1) // 3 + 1))
        cur.execute("SELECT date_id FROM dim_date WHERE full_date = %s", (d,))
        return cur.fetchone()[0]

    def map(self, value):
        try:
            row = json.loads(value)
            cur = self.conn.cursor()

            customer_id = self._upsert_customer(cur, row)
            seller_id = self._upsert_seller(cur, row)
            product_id = self._upsert_product(cur, row)
            store_id = self._upsert_store(cur, row)
            date_id = self._upsert_date(cur, row.get('sale_date'))

            cur.execute("""
                INSERT INTO fact_sales (source_sale_id, customer_id, seller_id, product_id, store_id, date_id, quantity, total_price)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                int(row['id']),
                customer_id, seller_id, product_id, store_id, date_id,
                int(row['sale_quantity']) if row.get('sale_quantity') else None,
                float(row['sale_total_price']) if row.get('sale_total_price') else None
            ))

            self.conn.commit()
            cur.close()
        except Exception as e:
            self.conn.rollback()
            print(f"Error processing record: {e}")
        return value


def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)

    source = KafkaSource.builder() \
        .set_bootstrap_servers(KAFKA_BOOTSTRAP) \
        .set_topics(TOPIC) \
        .set_group_id('flink-star-schema') \
        .set_starting_offsets(KafkaOffsetsInitializer.earliest()) \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .build()

    stream = env.from_source(source, WatermarkStrategy.no_watermarks(), 'Kafka Source')
    stream.map(StarSchemaWriter(), output_type=Types.STRING())

    env.execute('Pet Sales Star Schema ETL')


if __name__ == '__main__':
    main()
