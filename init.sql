CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id INT PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    age INT,
    email VARCHAR(200),
    country VARCHAR(100),
    postal_code VARCHAR(50),
    pet_type VARCHAR(50),
    pet_name VARCHAR(100),
    pet_breed VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS dim_seller (
    seller_id INT PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(200),
    country VARCHAR(100),
    postal_code VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_id INT PRIMARY KEY,
    name VARCHAR(200),
    category VARCHAR(100),
    price DECIMAL(10,2),
    quantity INT,
    weight DECIMAL(10,2),
    color VARCHAR(50),
    size VARCHAR(50),
    brand VARCHAR(100),
    material VARCHAR(100),
    description TEXT,
    rating DECIMAL(3,1),
    reviews INT,
    release_date DATE,
    expiry_date DATE,
    pet_category VARCHAR(50),
    supplier_name VARCHAR(200),
    supplier_contact VARCHAR(200),
    supplier_email VARCHAR(200),
    supplier_phone VARCHAR(50),
    supplier_address VARCHAR(200),
    supplier_city VARCHAR(100),
    supplier_country VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS dim_store (
    store_id INT PRIMARY KEY,
    name VARCHAR(200),
    location VARCHAR(200),
    city VARCHAR(100),
    state VARCHAR(50),
    country VARCHAR(100),
    phone VARCHAR(50),
    email VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_id SERIAL PRIMARY KEY,
    full_date DATE UNIQUE,
    day INT,
    month INT,
    year INT,
    quarter INT
);

CREATE TABLE IF NOT EXISTS fact_sales (
    sale_id SERIAL PRIMARY KEY,
    source_sale_id INT,
    customer_id INT REFERENCES dim_customer(customer_id),
    seller_id INT REFERENCES dim_seller(seller_id),
    product_id INT REFERENCES dim_product(product_id),
    store_id INT REFERENCES dim_store(store_id),
    date_id INT REFERENCES dim_date(date_id),
    quantity INT,
    total_price DECIMAL(10,2)
);
