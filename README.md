# BigDataFlink

Анализ больших данных - лабораторная работа №3 - Streaming processing с помощью Flink.

Выполнил: Крючков Артемий Владимирович, группа М8О-205СВ-25.

## Как запустить лабораторную работу

Требуется установленный Docker (при первой сборке нужен интернет: качаются образы, PyFlink и коннектор Kafka с Maven Central).

Из корня репозитория:

```bash
docker compose up -d --build
```

При старте автоматически выполняется:

1. Поднимается PostgreSQL 17 (порт на хосте 5434). Выполняется DDL модели звезда: `fact_sales` + 6 измерений с первичными и внешними ключами.
2. Поднимается Kafka 3.9 (KRaft, без Zookeeper) с топиком `mock_data` (3 партиции).
3. Поднимается кластер Apache Flink 1.19: JobManager (Web UI на http://localhost:8081) и TaskManager.
4. Контейнер `submitter` отправляет Flink-джобу `jobs/mock_to_star.py` в кластер (detached) и завершается.
5. Контейнер `producer` читает все 10 файлов `исходные данные/MOCK_DATA(*).csv`, каждую строку преобразует в JSON и отправляет сообщением в Kafka-топик `mock_data` (10000 сообщений).
6. Flink-джоба в режиме streaming читает топик, трансформирует каждую запись в строку измерения или факта и пишет в PostgreSQL. Джоба продолжает работать и ждёт новые сообщения.

Полная загрузка 10000 записей занимает около 5 минут. Прогресс виден в Flink Web UI (http://localhost:8081) или в DBeaver (счётчик `fact_sales`).

Ожидаемые статусы контейнеров (`docker compose ps -a`): `postgres`, `kafka`, `jobmanager`, `taskmanager` — Up; `producer` и `submitter` — Exited (0).

Повторная отправка данных в Kafka (джоба продолжает работать, дубликаты не создаются):

```bash
docker compose run --rm producer
```

Повторная отправка Flink-джобы в кластер:

```bash
docker compose run --rm submitter
```

## Подключение (DBeaver)

PostgreSQL:

| Параметр | Значение      |
| -------- | ------------- |
| Host     | localhost     |
| Port     | 5434          |
| Database | bigdataflink  |
| User     | postgres      |
| Password | postgres      |

Flink Web UI: http://localhost:8081 (джоба `mock_to_star` в статусе RUNNING).

## Проверка результата

Модель звезда в PostgreSQL: `fact_sales` + `dim_date`, `dim_customer`, `dim_seller`, `dim_product`, `dim_store`, `dim_supplier`. Суррогатные ключи назначает Flink как детерминированные 64-битные хеши полных наборов атрибутов; исходные `id`/`sale_*_id` в данных не уникальны, поэтому измерения строятся по полным наборам атрибутов. Вставки идемпотентны (`ON CONFLICT DO NOTHING`), джоба дедуплицирует записи через keyed state.

Контрольные значения:

```sql
SELECT count(*) FROM fact_sales;
SELECT sum(total_price) FROM fact_sales;
```

Ожидается: 10000, 2529852.12.

Наполнение измерений:

```sql
SELECT (SELECT count(*) FROM dim_date) AS dates,
       (SELECT count(*) FROM dim_customer) AS customers,
       (SELECT count(*) FROM dim_seller) AS sellers,
       (SELECT count(*) FROM dim_product) AS products,
       (SELECT count(*) FROM dim_store) AS stores,
       (SELECT count(*) FROM dim_supplier) AS suppliers;
```

Ожидается: 364, 10000, 10000, 10000, 10000, 10000.

Целостность внешних ключей (0 «висячих» ссылок):

```sql
SELECT count(*)
FROM fact_sales f
LEFT JOIN dim_date d ON f.date_key = d.date_key
LEFT JOIN dim_customer c ON f.customer_key = c.customer_key
LEFT JOIN dim_seller s ON f.seller_key = s.seller_key
LEFT JOIN dim_product p ON f.product_key = p.product_key
LEFT JOIN dim_store st ON f.store_key = st.store_key
LEFT JOIN dim_supplier sup ON f.supplier_key = sup.supplier_key
WHERE d.date_key IS NULL OR c.customer_key IS NULL OR s.seller_key IS NULL
   OR p.product_key IS NULL OR st.store_key IS NULL OR sup.supplier_key IS NULL;
```

Примеры запросов по звезде:

Выручка по категориям продуктов:

```sql
SELECT p.category, round(sum(f.total_price), 2) AS revenue, count(*) AS sales_cnt
FROM fact_sales f JOIN dim_product p ON f.product_key = p.product_key
GROUP BY p.category
ORDER BY revenue DESC;
```

Топ-10 клиентов по сумме покупок:

```sql
SELECT c.first_name, c.last_name, c.email, round(sum(f.total_price), 2) AS total
FROM fact_sales f JOIN dim_customer c ON f.customer_key = c.customer_key
GROUP BY c.customer_key, c.first_name, c.last_name, c.email
ORDER BY total DESC
LIMIT 10;
```

Месячные тренды продаж:

```sql
SELECT d.month, d.month_name, count(*) AS sales_cnt, round(sum(f.total_price), 2) AS revenue
FROM fact_sales f JOIN dim_date d ON f.date_key = d.date_key
GROUP BY d.month, d.month_name
ORDER BY d.month;
```

## Демонстрация streaming-режима

Джоба работает постоянно, поэтому новые сообщения из Kafka обрабатываются на лету. Можно отправить в топик произвольную строку JSON (например, копию существующей с изменённым `customer_email`) и через несколько секунд увидеть новую запись в PostgreSQL:

```bash
docker compose exec kafka /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 --topic mock_data
```

Затем вставить одну строку JSON и закрыть (Ctrl+C). Проверка:

```sql
SELECT count(*) FROM fact_sales;
SELECT * FROM dim_customer WHERE email = 'live.demo@flink.local';
```

## Управление

```bash
docker compose stop
docker compose down
docker compose down -v && docker compose up -d --build
```

`down -v` удаляет данные (включая Kafka) и запускает полную переинициализацию с нуля.

## Состав решения

| Файл                  | Назначение                                                                  |
| --------------------- | --------------------------------------------------------------------------- |
| `docker-compose.yml`  | PostgreSQL 17, Kafka 3.9 (KRaft), кластер Flink 1.19, автозапуск джобы и продюсера |
| `Dockerfile`          | Образ Flink 1.19 с PyFlink и коннектором Kafka                              |
| `init/01_ddl.sql`     | DDL модели звезда в PostgreSQL                                              |
| `producer/Dockerfile` | Образ приложения-источника данных                                           |
| `producer/produce.py` | CSV → JSON → отправка сообщений в Kafka-топик                               |
| `jobs/mock_to_star.py`| Flink-джоба (PyFlink): Kafka → трансформация в звезду → PostgreSQL          |

---

## Исходное задание

Анализ больших данных - лабораторная работа №3 - Streaming processing с помощью Flink

Одним из самых популярных фреймворков для работы со streaming processing является Apache Flink. Apache Flink - мощный фреймворк, который предлагает широкий набор функциональности для простого написания streaming processing.

Что необходимо сделать? 

Необходимо реализовать потоковую обработку данных с помощью Flink, который читает топик Kafka, трансформирует данные в режиме streaming в модель звезда и пишет результат в PostgreSQL. Данные в Kafka-топиках хранятся в формате json. Данные в топик kafka нужно отправлять самостоятельно, эмулируя источник данных.

Какие данные отправляются в Kafka?
 - Каждое сообщение в Kafka-топике - это строчка из csv файлов, преобразованная в формат json.

Какие данные отправляются в PostgreSQL?
 - Трансформированные данные в модель данных звезда.

![Лабораторная работа №3](https://github.com/user-attachments/assets/d3c1544d-3fe6-4c15-b673-9aa5d27dbd76)


Алгоритм:

1. Клонируете к себе этот репозиторий.
2. Устанавливаете инструмент для работы с запросами SQL (рекомендую DBeaver).
3. Устанавливаете базу данных PostgreSQL (рекомендую установку через docker).
4. Устанавливаете Apache Flink (рекомендую установку через Docker).
5. Устанавливаете Apache Kafka (рекомендую установку через Docker).
6. Скачиваете файлы с исходными данными mock_data( * ).csv, где ( * ) номера файлов. Всего 10 файлов, каждый по 1000 строк.
7. Реализуете приложение, которое каждую строчку из исходных csv-файлов преобразует в json и отправляет в виде сообщения в Kafka-топик.
8. Реализуете приложение на Flink, которое читает Kafka-топик, преобразует данные в модель звезда и сохраняет в PostgreSQL в режиме streaming.
9. Проверяете конечные данные в PostgreSQL.
10. Отправляете работу на проверку лаборантам.

Что должно быть результатом работы?

1. Репозиторий, в котором есть исходные данные mock_data().csv, где () номера файлов. Всего 10 файлов, каждый по 1000 строк.
2. Файл docker-compose.yml с установкой PostgreSQL, Flink, Kafka и запуском приложения, которое из файлов mock_data(*).csv создает сообщения json в Kafka.
3. Инструкция, как запускать Flink-джобу и приложение для отправки данных в Kafka для проверки лабораторной работы.
4. Код Apache Flink для трансформации данных в режиме streaming.
