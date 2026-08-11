from models import SessionLocal, InventoryItem
from inventory_data import components


def seed_inventory():
    db = SessionLocal()

    try:

        data = [

            # ==================================================
            # ESP MODULES
            # ==================================================

            {
                "name": "ESP32-CAM",
                "category": "ESP Modules",
                "stock": 8,
                "min_stock": 15,
                "supplier": "Tech Components Pvt. Ltd.",
            },

            {
                "name": "ESP32 DevKit V1",
                "category": "ESP Modules",
                "stock": 32,
                "min_stock": 15,
                "supplier": "ElectroHub India",
            },

            {
                "name": "ESP8266 NodeMCU",
                "category": "ESP Modules",
                "stock": 21,
                "min_stock": 10,
                "supplier": "Robo Components",
            },

            {
                "name": "ESP32 WROOM",
                "category": "ESP Modules",
                "stock": 18,
                "min_stock": 10,
                "supplier": "ElectroHub India",
            },

            {
                "name": "ESP32-S3 DevKit",
                "category": "ESP Modules",
                "stock": 25,
                "min_stock": 12,
                "supplier": "Tech Components Pvt. Ltd.",
            },

            # ==================================================
            # ARDUINO BOARDS
            # ==================================================

            {
                "name": "Arduino Uno R3",
                "category": "Arduino Boards",
                "stock": 20,
                "min_stock": 10,
                "supplier": "Arduino Store India",
            },

            {
                "name": "Arduino Nano",
                "category": "Arduino Boards",
                "stock": 15,
                "min_stock": 8,
                "supplier": "ElectroHub India",
            },

            {
                "name": "Arduino Mega 2560",
                "category": "Arduino Boards",
                "stock": 7,
                "min_stock": 10,
                "supplier": "Tech Components Pvt. Ltd.",
            },

            {
                "name": "Arduino Leonardo",
                "category": "Arduino Boards",
                "stock": 12,
                "min_stock": 6,
                "supplier": "Robo Components",
            },

            # ==================================================
            # MOTOR DRIVERS
            # ==================================================

            {
                "name": "L298N Motor Driver",
                "category": "Motor Drivers",
                "stock": 18,
                "min_stock": 8,
                "supplier": "Robo Components",
            },

            {
                "name": "BTS7960 Motor Driver",
                "category": "Motor Drivers",
                "stock": 6,
                "min_stock": 10,
                "supplier": "ElectroHub India",
            },

            {
                "name": "TB6612FNG Motor Driver",
                "category": "Motor Drivers",
                "stock": 14,
                "min_stock": 7,
                "supplier": "Tech Components Pvt. Ltd.",
            },

            # ==================================================
            # MOTORS
            # ==================================================

            {
                "name": "DC Gear Motor 12V",
                "category": "Motors",
                "stock": 25,
                "min_stock": 10,
                "supplier": "Motor World India",
            },

            {
                "name": "SG90 Servo Motor",
                "category": "Motors",
                "stock": 40,
                "min_stock": 15,
                "supplier": "ElectroHub India",
            },

            {
                "name": "MG996R Servo Motor",
                "category": "Motors",
                "stock": 8,
                "min_stock": 12,
                "supplier": "Robo Components",
            },

            {
                "name": "NEMA 17 Stepper Motor",
                "category": "Motors",
                "stock": 16,
                "min_stock": 8,
                "supplier": "Tech Components Pvt. Ltd.",
            },

            # ==================================================
            # SENSORS
            # ==================================================

            {
                "name": "HC-SR04 Ultrasonic Sensor",
                "category": "Sensors",
                "stock": 30,
                "min_stock": 15,
                "supplier": "Sensor Hub India",
            },

            {
                "name": "PIR Motion Sensor",
                "category": "Sensors",
                "stock": 22,
                "min_stock": 10,
                "supplier": "ElectroHub India",
            },

            {
                "name": "DHT11 Temperature Sensor",
                "category": "Sensors",
                "stock": 9,
                "min_stock": 15,
                "supplier": "Sensor Hub India",
            },

            {
                "name": "DHT22 Temperature Sensor",
                "category": "Sensors",
                "stock": 18,
                "min_stock": 8,
                "supplier": "Robo Components",
            },

            {
                "name": "IR Obstacle Sensor",
                "category": "Sensors",
                "stock": 35,
                "min_stock": 15,
                "supplier": "ElectroHub India",
            },

            {
                "name": "MPU6050 Gyroscope",
                "category": "Sensors",
                "stock": 5,
                "min_stock": 10,
                "supplier": "Tech Components Pvt. Ltd.",
            },

            # ==================================================
            # BATTERIES
            # ==================================================

            {
                "name": "18650 Li-ion Battery",
                "category": "Batteries",
                "stock": 50,
                "min_stock": 20,
                "supplier": "Battery World India",
            },

            {
                "name": "3.7V LiPo Battery",
                "category": "Batteries",
                "stock": 12,
                "min_stock": 15,
                "supplier": "PowerTech India",
            },

            {
                "name": "9V Rechargeable Battery",
                "category": "Batteries",
                "stock": 18,
                "min_stock": 8,
                "supplier": "Battery World India",
            },

            # ==================================================
            # DISPLAYS
            # ==================================================

            {
                "name": "16x2 LCD Display",
                "category": "Displays",
                "stock": 25,
                "min_stock": 10,
                "supplier": "Display Components India",
            },

            {
                "name": "0.96 inch OLED Display",
                "category": "Displays",
                "stock": 7,
                "min_stock": 12,
                "supplier": "ElectroHub India",
            },

            {
                "name": "2.4 inch TFT Display",
                "category": "Displays",
                "stock": 14,
                "min_stock": 6,
                "supplier": "Tech Components Pvt. Ltd.",
            },

            # ==================================================
            # RELAYS
            # ==================================================

            {
                "name": "1 Channel Relay Module",
                "category": "Relays",
                "stock": 30,
                "min_stock": 12,
                "supplier": "ElectroHub India",
            },

            {
                "name": "4 Channel Relay Module",
                "category": "Relays",
                "stock": 11,
                "min_stock": 15,
                "supplier": "Robo Components",
            },

            # ==================================================
            # COMMUNICATION
            # ==================================================

            {
                "name": "HC-05 Bluetooth Module",
                "category": "Communication",
                "stock": 18,
                "min_stock": 8,
                "supplier": "Communication Hub India",
            },

            {
                "name": "SIM800L GSM Module",
                "category": "Communication",
                "stock": 6,
                "min_stock": 10,
                "supplier": "Tech Components Pvt. Ltd.",
            },

            {
                "name": "NEO-6M GPS Module",
                "category": "Communication",
                "stock": 13,
                "min_stock": 7,
                "supplier": "Robo Components",
            },

            # ==================================================
            # ELECTRONIC COMPONENTS
            # ==================================================

            {
                "name": "220 Ohm Resistor Pack",
                "category": "Components",
                "stock": 100,
                "min_stock": 30,
                "supplier": "Components Market India",
            },

            {
                "name": "10K Ohm Resistor Pack",
                "category": "Components",
                "stock": 85,
                "min_stock": 30,
                "supplier": "Components Market India",
            },

            {
                "name": "100uF Capacitor Pack",
                "category": "Components",
                "stock": 40,
                "min_stock": 15,
                "supplier": "ElectroHub India",
            },

            {
                "name": "LED 5mm Assorted Pack",
                "category": "Components",
                "stock": 60,
                "min_stock": 20,
                "supplier": "Components Market India",
            },

            {
                "name": "Breadboard 830 Point",
                "category": "Components",
                "stock": 25,
                "min_stock": 10,
                "supplier": "Robo Components",
            },

            {
                "name": "Jumper Wire Kit",
                "category": "Components",
                "stock": 35,
                "min_stock": 15,
                "supplier": "ElectroHub India",
            },
        ]


        # =====================================================
        # INSERT DATA
        # =====================================================

        added = 0
        skipped = 0

        for item_data in data:

            existing = (
                db.query(InventoryItem)
                .filter(
                    InventoryItem.name ==
                    item_data["name"]
                )
                .first()
            )

            if existing:
                skipped += 1
                continue

            item = InventoryItem(
                name=item_data["name"],
                category=item_data["category"],
                stock=item_data["stock"],
                min_stock=item_data["min_stock"],
                supplier=item_data["supplier"],
            )

            db.add(item)

            added += 1


        db.commit()

        print()
        print("=" * 60)
        print("INVENTORY SEED COMPLETED")
        print("=" * 60)
        print(f"Added products  : {added}")
        print(f"Skipped existing: {skipped}")
        print(f"Total products  : {len(data)}")
        print("=" * 60)


    except Exception as error:

        db.rollback()

        print()
        print("ERROR SEEDING INVENTORY")
        print(error)

        raise

    finally:

        db.close()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    seed()