import logging

# pyrefly: ignore [missing-import]
from google import genai
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from config import GEMINI_API_KEY, GEMINI_MODEL
from rag_service import retrieve

from services.inventory_service import (
    get_all_inventory,
    get_component,
    get_low_stock_items,
    search_inventory,
    create_reorder_request,
)


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("agent")
logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(message)s",
)


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(api_key=GEMINI_API_KEY)

logger.info("MODEL: %s", GEMINI_MODEL)
logger.info("KEY PREFIX: %s", GEMINI_API_KEY[:8] if GEMINI_API_KEY else "MISSING")


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are an AI assistant for an IoT hardware inventory management system.

You are friendly, conversational, concise, and helpful.

Rules:

- Answer naturally like ChatGPT.
- Use the knowledge base for company/product information.
- Use live inventory data for stock-related questions.
- Never invent inventory quantities.
- When live inventory data is provided, trust it over the knowledge base.
- If inventory information is unavailable, clearly say so.
"""


# ============================================================
# PRODUCT ALIASES  (comprehensive normalization)
#
# Keys are lowercase phrases. Values are the exact product
# names stored in the database.  The matching logic checks
# whether any key appears as a *substring* of the user's
# message (lowercased), so ordering matters — longer /
# more-specific keys should come first so they match before
# shorter ones.
# ============================================================

PRODUCT_ALIASES = {
    # ----- ESP Modules -----
    "esp32-cam":                "ESP32-CAM",
    "esp32 cam":                "ESP32-CAM",
    "esp32cam":                 "ESP32-CAM",

    "esp32-s3 devkit":          "ESP32-S3 DevKit",
    "esp32 s3 devkit":          "ESP32-S3 DevKit",
    "esp32s3 devkit":           "ESP32-S3 DevKit",
    "esp32 s3":                 "ESP32-S3 DevKit",

    "esp32 devkit v1":          "ESP32 DevKit V1",
    "esp32 devkit":             "ESP32 DevKit V1",
    "esp32 dev kit":            "ESP32 DevKit V1",
    "esp32 development board":  "ESP32 DevKit V1",
    "esp32 development boards": "ESP32 DevKit V1",
    "esp32 dev board":          "ESP32 DevKit V1",
    "esp32 dev boards":         "ESP32 DevKit V1",

    "esp32 wroom":              "ESP32 WROOM",
    "esp32wroom":               "ESP32 WROOM",

    "esp8266 nodemcu":          "ESP8266 NodeMCU",
    "nodemcu":                  "ESP8266 NodeMCU",
    "esp8266":                  "ESP8266 NodeMCU",
    "node mcu":                 "ESP8266 NodeMCU",

    # ----- Arduino Boards -----
    "arduino uno r3":           "Arduino Uno R3",
    "arduino uno":              "Arduino Uno R3",

    "arduino nano":             "Arduino Nano",

    "arduino mega 2560":        "Arduino Mega 2560",
    "arduino mega":             "Arduino Mega 2560",

    "arduino leonardo":         "Arduino Leonardo",

    # ----- Motor Drivers -----
    "l298n motor driver":       "L298N Motor Driver",
    "l298n":                    "L298N Motor Driver",

    "bts7960 motor driver":     "BTS7960 Motor Driver",
    "bts7960":                  "BTS7960 Motor Driver",

    "tb6612fng motor driver":   "TB6612FNG Motor Driver",
    "tb6612fng":                "TB6612FNG Motor Driver",
    "tb6612":                   "TB6612FNG Motor Driver",

    # ----- Motors -----
    "dc gear motor 12v":        "DC Gear Motor 12V",
    "dc gear motor":            "DC Gear Motor 12V",
    "dc motor":                 "DC Gear Motor 12V",

    "sg90 servo motor":         "SG90 Servo Motor",
    "sg90 servo":               "SG90 Servo Motor",
    "sg90":                     "SG90 Servo Motor",

    "mg996r servo motor":       "MG996R Servo Motor",
    "mg996r servo":             "MG996R Servo Motor",
    "mg996r":                   "MG996R Servo Motor",

    "nema 17 stepper motor":    "NEMA 17 Stepper Motor",
    "nema 17 stepper":          "NEMA 17 Stepper Motor",
    "nema 17":                  "NEMA 17 Stepper Motor",
    "stepper motor":            "NEMA 17 Stepper Motor",

    # ----- Sensors -----
    "hc-sr04 ultrasonic sensor": "HC-SR04 Ultrasonic Sensor",
    "hc-sr04 ultrasonic":       "HC-SR04 Ultrasonic Sensor",
    "hc-sr04":                  "HC-SR04 Ultrasonic Sensor",
    "hcsr04":                   "HC-SR04 Ultrasonic Sensor",
    "ultrasonic sensor":        "HC-SR04 Ultrasonic Sensor",

    "pir motion sensor":        "PIR Motion Sensor",
    "pir sensor":               "PIR Motion Sensor",
    "motion sensor":            "PIR Motion Sensor",

    "dht11 temperature sensor": "DHT11 Temperature Sensor",
    "dht11 sensor":             "DHT11 Temperature Sensor",
    "dht11":                    "DHT11 Temperature Sensor",

    "dht22 temperature sensor": "DHT22 Temperature Sensor",
    "dht22 sensor":             "DHT22 Temperature Sensor",
    "dht22":                    "DHT22 Temperature Sensor",

    "ir obstacle sensor":       "IR Obstacle Sensor",
    "ir sensor":                "IR Obstacle Sensor",

    "mpu6050 gyroscope":        "MPU6050 Gyroscope",
    "mpu6050":                  "MPU6050 Gyroscope",
    "gyroscope":                "MPU6050 Gyroscope",

    # ----- Batteries -----
    "18650 li-ion battery":     "18650 Li-ion Battery",
    "18650 battery":            "18650 Li-ion Battery",
    "18650 li-ion":             "18650 Li-ion Battery",
    "18650":                    "18650 Li-ion Battery",

    "3.7v lipo battery":        "3.7V LiPo Battery",
    "lipo battery":             "3.7V LiPo Battery",
    "3.7v lipo":                "3.7V LiPo Battery",

    "9v rechargeable battery":  "9V Rechargeable Battery",
    "9v battery":               "9V Rechargeable Battery",

    # ----- Displays -----
    "16x2 lcd display":         "16x2 LCD Display",
    "16x2 lcd":                 "16x2 LCD Display",
    "lcd display":              "16x2 LCD Display",

    "0.96 inch oled display":   "0.96 inch OLED Display",
    "0.96 oled":                "0.96 inch OLED Display",
    "oled display":             "0.96 inch OLED Display",

    "2.4 inch tft display":     "2.4 inch TFT Display",
    "2.4 tft":                  "2.4 inch TFT Display",
    "tft display":              "2.4 inch TFT Display",

    # ----- Relays -----
    "1 channel relay module":   "1 Channel Relay Module",
    "1 channel relay":          "1 Channel Relay Module",
    "single channel relay":     "1 Channel Relay Module",

    "4 channel relay module":   "4 Channel Relay Module",
    "4 channel relay":          "4 Channel Relay Module",

    # ----- Communication -----
    "hc-05 bluetooth module":   "HC-05 Bluetooth Module",
    "hc-05 bluetooth":          "HC-05 Bluetooth Module",
    "hc-05":                    "HC-05 Bluetooth Module",
    "hc05":                     "HC-05 Bluetooth Module",
    "bluetooth module":         "HC-05 Bluetooth Module",

    "sim800l gsm module":       "SIM800L GSM Module",
    "sim800l":                  "SIM800L GSM Module",
    "gsm module":               "SIM800L GSM Module",

    "neo-6m gps module":        "NEO-6M GPS Module",
    "neo-6m":                   "NEO-6M GPS Module",
    "neo6m":                    "NEO-6M GPS Module",
    "gps module":               "NEO-6M GPS Module",

    # ----- Electronic Components -----
    "220 ohm resistor pack":    "220 Ohm Resistor Pack",
    "220 ohm resistor":         "220 Ohm Resistor Pack",
    "220 ohm":                  "220 Ohm Resistor Pack",

    "10k ohm resistor pack":    "10K Ohm Resistor Pack",
    "10k ohm resistor":         "10K Ohm Resistor Pack",
    "10k resistor":             "10K Ohm Resistor Pack",
    "10k ohm":                  "10K Ohm Resistor Pack",

    "100uf capacitor pack":     "100uF Capacitor Pack",
    "100uf capacitor":          "100uF Capacitor Pack",

    "led 5mm assorted pack":    "LED 5mm Assorted Pack",
    "led 5mm":                  "LED 5mm Assorted Pack",
    "led pack":                 "LED 5mm Assorted Pack",

    "breadboard 830 point":     "Breadboard 830 Point",
    "breadboard 830":           "Breadboard 830 Point",
    "breadboard":               "Breadboard 830 Point",

    "jumper wire kit":          "Jumper Wire Kit",
    "jumper wire":              "Jumper Wire Kit",
    "jumper wires":             "Jumper Wire Kit",
}

# Sort aliases by length descending so longer (more specific)
# aliases are checked first.  This prevents "esp32" from
# matching before "esp32 dev board".
_SORTED_ALIASES = sorted(
    PRODUCT_ALIASES.items(),
    key=lambda pair: len(pair[0]),
    reverse=True,
)


# ============================================================
# DETECT PRODUCT NAME FROM USER MESSAGE
# ============================================================

def detect_product(message: str, db: Session) -> str | None:
    """
    Try to identify a product from the user's message.

    Strategy (in order):
      1. Check PRODUCT_ALIASES (substring match, longest first)
      2. Check exact database product names (substring match)
      3. Fuzzy search via inventory_service.search_inventory
    """

    lower = message.lower().strip()

    # 1. Alias match (longest-first so "esp32 dev board" beats "esp32")
    for alias, product_name in _SORTED_ALIASES:
        if alias in lower:
            logger.info("Alias match: '%s' → '%s'", alias, product_name)
            return product_name

    # 2. Exact DB name match (case-insensitive substring)
    all_items = get_all_inventory(db)
    for item in all_items:
        if item.name.lower() in lower:
            logger.info("Exact name match: '%s'", item.name)
            return item.name

    # 3. Fuzzy search — extract meaningful words and search
    search_results = search_inventory(db, message)
    if search_results:
        logger.info(
            "Fuzzy search match: '%s' → '%s'",
            message,
            search_results[0].name,
        )
        return search_results[0].name

    logger.info("No product detected in: '%s'", message)
    return None


# ============================================================
# INTENT DETECTION KEYWORDS
# ============================================================

STOCK_KEYWORDS = [
    "stock", "inventory", "available", "availability",
    "quantity", "amount", "units", "how many",
    "do we have", "have we got", "in stock",
    "do you have", "left", "remaining",
]

LOW_STOCK_KEYWORDS = [
    "low stock", "low-stock", "lowstock",
    "shortage", "below minimum", "under minimum",
    "needs reorder", "need reorder",
    "running low", "running out",
]

REORDER_KEYWORDS = [
    "reorder", "re-order", "re order",
    "order more", "place order", "create order",
    "replenish", "restock", "re-stock",
]

SUPPLIER_KEYWORDS = [
    "supplier", "who supplies", "supplied by",
    "vendor", "where to buy", "who sells",
]


def _has_keyword(text: str, keywords: list[str]) -> bool:
    """Check if any keyword appears in text (case-insensitive)."""
    lower = text.lower()
    return any(kw in lower for kw in keywords)


# ============================================================
# KNOWLEDGE SEARCH
# ============================================================

def search_knowledge(query: str) -> str:
    results = retrieve(query)

    if not results:
        return "No relevant information found in the knowledge base."

    return "\n\n".join(
        f"Source: {r['source']}\n{r['text']}"
        for r in results
    )


# ============================================================
# INVENTORY ITEM → DICT
# ============================================================

def _item_to_dict(item) -> dict:
    """Convert a SQLAlchemy InventoryItem to a plain dict."""
    return {
        "id": item.id,
        "name": item.name,
        "category": item.category,
        "stock": item.stock,
        "min_stock": item.min_stock,
        "supplier": item.supplier,
        "is_low_stock": item.stock <= item.min_stock,
        "last_updated": (
            item.updated_at.isoformat()
            if getattr(item, "updated_at", None)
            else None
        ),
    }


# ============================================================
# MAIN CHAT FUNCTION
#
# Returns a dict with keys:
#   type     — "component" | "low_stock" | "inventory" |
#              "reorder" | "ai"
#   message  — human-readable text
#   data     — list of item dicts (or single dict for component)
# ============================================================

async def ask_agent(message: str, db: Session) -> dict:

    lower = message.lower().strip()
    logger.info("User message: %s", message)

    # --------------------------------------------------------
    # LOW STOCK QUERIES
    # --------------------------------------------------------

    if _has_keyword(lower, LOW_STOCK_KEYWORDS):
        logger.info("Intent: low_stock")
        items = get_low_stock_items(db)

        if not items:
            return {
                "type": "low_stock",
                "message": "There are currently no low-stock items. All inventory levels look healthy!",
                "data": [],
            }

        data = [_item_to_dict(i) for i in items]
        names = ", ".join(i.name for i in items)

        return {
            "type": "low_stock",
            "message": f"{len(items)} item(s) are below minimum stock: {names}",
            "data": data,
        }

    # --------------------------------------------------------
    # ALL INVENTORY
    # --------------------------------------------------------

    if any(x in lower for x in [
        "all inventory", "all products", "all components",
        "show inventory", "show everything", "list inventory",
        "list all", "show all",
    ]):
        logger.info("Intent: all_inventory")
        items = get_all_inventory(db)

        if not items:
            return {
                "type": "inventory",
                "message": "There are currently no inventory items.",
                "data": [],
            }

        data = [_item_to_dict(i) for i in items]

        return {
            "type": "inventory",
            "message": f"Showing all {len(items)} inventory items.",
            "data": data,
        }

    # --------------------------------------------------------
    # DETECT PRODUCT
    # --------------------------------------------------------

    product_name = detect_product(message, db)

    if product_name:
        product = get_component(db, product_name)

        if not product:
            logger.warning(
                "Product '%s' detected but not found in DB",
                product_name,
            )
        else:
            logger.info(
                "Product found: %s (stock=%d, min=%d)",
                product.name, product.stock, product.min_stock,
            )

            item_data = _item_to_dict(product)

            # --- REORDER ---
            if _has_keyword(lower, REORDER_KEYWORDS):
                logger.info("Intent: reorder for %s", product.name)
                try:
                    result = create_reorder_request(
                        db=db,
                        item_id=product.id,
                        quantity=max(product.min_stock - product.stock, 25),
                    )
                    if result:
                        return {
                            "type": "reorder",
                            "message": (
                                f"Reorder request created for {product.name} "
                                f"({result.quantity} units). "
                                f"Supplier: {product.supplier}."
                            ),
                            "data": item_data,
                        }
                except Exception as e:
                    logger.error("Reorder error: %s", e)

                return {
                    "type": "reorder",
                    "message": f"Could not create reorder request for {product.name}.",
                    "data": item_data,
                }

            # --- SUPPLIER ---
            if _has_keyword(lower, SUPPLIER_KEYWORDS):
                logger.info("Intent: supplier for %s", product.name)
                return {
                    "type": "component",
                    "message": (
                        f"{product.name} is supplied by {product.supplier}."
                    ),
                    "data": item_data,
                }

            # --- STOCK / GENERAL PRODUCT QUERY ---
            if _has_keyword(lower, STOCK_KEYWORDS):
                logger.info("Intent: stock query for %s", product.name)

                status = "LOW STOCK ⚠" if product.stock <= product.min_stock else "In Stock ✓"

                return {
                    "type": "component",
                    "message": (
                        f"{product.name} currently has {product.stock} units in stock.\n"
                        f"Minimum stock level: {product.min_stock} units.\n"
                        f"Supplier: {product.supplier}.\n"
                        f"Status: {status}"
                    ),
                    "data": item_data,
                }

            # Product detected but no specific intent — show details
            logger.info("Intent: general product info for %s", product.name)
            return {
                "type": "component",
                "message": (
                    f"{product.name}\n"
                    f"Category: {product.category}\n"
                    f"Stock: {product.stock} units (min: {product.min_stock})\n"
                    f"Supplier: {product.supplier}"
                ),
                "data": item_data,
            }

    # --------------------------------------------------------
    # GENERAL INVENTORY SEARCH (no specific product matched)
    # --------------------------------------------------------

    if _has_keyword(lower, STOCK_KEYWORDS):
        logger.info("Intent: general inventory search")
        results = search_inventory(db, message)

        if results:
            data = [_item_to_dict(i) for i in results[:10]]
            return {
                "type": "inventory",
                "message": f"Found {len(results)} matching items.",
                "data": data,
            }

    # --------------------------------------------------------
    # AI / KNOWLEDGE BASE FALLBACK
    # --------------------------------------------------------

    logger.info("Intent: AI/knowledge fallback")

    knowledge_context = search_knowledge(message)

    prompt = f"""
{SYSTEM_PROMPT}

