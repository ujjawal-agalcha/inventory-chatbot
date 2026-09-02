import logging
from datetime import datetime
from database.mongodb import get_products_collection, init_mongo_indexes
from excel.normalizer import normalize_text, extract_keywords_and_aliases

logger = logging.getLogger("scripts.seed_database")

# ============================================================
# LEGITIMATE ELECTRONIC EQUIPMENT INVENTORY (39 PERMANENT ITEMS)
# ============================================================

ELECTRONIC_COMPONENTS_DATA = [
    # ESP MODULES
    {
        "name": "ESP32-CAM",
        "category": "ESP Modules",
        "stock": 8,
        "min_stock": 15,
        "unit_price": 550.0,
        "supplier": "Tech Components Pvt. Ltd.",
        "details": "Wi-Fi + Bluetooth camera module OV2640 with MicroSD support",
        "market": "Direct / Tech Components",
    },
    {
        "name": "ESP32 DevKit V1",
        "category": "ESP Modules",
        "stock": 32,
        "min_stock": 15,
        "unit_price": 420.0,
        "supplier": "ElectroHub India",
        "details": "Dual-core ESP32 30-pin development board with Wi-Fi & BLE",
        "market": "ElectroHub Direct",
    },
    {
        "name": "ESP8266 NodeMCU",
        "category": "ESP Modules",
        "stock": 21,
        "min_stock": 10,
        "unit_price": 280.0,
        "supplier": "Robo Components",
        "details": "ESP-12E Wi-Fi development board with CP2102/CH340",
        "market": "Robo Components Hub",
    },
    {
        "name": "ESP32 WROOM",
        "category": "ESP Modules",
        "stock": 18,
        "min_stock": 10,
        "unit_price": 350.0,
        "supplier": "ElectroHub India",
        "details": "ESP32-WROOM-32D SMD Wi-Fi & Bluetooth module",
        "market": "ElectroHub Direct",
    },
    {
        "name": "ESP32-S3 DevKit",
        "category": "ESP Modules",
        "stock": 25,
        "min_stock": 12,
        "unit_price": 680.0,
        "supplier": "Tech Components Pvt. Ltd.",
        "details": "ESP32-S3 Dual-core LX7 microcontroller board with Vector Instructions",
        "market": "Tech Components Direct",
    },

    # ARDUINO BOARDS
    {
        "name": "Arduino Uno R3",
        "category": "Arduino Boards",
        "stock": 20,
        "min_stock": 10,
        "unit_price": 450.0,
        "supplier": "Arduino Store India",
        "details": "ATmega328P microcontroller board with USB interface",
        "market": "Arduino Store",
    },
    {
        "name": "Arduino Nano",
        "category": "Arduino Boards",
        "stock": 15,
        "min_stock": 8,
        "unit_price": 250.0,
        "supplier": "ElectroHub India",
        "details": "Compact ATmega328P breadboard-friendly board with Mini/Type-C USB",
        "market": "ElectroHub Direct",
    },
    {
        "name": "Arduino Mega 2560",
        "category": "Arduino Boards",
        "stock": 7,
        "min_stock": 10,
        "unit_price": 850.0,
        "supplier": "Tech Components Pvt. Ltd.",
        "details": "ATmega2560 microcontroller board with 54 digital I/O pins",
        "market": "Tech Components Direct",
    },
    {
        "name": "Arduino Leonardo",
        "category": "Arduino Boards",
        "stock": 12,
        "min_stock": 6,
        "unit_price": 480.0,
        "supplier": "Robo Components",
        "details": "ATmega32u4 board with built-in USB communication",
        "market": "Robo Components Hub",
    },

    # MOTOR DRIVERS
    {
        "name": "L298N Motor Driver",
        "category": "Motor Drivers",
        "stock": 18,
        "min_stock": 8,
        "unit_price": 160.0,
        "supplier": "Robo Components",
        "details": "Dual H-Bridge DC and Stepper motor driver module",
        "market": "Robo Components Hub",
    },
    {
        "name": "BTS7960 Motor Driver",
        "category": "Motor Drivers",
        "stock": 6,
        "min_stock": 10,
        "unit_price": 580.0,
        "supplier": "ElectroHub India",
        "details": "High-power 43A H-Bridge motor driver module",
        "market": "ElectroHub Direct",
    },
    {
        "name": "TB6612FNG Motor Driver",
        "category": "Motor Drivers",
        "stock": 14,
        "min_stock": 7,
        "unit_price": 190.0,
        "supplier": "Tech Components Pvt. Ltd.",
        "details": "High-efficiency MOSFET-based 1.2A dual motor driver",
        "market": "Tech Components Direct",
    },

    # MOTORS
    {
        "name": "DC Gear Motor 12V",
        "category": "Motors",
        "stock": 25,
        "min_stock": 10,
        "unit_price": 220.0,
        "supplier": "Motor World India",
        "details": "12V high-torque DC geared motor for robotics",
        "market": "Motor World",
    },
    {
        "name": "SG90 Servo Motor",
        "category": "Motors",
        "stock": 40,
        "min_stock": 15,
        "unit_price": 90.0,
        "supplier": "ElectroHub India",
        "details": "9g micro servo motor with 180 degree rotation",
        "market": "ElectroHub Direct",
    },
    {
        "name": "MG996R Servo Motor",
        "category": "Motors",
        "stock": 8,
        "min_stock": 12,
        "unit_price": 320.0,
        "supplier": "Robo Components",
        "details": "High-torque metal gear servo motor",
        "market": "Robo Components Hub",
    },
    {
        "name": "NEMA 17 Stepper Motor",
        "category": "Motors",
        "stock": 16,
        "min_stock": 8,
        "unit_price": 750.0,
        "supplier": "Tech Components Pvt. Ltd.",
        "details": "1.8 deg 4.2 kg-cm bipolar stepper motor for 3D printers and CNC",
        "market": "Tech Components Direct",
    },

    # SENSORS
    {
        "name": "HC-SR04 Ultrasonic Sensor",
        "category": "Sensors",
        "stock": 30,
        "min_stock": 15,
        "unit_price": 80.0,
        "supplier": "Sensor Hub India",
        "details": "Ultrasonic distance ranging sensor 2cm-400cm",
        "market": "Sensor Hub",
    },
    {
        "name": "PIR Motion Sensor",
        "category": "Sensors",
        "stock": 22,
        "min_stock": 10,
        "unit_price": 95.0,
        "supplier": "ElectroHub India",
        "details": "HC-SR501 passive infrared human motion sensor",
        "market": "ElectroHub Direct",
    },
    {
        "name": "DHT11 Temperature Sensor",
        "category": "Sensors",
        "stock": 9,
        "min_stock": 15,
        "unit_price": 70.0,
        "supplier": "Sensor Hub India",
        "details": "Basic digital temperature and humidity sensor",
        "market": "Sensor Hub",
    },
    {
        "name": "DHT22 Temperature Sensor",
        "category": "Sensors",
        "stock": 18,
        "min_stock": 8,
        "unit_price": 240.0,
        "supplier": "Robo Components",
        "details": "High-precision digital temperature & humidity sensor AM2302",
        "market": "Robo Components Hub",
    },
    {
        "name": "IR Obstacle Sensor",
        "category": "Sensors",
        "stock": 35,
        "min_stock": 15,
        "unit_price": 45.0,
        "supplier": "ElectroHub India",
        "details": "Infrared obstacle avoidance proximity sensor module",
        "market": "ElectroHub Direct",
    },
    {
        "name": "MPU6050 Gyroscope",
        "category": "Sensors",
        "stock": 5,
        "min_stock": 10,
        "unit_price": 150.0,
        "supplier": "Tech Components Pvt. Ltd.",
        "details": "6-axis motion tracking sensor with 3-axis gyro and 3-axis accelerometer",
        "market": "Tech Components Direct",
    },

    # BATTERIES
    {
        "name": "18650 Li-ion Battery",
        "category": "Batteries",
        "stock": 50,
        "min_stock": 20,
        "unit_price": 180.0,
        "supplier": "Battery World India",
        "details": "3.7V 2600mAh rechargeable Lithium-Ion cell",
        "market": "Battery World",
    },
    {
        "name": "3.7V LiPo Battery",
        "category": "Batteries",
        "stock": 12,
        "min_stock": 15,
        "unit_price": 250.0,
        "supplier": "PowerTech India",
        "details": "3.7V 1000mAh rechargeable Lithium-Polymer battery",
        "market": "PowerTech",
    },
    {
        "name": "9V Rechargeable Battery",
        "category": "Batteries",
        "stock": 18,
        "min_stock": 8,
        "unit_price": 320.0,
        "supplier": "Battery World India",
        "details": "9V 650mAh rechargeable Li-ion battery with micro USB",
        "market": "Battery World",
    },

    # DISPLAYS
    {
        "name": "16x2 LCD Display",
        "category": "Displays",
        "stock": 25,
        "min_stock": 10,
        "unit_price": 140.0,
        "supplier": "Display Components India",
        "details": "16 characters x 2 lines alphanumeric LCD module with I2C support",
        "market": "Display Components",
    },
    {
        "name": "0.96 inch OLED Display",
        "category": "Displays",
        "stock": 7,
        "min_stock": 12,
        "unit_price": 220.0,
        "supplier": "ElectroHub India",
        "details": "128x64 I2C SSD1306 monochrome OLED display module",
        "market": "ElectroHub Direct",
    },
    {
        "name": "2.4 inch TFT Display",
        "category": "Displays",
        "stock": 14,
        "min_stock": 6,
        "unit_price": 650.0,
        "supplier": "Tech Components Pvt. Ltd.",
        "details": "2.4 inch SPI color TFT LCD display shield with touch screen",
        "market": "Tech Components Direct",
    },

    # RELAYS
    {
        "name": "1 Channel Relay Module",
        "category": "Relays",
        "stock": 30,
        "min_stock": 12,
        "unit_price": 65.0,
        "supplier": "ElectroHub India",
        "details": "5V 1-channel relay control module 10A 250VAC",
        "market": "ElectroHub Direct",
    },
    {
        "name": "4 Channel Relay Module",
        "category": "Relays",
        "stock": 11,
        "min_stock": 15,
        "unit_price": 210.0,
        "supplier": "Robo Components",
        "details": "5V 4-channel optocoupler isolated relay board",
        "market": "Robo Components Hub",
    },

    # COMMUNICATION
    {
        "name": "HC-05 Bluetooth Module",
        "category": "Communication",
        "stock": 18,
        "min_stock": 8,
        "unit_price": 280.0,
        "supplier": "Communication Hub India",
        "details": "Serial Bluetooth SPP transceiver module",
        "market": "Communication Hub",
    },
    {
        "name": "SIM800L GSM Module",
        "category": "Communication",
        "stock": 6,
        "min_stock": 10,
        "unit_price": 480.0,
        "supplier": "Tech Components Pvt. Ltd.",
        "details": "Quad-band GSM/GPRS wireless cellular module",
        "market": "Tech Components Direct",
    },
    {
        "name": "NEO-6M GPS Module",
        "category": "Communication",
        "stock": 13,
        "min_stock": 7,
        "unit_price": 550.0,
        "supplier": "Robo Components",
        "details": "GPS positioning module with ceramic active antenna",
        "market": "Robo Components Hub",
    },

    # ELECTRONIC COMPONENTS
    {
        "name": "220 Ohm Resistor Pack",
        "category": "Components",
        "stock": 100,
        "min_stock": 30,
        "unit_price": 35.0,
        "supplier": "Components Market India",
        "details": "1/4W metal film resistors pack of 50",
        "market": "Components Market",
    },
    {
        "name": "10K Ohm Resistor Pack",
        "category": "Components",
        "stock": 85,
        "min_stock": 30,
        "unit_price": 35.0,
        "supplier": "Components Market India",
        "details": "1/4W pull-up/pull-down resistor pack of 50",
        "market": "Components Market",
    },
    {
        "name": "100uF Capacitor Pack",
        "category": "Components",
        "stock": 40,
        "min_stock": 15,
        "unit_price": 50.0,
        "supplier": "ElectroHub India",
        "details": "25V electrolytic capacitor pack of 20",
        "market": "ElectroHub Direct",
    },
    {
        "name": "LED 5mm Assorted Pack",
        "category": "Components",
        "stock": 60,
        "min_stock": 20,
        "unit_price": 60.0,
        "supplier": "Components Market India",
        "details": "Assorted red, green, blue, yellow, white LEDs pack of 50",
        "market": "Components Market",
    },
    {
        "name": "Breadboard 830 Point",
        "category": "Components",
        "stock": 25,
        "min_stock": 10,
        "unit_price": 120.0,
        "supplier": "Robo Components",
        "details": "MB-102 solderless prototyping breadboard 830 tie-points",
        "market": "Robo Components Hub",
    },
    {
        "name": "Jumper Wire Kit",
        "category": "Components",
        "stock": 35,
        "min_stock": 15,
        "unit_price": 90.0,
        "supplier": "ElectroHub India",
        "details": "Male-to-Male, Male-to-Female, Female-to-Female jumper wires 65 pcs",
        "market": "ElectroHub Direct",
    },
]


