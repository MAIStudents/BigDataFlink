package com.lab3;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.sink.RichSinkFunction;
import org.apache.flink.configuration.Configuration;

import java.sql.*;

public class FlinkJob {
    public static void main(String[] args) throws Exception {
        final StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        KafkaSource<String> source = KafkaSource.<String>builder()
                .setBootstrapServers("kafka:29092")
                .setTopics("sales_topic")
                .setGroupId("flink-group")
                .setStartingOffsets(OffsetsInitializer.earliest())
                .setValueOnlyDeserializer(new SimpleStringSchema())
                .build();

        env.fromSource(source, WatermarkStrategy.noWatermarks(), "Kafka Source")
           .addSink(new PostgresStarSchemaSink());

        env.execute("Flink Kafka to Postgres Star Schema");
    }

    public static class PostgresStarSchemaSink extends RichSinkFunction<String> {
        private Connection connection;
        private transient ObjectMapper mapper;

        @Override
        public void open(Configuration parameters) throws Exception {
            super.open(parameters);
            mapper = new ObjectMapper();
            String url = "jdbc:postgresql://bigdata:5433/bigdata";
            String user = "bigdata";
            String password = "bigdata";

            int attempts = 10;
            while (attempts > 0) {
                try {
                    connection = DriverManager.getConnection("jdbc:postgresql://postgres_db:5432/bigdata", "bigdata", "bigdata");
                    break;
                } catch (SQLException e) {
                    attempts--;
                    Thread.sleep(3000);
                }
            }
        }

