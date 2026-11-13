FROM flink:1.19.1-scala_2.12-java11

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && ln -s /usr/bin/python3 /usr/local/bin/python \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir apache-flink==1.19.1 "psycopg[binary]==3.2.3"

ADD --chmod=644 https://repo1.maven.org/maven2/org/apache/flink/flink-connector-kafka/3.2.0-1.19/flink-connector-kafka-3.2.0-1.19.jar /opt/flink/lib/
ADD --chmod=644 https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.7.1/kafka-clients-3.7.1.jar /opt/flink/lib/

USER flink