def seed_mongo_inventory():
    """
    Ensure the 39 legitimate electronic equipment items are present in MongoDB
    under the 'products' collection as permanent inventory.
    """
    init_mongo_indexes()
    products_col = get_products_collection()

    added = 0
    updated = 0

    for item in ELECTRONIC_COMPONENTS_DATA:
        norm_name = normalize_text(item["name"])
        keywords, aliases = extract_keywords_and_aliases(item["name"], item.get("details", ""))

        existing = products_col.find_one({"normalized_name": norm_name})
        stock = item["stock"]
        min_stock = item["min_stock"]
        status_str = "out_of_stock" if stock == 0 else ("low_stock" if stock <= min_stock else "in_stock")

        if existing:
            products_col.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "source_type": "permanent_inventory",
                        "category": item["category"],
                        "supplier": item["supplier"],
                        "details": item.get("details", existing.get("details", "")),
                        "market": item.get("market", existing.get("market", "Local")),
                        "unit_price": item.get("unit_price", existing.get("unit_price", 0.0)),
                    }
                }
            )
            updated += 1
        else:
            doc = {
                "name": item["name"],
                "normalized_name": norm_name,
                "details": item.get("details", ""),
                "aliases": aliases,
                "keywords": keywords,
                "category": item["category"],
                "current_stock": stock,
                "min_stock": min_stock,
                "unit_price": item.get("unit_price", 0.0),
                "supplier": item["supplier"],
                "market": item.get("market", "Local"),
                "status": status_str,
                "total_expense": round(stock * item.get("unit_price", 0.0), 2),
                "total_qty_purchased": stock,
                "total_qty_required": 0,
                "pending_requirements": 0,
                "source_type": "permanent_inventory",
                "created_by_import_id": None,
                "import_batch_ids": [],
                "source_files": [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            products_col.insert_one(doc)
            added += 1

    logger.info("MongoDB Permanent Inventory Seed: Added %d, Updated %d", added, updated)
    return {"added": added, "updated": updated, "total": len(ELECTRONIC_COMPONENTS_DATA)}


def seed_inventory():
    """Seed MongoDB with permanent electronic equipment inventory."""
    return seed_mongo_inventory()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = seed_inventory()
    print(f"Database seeding completed successfully: {res}")