Knowledge base:
{knowledge_context}

User: {message}

Answer naturally and conversationally.
"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        answer = response.text

    except Exception as e:
        logger.error("Gemini primary model failed: %s", e)

        try:
            response = client.models.generate_content(
                model="models/gemini-3.5-flash",
                contents=prompt,
            )
            answer = response.text

        except Exception as e2:
            logger.error("Gemini fallback failed: %s", e2)
            answer = (
                "The AI service is temporarily unavailable. "
                "Please try again in a few moments."
            )

    return {
        "type": "ai",
        "message": answer,
        "data": [],
    }


# ============================================================
# COMMAND LINE TEST
# ============================================================

if __name__ == "__main__":

    from models import SessionLocal

    async def main():

        db = SessionLocal()

        try:

            print("Inventory AI Agent")
            print("Type 'exit' to quit.\n")

            while True:

                msg = input("You: ").strip()

                if msg.lower() == "exit":
                    break

                result = await ask_agent(msg, db)

                print(f"\nAssistant: {result['message']}\n")

                if result.get("data"):
                    if isinstance(result["data"], list):
                        for item in result["data"]:
                            print(f"  - {item.get('name', 'N/A')}: "
                                  f"{item.get('stock', '?')} units")
                    elif isinstance(result["data"], dict):
                        d = result["data"]
                        print(f"  - {d.get('name', 'N/A')}: "
                              f"{d.get('stock', '?')} units")
                    print()

        finally:
            db.close()


    import asyncio
    asyncio.run(main())