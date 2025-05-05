# BigDataFlink

Соколова ВД М8О-301Б-22

Анализ больших данных - лабораторная работа №3 - Streaming processing с помощью Flink

Инструкция, как запускать Flink-джобу:

docker-compose build
docker-compose up -d zookeeper kafka postgres
docker-compose exec kafka kafka-topics --create --bootstrap-server kafka:9092 --replication-factor 1 --partitions 1 --topic raw-mock
docker-compose up -d kafka-producer
docker-compose up -d jobmanager taskmanager
docker-compose up -d flink-job

Далее можно открыть http://localhost:8081 и убедиться, что задание в состоянии RUNNING и колонке Records Sent отмечается, сколько отправляется. А также в логах TaskManadger будут строки вида ">>> GOT ROW: …"

А убедиться, что данные попали в базу можно просто зайдя в dbeaver 
      POSTGRES_DB: lab3
      POSTGRES_USER: labuser
      POSTGRES_PASSWORD: labpass

Данные отправляются в кафку с помощью продюсера.