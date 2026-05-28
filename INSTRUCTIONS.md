# Инструкция по запуску лабораторной работы №3

## Требования
- Docker и Docker Compose
- Python 3.8+

## Шаги запуска

### 1. Запустить инфраструктуру

```bash
docker-compose up -d
```

Подождать ~30 секунд, пока все сервисы поднимутся.

### 2. Установить зависимости Python

```bash
pip install -r requirements.txt
```

### 3. Запустить Kafka Producer

Отправляет все строки из CSV-файлов в топик `pet_sales`:

```bash
python kafka_producer.py
```

### 4. Запустить Flink Job

**Вариант A — локально (для разработки):**

```bash
python flink_job.py
```

**Вариант B — через Flink Web UI (рекомендуется):**

1. Открыть http://localhost:8081
2. Упаковать job в JAR или использовать PyFlink:

```bash
# Скопировать job в контейнер jobmanager
docker cp flink_job.py bdlab3-jobmanager-1:/opt/flink/

# Зайти в контейнер
docker exec -it bdlab3-jobmanager-1 bash

# Установить зависимости внутри контейнера
pip install psycopg2-binary apache-flink

# Запустить job
python /opt/flink/flink_job.py
```

### 5. Проверить данные в PostgreSQL

```bash
docker exec -it bdlab3-postgres-1 psql -U flink -d petstore
```

```sql
SELECT COUNT(*) FROM fact_sales;
SELECT COUNT(*) FROM dim_customer;
SELECT COUNT(*) FROM dim_product;
SELECT COUNT(*) FROM dim_seller;
SELECT COUNT(*) FROM dim_store;
SELECT COUNT(*) FROM dim_date;

-- Пример аналитического запроса
SELECT 
    dd.year, dd.month,
    SUM(fs.total_price) AS total_revenue,
    COUNT(*) AS sales_count
FROM fact_sales fs
JOIN dim_date dd ON fs.date_id = dd.date_id
GROUP BY dd.year, dd.month
ORDER BY dd.year, dd.month;
```

## Архитектура модели звезда

```
                    dim_customer
                         |
dim_date --- fact_sales --- dim_seller
                         |
                    dim_product
                         |
                    dim_store
```

### Таблицы фактов
- **fact_sales** — продажи (количество, сумма, ссылки на измерения)

### Таблицы измерений
- **dim_customer** — покупатели с информацией о питомцах
- **dim_seller** — продавцы
- **dim_product** — товары с информацией о поставщиках
- **dim_store** — магазины
- **dim_date** — даты (день, месяц, год, квартал)

## Остановка

```bash
docker-compose down -v
```
