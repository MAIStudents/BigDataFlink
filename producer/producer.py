import glob
import os
import csv
import json
import time
import random
from datetime import datetime, timedelta
from kafka import KafkaProducer

TOPIC = "sales_topic"
BOOTSTRAP_SERVERS = ["kafka:29092"]

def generate_mock_csv_files():
    print("Проверка наличия mock-данных...")
    for i in range(1, 11):
        filename = f"mock_data_{i}.csv"
        if os.path.exists(filename):
            continue
        
        print(f"Генерация файла {filename}...")
        headers = [
            "saleDate", "quantity", "totalPrice",
            "cust_firstName", "cust_lastName", "cust_age", "cust_email", "cust_petType", "cust_petName", "cust_petBreed", "cust_country", "cust_city", "cust_state", "cust_postalCode",
            "sell_firstName", "sell_lastName", "sell_email", "sell_country", "sell_city", "sell_state", "sell_postalCode",
            "supp_name", "supp_contactName", "supp_email", "supp_phone", "supp_country", "supp_city", "supp_state", "supp_postalCode",
            "store_name", "store_locationAddress", "store_phone", "store_email", "store_country", "store_city", "store_state", "store_postalCode",
            "prod_name", "categoryName", "petCategory", "brand", "price", "weight", "color", "size", "material", "description", "rating", "releaseDate", "expiryDate"
        ]
        
        with open(filename, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for j in range(1, 1001):
                quantity = random.randint(1, 5)
                base_price = round(random.uniform(10.0, 150.0), 2)
                total_price = round(quantity * base_price, 2)
                c_id = f"{i}_{j}"
                
                writer.writerow([
                    (datetime.now() - timedelta(days=random.randint(0, 30))).strftime('%Y-%m-%d'),
                    quantity, total_price,
                    f"CustFN_{c_id}", f"CustLN_{c_id}", random.randint(18, 70), f"cust_{c_id}@mail.com", "Dog", f"Buddy_{c_id}", "Labrador", "Kazakhstan", "Almaty", "Almaty", "050000",
                    f"SellFN_{i}", f"SellLN_{i}", f"seller_{i}_{random.randint(1,5)}@shop.com", "Kazakhstan", "Astana", "Astana", "010000",
                    f"Supplier_{i}", f"Contact_{i}", f"supp_{i}@supply.com", "+77011112233", "Kazakhstan", "Shymkent", "Shymkent", "160000",
                    f"Store_{i}", f"Address St {i}", "+77025556677", f"store_{i}@retail.com", "Kazakhstan", "Almaty", "Almaty", "050000",
                    f"Product_{random.randint(1, 20)}", "Pet Food", "Dogs", "PremiumBrand", base_price, "5kg", "Brown", "Medium", "Organic", "Premium quality food", round(random.uniform(4.0, 5.0), 1), "2025-01-01", "2027-01-01"
                ])

def main():
    # generate_mock_csv_files()
    
    producer = None
    while not producer:
        try:
            producer = KafkaProducer(
                bootstrap_servers=BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
        except Exception:
            print("Ожидание подключения к Kafka...")
            time.sleep(3)
            
    print("Продюсер успешно подключился к Kafka. Начинается отправка стрима...")
    
    data_folder = "mock_data"
    search_path = os.path.join(data_folder, "*.csv")
    csv_files = glob.glob(search_path)
    
    if not csv_files:
        print(f"⚠ Внимание: В папке '{data_folder}' не найдено CSV-файлов для отправки!")
    else:
        csv_files.sort()
        print(f"Найдено файлов для отправки: {len(csv_files)}")

    for filename in csv_files:
        print(f"Чтение и отправка: {filename}")
        with open(filename, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                payload = {k: v for k, v in row.items()}
                payload['quantity'] = int(payload['quantity'])
                payload['totalPrice'] = float(payload['totalPrice'])
                payload['cust_age'] = int(payload['cust_age'])
                payload['price'] = float(payload['price'])
                payload['rating'] = float(payload['rating'])
                producer.send(TOPIC, payload)
                
    producer.flush()
    print("Все сообщения успешно отправлены в Kafka.")

if __name__ == "__main__":
    main()