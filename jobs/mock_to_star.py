import hashlib
import json
import time
from datetime import date
from decimal import Decimal

import psycopg
from pyflink.common import RestartStrategies, SimpleStringSchema, Types, WatermarkStrategy
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import KafkaOffsetsInitializer, KafkaSource
from pyflink.datastream.functions import KeyedProcessFunction
from pyflink.datastream.state import ValueStateDescriptor

MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
DAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
SEP = "\x1f"
NULL = "\x00"

PG_HOST = "postgres"
PG_PORT = 5432
PG_DB = "bigdataflink"
PG_USER = "postgres"
PG_PASSWORD = "postgres"
BATCH_SIZE = 500
FLUSH_DELAY_MS = 10000


def h64(value):
    return int.from_bytes(hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest(), "big", signed=True)


def norm(value):
    return None if value == "" else value


def part(value):
    return NULL if value is None else str(value)


def parse_date(value):
    month, day, year = (int(x) for x in value.split("/"))
    return date(year, month, day)


def to_records(line):
    m = json.loads(line)
    sale_date = parse_date(m["sale_date"])

    customer = (
        m["customer_first_name"],
        m["customer_last_name"],
        m["customer_email"],
        m["customer_country"],
        norm(m["customer_postal_code"]),
        m["customer_pet_type"],
        m["customer_pet_name"],
        m["customer_pet_breed"],
    )
    seller = (
        m["seller_first_name"],
        m["seller_last_name"],
        m["seller_email"],
        m["seller_country"],
        norm(m["seller_postal_code"]),
    )
    product = (
        m["product_name"],
        m["product_category"],
        m["pet_category"],
        m["product_brand"],
        m["product_color"],
        m["product_size"],
        m["product_material"],
        m["product_description"],
        Decimal(m["product_price"]),
        Decimal(m["product_weight"]),
        Decimal(m["product_rating"]),
        int(m["product_reviews"]),
        parse_date(m["product_release_date"]),
        parse_date(m["product_expiry_date"]),
    )
    store = (
        m["store_name"],
        m["store_location"],
        m["store_city"],
        norm(m["store_state"]),
        m["store_country"],
        m["store_phone"],
        m["store_email"],
    )
    supplier = (
        m["supplier_name"],
        m["supplier_contact"],
        m["supplier_email"],
        m["supplier_phone"],
        m["supplier_address"],
        m["supplier_city"],
        m["supplier_country"],
    )

    weekday = sale_date.weekday()
    date_row = (
        sale_date,
        sale_date.day,
        sale_date.month,
        MONTHS[sale_date.month - 1],
        (sale_date.month - 1) // 3 + 1,
        sale_date.year,
        weekday,
        DAYS[weekday],
        int(weekday >= 5),
    )
    customer_key = h64("dim_customer" + SEP + SEP.join(part(x) for x in customer))
    seller_key = h64("dim_seller" + SEP + SEP.join(part(x) for x in seller))
    product_key = h64("dim_product" + SEP + SEP.join(part(x) for x in product))
    store_key = h64("dim_store" + SEP + SEP.join(part(x) for x in store))
    supplier_key = h64("dim_supplier" + SEP + SEP.join(part(x) for x in supplier))
    sale_key = h64("fact_sales" + SEP + json.dumps(m, sort_keys=True, ensure_ascii=False))

    yield {"table": "dim_date", "pk": h64("dim_date" + SEP + str(sale_date)), "row": date_row}
    yield {"table": "dim_customer", "pk": customer_key, "row": (customer_key,) + customer}
    yield {"table": "dim_seller", "pk": seller_key, "row": (seller_key,) + seller}
    yield {"table": "dim_product", "pk": product_key, "row": (product_key,) + product}
    yield {"table": "dim_store", "pk": store_key, "row": (store_key,) + store}
    yield {"table": "dim_supplier", "pk": supplier_key, "row": (supplier_key,) + supplier}
    yield {
        "table": "fact_sales",
        "pk": sale_key,
        "row": (
            sale_key,
            sale_date,
            customer_key,
            seller_key,
            product_key,
            store_key,
            supplier_key,
            int(m["sale_quantity"]),
            Decimal(m["sale_total_price"]),
        ),
    }