        @Override
        public void invoke(String value, Context context) throws Exception {
            JsonNode node = mapper.readTree(value);
            connection.setAutoCommit(false);

            try {
                int custGeoId = getOrCreateGeography(
                        node.get("cust_country").asText(),
                        node.get("cust_city").asText(),
                        node.get("cust_state").asText(),
                        node.get("cust_postalCode").asText()
                );

                int sellGeoId = getOrCreateGeography(
                        node.get("sell_country").asText(),
                        node.get("sell_city").asText(),
                        node.get("sell_state").asText(),
                        node.get("sell_postalCode").asText()
                );

                int suppGeoId = getOrCreateGeography(
                        node.get("supp_country").asText(),
                        node.get("supp_city").asText(),
                        node.get("supp_state").asText(),
                        node.get("supp_postalCode").asText()
                );

                int storeGeoId = getOrCreateGeography(
                        node.get("store_country").asText(),
                        node.get("store_city").asText(),
                        node.get("store_state").asText(),
                        node.get("store_postalCode").asText()
                );

                int customerId = getOrCreateCustomer(
                        node.get("cust_firstName").asText(),
                        node.get("cust_lastName").asText(),
                        node.get("cust_age").asInt(),
                        node.get("cust_email").asText(),
                        custGeoId,
                        node.get("cust_petType").asText(),
                        node.get("cust_petName").asText(),
                        node.get("cust_petBreed").asText()
                );

                int sellerId = getOrCreateSeller(
                        node.get("sell_firstName").asText(),
                        node.get("sell_lastName").asText(),
                        node.get("sell_email").asText(),
                        sellGeoId
                );

                int supplierId = getOrCreateSupplier(
                        node.get("supp_name").asText(),
                        node.get("supp_contactName").asText(),
                        node.get("supp_email").asText(),
                        node.get("supp_phone").asText(),
                        suppGeoId
                );

                int storeId = getOrCreateStore(
                        node.get("store_name").asText(),
                        node.get("store_locationAddress").asText(),
                        node.get("store_phone").asText(),
                        node.get("store_email").asText(),
                        storeGeoId
                );

                int categoryId = getOrCreateCategory(
                        node.get("categoryName").asText(),
                        node.get("petCategory").asText()
                );

                int productId = getOrCreateProduct(
                        node.get("prod_name").asText(),
                        categoryId,
                        node.get("brand").asText(),
                        node.get("price").asDouble(),
                        node.get("weight").asText(),
                        node.get("color").asText(),
                        node.get("size").asText(),
                        node.get("material").asText(),
                        node.get("description").asText(),
                        node.get("rating").asDouble(),
                        Date.valueOf(node.get("releaseDate").asText()),
                        Date.valueOf(node.get("expiryDate").asText())
                );

                try (PreparedStatement ps = connection.prepareStatement(
                        "INSERT INTO FactSales (saleDate, customerId, sellerId, productId, storeId, supplierId, quantity, totalPrice) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                )) {
                    ps.setDate(1, Date.valueOf(node.get("saleDate").asText()));
                    ps.setInt(2, customerId);
                    ps.setInt(3, sellerId);
                    ps.setInt(4, productId);
                    ps.setInt(5, storeId);
                    ps.setInt(6, supplierId);
                    ps.setInt(7, node.get("quantity").asInt());
                    ps.setDouble(8, node.get("totalPrice").asDouble());
                    ps.executeUpdate();
                }

                connection.commit();
            } catch (Exception e) {
                connection.rollback();
                throw e;
            }
        }

        private int getOrCreateGeography(String country, String city, String state, String postalCode) throws SQLException {
            String sql = "INSERT INTO DimGeography (country, city, state, postalCode) VALUES (?, ?, ?, ?) " +
                         "ON CONFLICT (country, city, state, postalCode) DO UPDATE SET country=EXCLUDED.country RETURNING geoId";
            try (PreparedStatement ps = connection.prepareStatement(sql)) {
                ps.setString(1, country);
                ps.setString(2, city);
                ps.setString(3, state);
                ps.setString(4, postalCode);
                try (ResultSet rs = ps.executeQuery()) {
                    if (rs.next()) return rs.getInt(1);
                }
            }
            throw new SQLException("Failed to get or create Geography record");
        }

        private int getOrCreateCustomer(String fName, String lName, int age, String email, int geoId, String petType, String petName, String petBreed) throws SQLException {
            String sql = "INSERT INTO DimCustomers (firstName, lastName, age, email, geoId, petType, petName, petBreed) VALUES (?, ?, ?, ?, ?, ?, ?, ?) " +
                         "ON CONFLICT (email) DO UPDATE SET firstName=EXCLUDED.firstName RETURNING customerId";
            try (PreparedStatement ps = connection.prepareStatement(sql)) {
                ps.setString(1, fName);
                ps.setString(2, lName);
                ps.setInt(3, age);
                ps.setString(4, email);
                ps.setInt(5, geoId);
                ps.setString(6, petType);
                ps.setString(7, petName);
                ps.setString(8, petBreed);
                try (ResultSet rs = ps.executeQuery()) {
                    if (rs.next()) return rs.getInt(1);
                }
            }
            throw new SQLException("Failed to handle Customer record");
        }

        private int getOrCreateSeller(String fName, String lName, String email, int geoId) throws SQLException {
            String sql = "INSERT INTO DimSellers (firstName, lastName, email, geoId) VALUES (?, ?, ?, ?) " +
                         "ON CONFLICT (email) DO UPDATE SET firstName=EXCLUDED.firstName RETURNING sellerId";
            try (PreparedStatement ps = connection.prepareStatement(sql)) {
                ps.setString(1, fName);
                ps.setString(2, lName);
                ps.setString(3, email);
                ps.setInt(4, geoId);
                try (ResultSet rs = ps.executeQuery()) {
                    if (rs.next()) return rs.getInt(1);
                }
            }
            throw new SQLException("Failed to handle Seller record");
        }

        private int getOrCreateSupplier(String name, String contact, String email, String phone, int geoId) throws SQLException {
            String sql = "INSERT INTO DimSuppliers (name, contactName, email, phone, geoId) VALUES (?, ?, ?, ?, ?) " +
                         "ON CONFLICT (email) DO UPDATE SET name=EXCLUDED.name RETURNING supplierId";
            try (PreparedStatement ps = connection.prepareStatement(sql)) {
                ps.setString(1, name);
                ps.setString(2, contact);
                ps.setString(3, email);
                ps.setString(4, phone);
                ps.setInt(5, geoId);
                try (ResultSet rs = ps.executeQuery()) {
                    if (rs.next()) return rs.getInt(1);
                }
            }
            throw new SQLException("Failed to handle Supplier record");
        }

        private int getOrCreateStore(String name, String address, String phone, String email, int geoId) throws SQLException {
            String sql = "INSERT INTO DimStores (name, locationAddress, phone, email, geoId) VALUES (?, ?, ?, ?, ?) " +
                         "ON CONFLICT (name, locationAddress) DO UPDATE SET phone=EXCLUDED.phone RETURNING storeId";
            try (PreparedStatement ps = connection.prepareStatement(sql)) {
                ps.setString(1, name);
                ps.setString(2, address);
                ps.setString(3, phone);
                ps.setString(4, email);
                ps.setInt(5, geoId);
                try (ResultSet rs = ps.executeQuery()) {
                    if (rs.next()) return rs.getInt(1);
                }
            }
            throw new SQLException("Failed to handle Store record");
        }

        private int getOrCreateCategory(String catName, String petCat) throws SQLException {
            String sql = "INSERT INTO DimProductCategories (categoryName, petCategory) VALUES (?, ?) " +
                         "ON CONFLICT (categoryName, petCategory) DO UPDATE SET categoryName=EXCLUDED.categoryName RETURNING categoryId";
            try (PreparedStatement ps = connection.prepareStatement(sql)) {
                ps.setString(1, catName);
                ps.setString(2, petCat);
                try (ResultSet rs = ps.executeQuery()) {
                    if (rs.next()) return rs.getInt(1);
                }
            }
            throw new SQLException("Failed to handle Category record");
        }

        private int getOrCreateProduct(String name, int catId, String brand, double price, String weight, String color, String size, String mat, String desc, double rating, Date relDate, Date expDate) throws SQLException {
            String sql = "INSERT INTO DimProducts (name, categoryId, brand, price, weight, color, size, material, description, rating, releaseDate, expiryDate) " +
                         "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (name, brand) DO UPDATE SET price=EXCLUDED.price RETURNING productId";
            try (PreparedStatement ps = connection.prepareStatement(sql)) {
                ps.setString(1, name);
                ps.setInt(2, catId);
                ps.setString(3, brand);
                ps.setDouble(4, price);
                ps.setString(5, weight);
                ps.setString(6, color);
                ps.setString(7, size);
                ps.setString(8, mat);
                ps.setString(9, desc);
                ps.setDouble(10, rating);
                ps.setDate(11, relDate);
                ps.setDate(12, expDate);
                try (ResultSet rs = ps.executeQuery()) {
                    if (rs.next()) return rs.getInt(1);
                }
            }
            throw new SQLException("Failed to handle Product record");
        }

        @Override
        public void close() throws Exception {
            if (connection != null) {
                connection.close();
            }
            super.close();
        }
    }
}
