FROM maven:3.8.5-openjdk-11

WORKDIR /app

COPY . .

RUN wget -qO- https://archive.apache.org/dist/flink/flink-1.18.1/flink-1.18.1-bin-scala_2.12.tgz | tar xvz -C /opt/
ENV PATH="/opt/flink-1.18.1/bin:${PATH}"