class TableWriter(KeyedProcessFunction):
    def __init__(self):
        self.seen = None
        self.conn = None
        self.cursor = None
        self.rows = []
        self.timer_registered = False

    def open(self, runtime_context):
        self.seen = runtime_context.get_state(ValueStateDescriptor("seen", Types.BOOLEAN()))
        self.conn = psycopg.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASSWORD,
        )
        self.cursor = self.conn.cursor()

    def commit_rows(self):
        self.conn.commit()
        self.rows = []
        self.timer_registered = False

    def run_flush(self):
        for _ in range(30):
            try:
                self.flush()
                return
            except psycopg.errors.ForeignKeyViolation:
                self.conn.rollback()
                time.sleep(1)
        raise RuntimeError("referenced dimensions are not loaded yet")

    def process_element(self, value, ctx):
        if self.seen.value():
            return
        self.seen.update(True)
        self.rows.append(value["row"])
        if len(self.rows) >= BATCH_SIZE:
            self.run_flush()
            return
        if not self.timer_registered:
            service = ctx.timer_service()
            service.register_processing_time_timer(service.current_processing_time() + FLUSH_DELAY_MS)
            self.timer_registered = True
        yield from ()

    def on_timer(self, timestamp, ctx):
        self.run_flush()
        yield from ()

    def flush(self):
        raise NotImplementedError


class DimDateWriter(TableWriter):
    def flush(self):
        if self.rows:
            self.cursor.executemany(
                "INSERT INTO dim_date VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (date_key) DO NOTHING",
                self.rows,
            )
            self.commit_rows()


class DimCustomerWriter(TableWriter):
    def flush(self):
        if self.rows:
            self.cursor.executemany(
                "INSERT INTO dim_customer VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (customer_key) DO NOTHING",
                self.rows,
            )
            self.commit_rows()


class DimSellerWriter(TableWriter):
    def flush(self):
        if self.rows:
            self.cursor.executemany(
                "INSERT INTO dim_seller VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (seller_key) DO NOTHING",
                self.rows,
            )
            self.commit_rows()


class DimProductWriter(TableWriter):
    def flush(self):
        if self.rows:
            self.cursor.executemany(
                "INSERT INTO dim_product VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (product_key) DO NOTHING",
                self.rows,
            )
            self.commit_rows()


class DimStoreWriter(TableWriter):
    def flush(self):
        if self.rows:
            self.cursor.executemany(
                "INSERT INTO dim_store VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (store_key) DO NOTHING",
                self.rows,
            )
            self.commit_rows()


class DimSupplierWriter(TableWriter):
    def flush(self):
        if self.rows:
            self.cursor.executemany(
                "INSERT INTO dim_supplier VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (supplier_key) DO NOTHING",
                self.rows,
            )
            self.commit_rows()


class FactSalesWriter(TableWriter):
    def flush(self):
        if self.rows:
            self.cursor.executemany(
                "INSERT INTO fact_sales VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (sale_key) DO NOTHING",
                self.rows,
            )
            self.commit_rows()


WRITERS = {
    "dim_date": DimDateWriter,
    "dim_customer": DimCustomerWriter,
    "dim_seller": DimSellerWriter,
    "dim_product": DimProductWriter,
    "dim_store": DimStoreWriter,
    "dim_supplier": DimSupplierWriter,
    "fact_sales": FactSalesWriter,
}

env = StreamExecutionEnvironment.get_execution_environment()
env.set_parallelism(1)
env.enable_checkpointing(30000)
env.set_restart_strategy(RestartStrategies.fixed_delay_restart(10, 10000))

source = (
    KafkaSource.builder()
    .set_bootstrap_servers("kafka:9092")
    .set_topics("mock_data")
    .set_group_id("mock_to_star")
    .set_starting_offsets(KafkaOffsetsInitializer.earliest())
    .set_value_only_deserializer(SimpleStringSchema())
    .build()
)

records = env.from_source(source, WatermarkStrategy.no_watermarks(), "mock_data").flat_map(to_records)

for table, writer in WRITERS.items():
    records.filter(lambda r, t=table: r["table"] == t).key_by(
        lambda r: r["pk"], key_type=Types.LONG()
    ).process(writer())

env.execute("mock_to_star")
