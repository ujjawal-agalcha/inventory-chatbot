import logging
import re
import asyncio
from typing import AsyncGenerator

from sqlalchemy.orm import Session

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

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
# GEMINI
# ============================================================

def get_llm():
    """
    Create the LangChain Gemini client.

    IMPORTANT:
    GEMINI_MODEL can be:
        gemini-3.5-flash
    or:
        models/gemini-3.5-flash

    LangChain expects the model name without "models/".
    """

    clean_model = (
        GEMINI_MODEL.replace("models/", "")
        if GEMINI_MODEL
        else "gemini-3.5-flash"
    )

    return ChatGoogleGenerativeAI(
        model=clean_model,
        google_api_key=GEMINI_API_KEY,
        temperature=0.2,
    )


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are an AI assistant for an IoT hardware inventory management system.

You are friendly, professional, concise, and helpful like ChatGPT.

CRITICAL INVENTORY RULES:

1. Never invent inventory data.
2. Never guess stock quantities.
3. Never guess suppliers.
4. Never guess categories.
5. Inventory data returned by the database is absolute ground truth.
6. If a product is not found in the database, clearly say so.
7. For technical questions unrelated to current inventory, use the knowledge base.
8. Never claim that a product is in stock unless verified by the database.
"""


# ============================================================
# PRODUCT ALIASES
# ============================================================

PRODUCT_ALIASES = {

    # --------------------------------------------------------
    # ESP MODULES
    # --------------------------------------------------------

    "esp32-cam": "ESP32-CAM",
    "esp32 cam": "ESP32-CAM",
    "esp32cam": "ESP32-CAM",

    "esp32-s3 devkit": "ESP32-S3 DevKit",
    "esp32 s3 devkit": "ESP32-S3 DevKit",
    "esp32s3 devkit": "ESP32-S3 DevKit",
    "esp32 s3": "ESP32-S3 DevKit",

    "esp32 devkit v1": "ESP32 DevKit V1",
    "esp32 devkit": "ESP32 DevKit V1",
    "esp32 dev kit": "ESP32 DevKit V1",
    "esp32 development board": "ESP32 DevKit V1",
    "esp32 development boards": "ESP32 DevKit V1",
    "esp32 dev board": "ESP32 DevKit V1",
    "esp32 dev boards": "ESP32 DevKit V1",
    "esp 32 dev kit": "ESP32 DevKit V1",

    "esp32 wroom": "ESP32 WROOM",
    "esp32wroom": "ESP32 WROOM",

    "esp8266 nodemcu": "ESP8266 NodeMCU",
    "node mcu": "ESP8266 NodeMCU",
    "nodemcu": "ESP8266 NodeMCU",
    "esp8266": "ESP8266 NodeMCU",

    # --------------------------------------------------------
    # ARDUINO
    # --------------------------------------------------------

    "arduino uno r3": "Arduino Uno R3",
    "arduino uno": "Arduino Uno R3",
    "uno r3": "Arduino Uno R3",
    "uno": "Arduino Uno R3",

    "arduino nano": "Arduino Nano",
    "nano": "Arduino Nano",

    "arduino mega 2560": "Arduino Mega 2560",
    "arduino mega": "Arduino Mega 2560",
    "mega 2560": "Arduino Mega 2560",
    "mega": "Arduino Mega 2560",

    "arduino leonardo": "Arduino Leonardo",
    "leonardo": "Arduino Leonardo",

    # --------------------------------------------------------
    # MOTOR DRIVERS
    # --------------------------------------------------------

    "l298n motor driver": "L298N Motor Driver",
    "l298n": "L298N Motor Driver",

    "bts7960 motor driver": "BTS7960 Motor Driver",
    "bts7960": "BTS7960 Motor Driver",

    "tb6612fng motor driver": "TB6612FNG Motor Driver",
    "tb6612fng": "TB6612FNG Motor Driver",
    "tb6612": "TB6612FNG Motor Driver",

    # --------------------------------------------------------
    # MOTORS
    # --------------------------------------------------------

    "dc gear motor 12v": "DC Gear Motor 12V",
    "dc gear motor": "DC Gear Motor 12V",
    "dc motor": "DC Gear Motor 12V",

    "sg90 servo motor": "SG90 Servo Motor",
    "sg90 servo": "SG90 Servo Motor",
    "sg90": "SG90 Servo Motor",

    "mg996r servo motor": "MG996R Servo Motor",
    "mg996r servo": "MG996R Servo Motor",
    "mg996r": "MG996R Servo Motor",

    "nema 17 stepper motor": "NEMA 17 Stepper Motor",
    "nema 17 stepper": "NEMA 17 Stepper Motor",
    "nema 17": "NEMA 17 Stepper Motor",
    "stepper motor": "NEMA 17 Stepper Motor",

    # --------------------------------------------------------
    # SENSORS
    # --------------------------------------------------------

    "hc-sr04 ultrasonic sensor": "HC-SR04 Ultrasonic Sensor",
    "hc-sr04 ultrasonic": "HC-SR04 Ultrasonic Sensor",
    "hc-sr04": "HC-SR04 Ultrasonic Sensor",
    "hcsr04": "HC-SR04 Ultrasonic Sensor",
    "ultrasonic sensor": "HC-SR04 Ultrasonic Sensor",

    "pir motion sensor": "PIR Motion Sensor",
    "pir sensor": "PIR Motion Sensor",
    "motion sensor": "PIR Motion Sensor",

    "dht11 temperature sensor": "DHT11 Temperature Sensor",
    "dht11 sensor": "DHT11 Temperature Sensor",
    "dht11": "DHT11 Temperature Sensor",

    "dht22 temperature sensor": "DHT22 Temperature Sensor",
    "dht22 sensor": "DHT22 Temperature Sensor",
    "dht22": "DHT22 Temperature Sensor",

    "ir obstacle sensor": "IR Obstacle Sensor",
    "ir sensor": "IR Obstacle Sensor",

    "mpu6050 gyroscope": "MPU6050 Gyroscope",
    "mpu6050": "MPU6050 Gyroscope",
    "gyroscope": "MPU6050 Gyroscope",

    # --------------------------------------------------------
    # BATTERIES
    # --------------------------------------------------------

    "18650 li-ion battery": "18650 Li-ion Battery",
    "18650 battery": "18650 Li-ion Battery",
    "18650 li-ion": "18650 Li-ion Battery",
    "18650": "18650 Li-ion Battery",

    "3.7v lipo battery": "3.7V LiPo Battery",
    "lipo battery": "3.7V LiPo Battery",
    "3.7v lipo": "3.7V LiPo Battery",

    "9v rechargeable battery": "9V Rechargeable Battery",
    "9v battery": "9V Rechargeable Battery",

    # --------------------------------------------------------
    # DISPLAYS
    # --------------------------------------------------------

    "16x2 lcd display": "16x2 LCD Display",
    "16x2 lcd": "16x2 LCD Display",
    "lcd display": "16x2 LCD Display",

    "0.96 inch oled display": "0.96 inch OLED Display",
    "0.96 oled": "0.96 inch OLED Display",
    "oled display": "0.96 inch OLED Display",

    "2.4 inch tft display": "2.4 inch TFT Display",
    "2.4 tft": "2.4 inch TFT Display",
    "tft display": "2.4 inch TFT Display",

    # --------------------------------------------------------
    # RELAYS
    # --------------------------------------------------------

    "1 channel relay module": "1 Channel Relay Module",
    "1 channel relay": "1 Channel Relay Module",
    "single channel relay": "1 Channel Relay Module",

    "4 channel relay module": "4 Channel Relay Module",
    "4 channel relay": "4 Channel Relay Module",

    # --------------------------------------------------------
    # COMMUNICATION
    # --------------------------------------------------------

    "hc-05 bluetooth module": "HC-05 Bluetooth Module",
    "hc-05 bluetooth": "HC-05 Bluetooth Module",
    "hc-05": "HC-05 Bluetooth Module",
    "hc05": "HC-05 Bluetooth Module",
    "bluetooth module": "HC-05 Bluetooth Module",

    "sim800l gsm module": "SIM800L GSM Module",
    "sim800l": "SIM800L GSM Module",
    "gsm module": "SIM800L GSM Module",

    "neo-6m gps module": "NEO-6M GPS Module",
    "neo-6m": "NEO-6M GPS Module",
    "neo6m": "NEO-6M GPS Module",
    "gps module": "NEO-6M GPS Module",

    # --------------------------------------------------------
    # ELECTRONIC COMPONENTS
    # --------------------------------------------------------

    "220 ohm resistor pack": "220 Ohm Resistor Pack",
    "220 ohm resistor": "220 Ohm Resistor Pack",
    "220 ohm": "220 Ohm Resistor Pack",

    "10k ohm resistor pack": "10K Ohm Resistor Pack",
    "10k ohm resistor": "10K Ohm Resistor Pack",
    "10k resistor": "10K Ohm Resistor Pack",
    "10k ohm": "10K Ohm Resistor Pack",

    "100uf capacitor pack": "100uF Capacitor Pack",
    "100uf capacitor": "100uF Capacitor Pack",

    "led 5mm assorted pack": "LED 5mm Assorted Pack",
    "led 5mm": "LED 5mm Assorted Pack",
    "led pack": "LED 5mm Assorted Pack",

    "breadboard 830 point": "Breadboard 830 Point",
    "breadboard 830": "Breadboard 830 Point",
    "breadboard": "Breadboard 830 Point",

    "jumper wire kit": "Jumper Wire Kit",
    "jumper wire": "Jumper Wire Kit",
    "jumper wires": "Jumper Wire Kit",
}


_SORTED_ALIASES = sorted(
    PRODUCT_ALIASES.items(),
    key=lambda pair: len(pair[0]),
    reverse=True,
)


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def _normalize_text(text: str) -> str:
    """
    Normalize user text.

    Example:

        "How many ESP32 Dev Kit are there?"
        ->
        "how many esp32 dev kit are there"
    """

    text = text.lower()

    text = re.sub(
        r"[^\w\s-]",
        " ",
        text,
    )

    return " ".join(text.split())


# ============================================================
# PRODUCT DETECTION
# ============================================================

def detect_product(message: str, db: Session) -> str | None:
    """
    Resolve a product from the user's natural-language message.

    Resolution order:

    1. Longest known alias
    2. Exact database product name
    3. Normalized database product name
    4. Intelligent inventory search
    """

    if not message:
        return None

    lower = message.lower().strip()
    norm = _normalize_text(message)

    # ---------------------------------------------------------
    # 1. PRODUCT ALIASES
    # ---------------------------------------------------------

    for alias, product_name in _SORTED_ALIASES:

        alias_norm = _normalize_text(alias)

        if alias in lower or alias_norm in norm:
            logger.info(
                "Alias match: '%s' -> '%s'",
                alias,
                product_name,
            )

            # Verify against DB
            product = get_component(
                db,
                product_name,
            )

            if product:
                logger.info(
                    "Verified product in DB: %s",
                    product.name,
                )

                return product.name

            logger.warning(
                "Alias resolved to '%s' but product "
                "does not exist in database",
                product_name,
            )

    # ---------------------------------------------------------
    # 2. EXACT DATABASE PRODUCT NAMES
    # ---------------------------------------------------------

    all_items = get_all_inventory(db)

    for item in all_items:

        item_lower = item.name.lower()
        item_norm = _normalize_text(item.name)

        if item_lower in lower:
            logger.info(
                "Exact DB product match: '%s'",
                item.name,
            )

            return item.name

        if item_norm in norm:
            logger.info(
                "Normalized DB product match: '%s'",
                item.name,
            )

            return item.name

    # ---------------------------------------------------------
    # 3. INTELLIGENT SEARCH
    # ---------------------------------------------------------

    search_results = search_inventory(
        db,
        message,
    )

    if search_results:

        # Only accept a confident result
        best = search_results[0]

        logger.info(
            "Inventory search match: '%s' -> '%s'",
            message,
            best.name,
        )

        return best.name

    return None

    # --------------------------------------------------------
    # 1. ALIAS MATCH
    # --------------------------------------------------------

    for alias, product_name in _SORTED_ALIASES:

        alias_normalized = _normalize_text(alias)

        if alias_normalized in normalized:

            logger.info(
                "Alias match: '%s' -> '%s'",
                alias,
                product_name,
            )

            return product_name

    # --------------------------------------------------------
    # 2. EXACT DATABASE PRODUCT NAME
    # --------------------------------------------------------

    items = get_all_inventory(db)

    for item in items:

        item_name_normalized = _normalize_text(item.name)

        if item_name_normalized in normalized:

            logger.info(
                "Database product match: '%s'",
                item.name,
            )

            return item.name

    # --------------------------------------------------------
    # 3. TOKEN BASED MATCHING
    # --------------------------------------------------------

    # Remove common question words.
    stop_words = {
        "how",
        "many",
        "much",
        "is",
        "are",
        "there",
        "in",
        "stock",
        "available",
        "availability",
        "do",
        "we",
        "have",
        "got",
        "the",
        "a",
        "an",
        "what",
        "what's",
        "which",
        "please",
        "tell",
        "me",
        "about",
        "can",
        "you",
        "show",
        "give",
        "current",
        "currently",
        "quantity",
        "units",
        "left",
        "remaining",
    }

    message_tokens = set(
        token
        for token in normalized.split()
        if token not in stop_words
    )

    if message_tokens:

        best_item = None
        best_score = 0

        for item in items:

            item_tokens = set(
                _normalize_text(item.name).split()
            )

            matched_tokens = (
                message_tokens & item_tokens
            )

            score = len(matched_tokens)

            if score > best_score:

                best_score = score
                best_item = item

        # Require at least one meaningful token.
        if best_item and best_score >= 1:

            logger.info(
                "Token product match: '%s' -> '%s'",
                message,
                best_item.name,
            )

            return best_item.name

    return None


# ============================================================
# CONTEXTUAL PRODUCT RESOLUTION
# ============================================================

def resolve_product_with_context(
    message: str,
    conversation_history: list[dict] | None,
    db: Session,
) -> str | None:

    # First: current message.
    product = detect_product(
        message,
        db,
    )

    if product:
        return product

    # --------------------------------------------------------
    # Pronoun/context resolution
    # --------------------------------------------------------

    lower = message.lower()

    pronoun_words = [
        "it",
        "its",
        "this",
        "that",
        "the item",
        "the product",
        "the component",
        "the board",
        "who supplies",
        "who sells",
        "supplier",
        "how much is it",
        "what is its stock",
        "reorder it",
    ]

    has_context_reference = any(
        phrase in lower
        for phrase in pronoun_words
    )

    if not has_context_reference:
        return None

    if not conversation_history:
        return None

    # Search backwards.
    for turn in reversed(
        conversation_history
    ):

        content = turn.get(
            "content",
            "",
        )

        if not content:
            continue

        product = detect_product(
            content,
            db,
        )

        if product:

            logger.info(
                "Context product match: '%s' -> '%s'",
                content,
                product,
            )

            return product

    return None


# ============================================================
# INTENT KEYWORDS
# ============================================================

STOCK_KEYWORDS = [
    "stock",
    "inventory",
    "available",
    "availability",
    "quantity",
    "amount",
    "units",
    "how many",
    "do we have",
    "have we got",
    "in stock",
    "do you have",
    "left",
    "remaining",
    "count",
]

LOW_STOCK_KEYWORDS = [
    "low stock",
    "low-stock",
    "lowstock",
    "shortage",
    "below minimum",
    "under minimum",
    "needs reorder",
    "need reorder",
    "running low",
    "running out",
    "out of stock",
]

REORDER_KEYWORDS = [
    "reorder",
    "re-order",
    "re order",
    "order more",
    "place order",
    "create order",
    "replenish",
    "restock",
    "re-stock",
]

SUPPLIER_KEYWORDS = [
    "supplier",
    "who supplies",
    "supplied by",
    "vendor",
    "where to buy",
    "who sells",
    "distributor",
]

ALL_INVENTORY_KEYWORDS = [
    "all inventory",
    "all products",
    "all components",
    "show inventory",
    "show everything",
    "list inventory",
    "list all",
    "show all",
    "view all",
    "entire inventory",
]


def _has_keyword(
    text: str,
    keywords: list[str],
) -> bool:

    lower = text.lower()

    return any(
        keyword in lower
        for keyword in keywords
    )


# ============================================================
# INVENTORY SERIALIZATION
# ============================================================

def _item_to_dict(item) -> dict:

    return {
        "id": item.id,
        "name": item.name,
        "category": item.category,
        "stock": item.stock,
        "min_stock": item.min_stock,
        "supplier": item.supplier,
        "is_low_stock": (
            item.stock <= item.min_stock
        ),
        "last_updated": (
            item.updated_at.isoformat()
            if getattr(
                item,
                "updated_at",
                None,
            )
            else None
        ),
    }


# ============================================================
# LANGCHAIN CHUNK EXTRACTION
# ============================================================

def _extract_chunk_text(
    chunk_content,
) -> str:

    if isinstance(
        chunk_content,
        str,
    ):
        return chunk_content

    if isinstance(
        chunk_content,
        list,
    ):

        output = []

        for part in chunk_content:

            if (
                isinstance(part, dict)
                and "text" in part
            ):
                output.append(
                    part["text"]
                )

            elif isinstance(
                part,
                str,
            ):
                output.append(part)

        return "".join(output)

    return (
        str(chunk_content)
        if chunk_content
        else ""
    )


# ============================================================
# STREAM STATIC RESPONSE
# ============================================================

async def _stream_text(
    text: str,
) -> AsyncGenerator[dict, None]:

    # Stream by small chunks instead of calling Gemini.
    words = text.split(" ")

    for index, word in enumerate(words):

        content = word

        if index < len(words) - 1:
            content += " "

        yield {
            "type": "token",
            "content": content,
        }

        await asyncio.sleep(0.015)


# ============================================================
# MAIN STREAMING AGENT
# ============================================================

async def stream_agent_response(
    message: str,
    conversation_history: list[dict],
    db: Session,
) -> AsyncGenerator[dict, None]:

    lower = message.lower().strip()

    logger.info(
        "User message: %s",
        message,
    )

    # ========================================================
    # 1. LOW STOCK
    # ========================================================

    if _has_keyword(
        lower,
        LOW_STOCK_KEYWORDS,
    ):

        logger.info(
            "Intent: low_stock"
        )

        items = get_low_stock_items(db)

        if not items:

            full_msg = (
                "There are currently no "
                "low-stock items. All "
                "inventory levels are healthy!"
            )

            async for event in _stream_text(
                full_msg
            ):
                yield event

            yield {
                "type": "done",
                "message": full_msg,
                "data": [],
                "data_type": "low_stock",
            }

            return

        data = [
            _item_to_dict(item)
            for item in items
        ]

        lines = []

        for item in items:

            lines.append(
                f"- **{item.name}**: "
                f"{item.stock} units "
                f"(minimum: {item.min_stock}, "
                f"supplier: {item.supplier})"
            )

        full_msg = (
            f"The following **{len(items)} "
            f"item(s)** are currently at "
            f"or below minimum stock:\n\n"
            + "\n".join(lines)
        )

        async for event in _stream_text(
            full_msg
        ):
            yield event

        yield {
            "type": "done",
            "message": full_msg,
            "data": data,
            "data_type": "low_stock",
        }

        return

    # ========================================================
    # 2. ALL INVENTORY
    # ========================================================

    if _has_keyword(
        lower,
        ALL_INVENTORY_KEYWORDS,
    ):

        logger.info(
            "Intent: all_inventory"
        )

        items = get_all_inventory(db)

        data = [
            _item_to_dict(item)
            for item in items
        ]

        full_msg = (
            f"Showing all **{len(items)} "
            f"inventory items** currently "
            f"registered in the database."
        )

        async for event in _stream_text(
            full_msg
        ):
            yield event

        yield {
            "type": "done",
            "message": full_msg,
            "data": data,
            "data_type": "inventory",
        }

        return

    # ========================================================
    # 3. PRODUCT DETECTION
    # ========================================================

    product_name = (
        resolve_product_with_context(
            message,
            conversation_history,
            db,
        )
    )

    logger.info(
        "Detected product: %s",
        product_name,
    )

    # ========================================================
    # 4. PRODUCT INVENTORY
    # ========================================================

    if product_name:

        product = get_component(
            db,
            product_name,
        )

        if product:

            logger.info(
                "Database product found: "
                "%s | stock=%s",
                product.name,
                product.stock,
            )

            item_data = _item_to_dict(
                product
            )

            # ------------------------------------------------
            # REORDER
            # ------------------------------------------------

            if _has_keyword(
                lower,
                REORDER_KEYWORDS,
            ):

                logger.info(
                    "Intent: reorder"
                )

                qty = max(
                    product.min_stock
                    - product.stock,
                    25,
                )

                reorder = (
                    create_reorder_request(
                        db=db,
                        item_id=product.id,
                        quantity=qty,
                    )
                )

                if reorder:

                    full_msg = (
                        f"A reorder request for "
                        f"**{qty} units** of "
                        f"**{product.name}** "
                        f"has been created.\n\n"
                        f"Supplier: **{product.supplier}**\n"
                        f"Status: **Pending**"
                    )

                else:

                    full_msg = (
                        f"Could not create "
                        f"a reorder request "
                        f"for {product.name}."
                    )

                async for event in _stream_text(
                    full_msg
                ):
                    yield event

                yield {
                    "type": "done",
                    "message": full_msg,
                    "data": item_data,
                    "data_type": "reorder",
                }

                return

            # ------------------------------------------------
            # SUPPLIER
            # ------------------------------------------------

            if _has_keyword(
                lower,
                SUPPLIER_KEYWORDS,
            ):

                full_msg = (
                    f"**{product.name}** is "
                    f"supplied by "
                    f"**{product.supplier}**."
                )

                async for event in _stream_text(
                    full_msg
                ):
                    yield event

                yield {
                    "type": "done",
                    "message": full_msg,
                    "data": item_data,
                    "data_type": "component",
                }

                return

            # ------------------------------------------------
            # STOCK
            # ------------------------------------------------

            if _has_keyword(
                lower,
                STOCK_KEYWORDS,
            ):

                logger.info(
                    "Intent: stock query"
                )

                status = (
                    "⚠ Low Stock"
                    if product.stock
                    <= product.min_stock
                    else "✓ In Stock"
                )

                full_msg = (
                    f"**{product.name}** has "
                    f"**{product.stock} units** "
                    f"in stock.\n\n"
                    f"- **Category:** "
                    f"{product.category}\n"
                    f"- **Minimum Stock:** "
                    f"{product.min_stock} units\n"
                    f"- **Supplier:** "
                    f"{product.supplier}\n"
                    f"- **Status:** {status}"
                )

                async for event in _stream_text(
                    full_msg
                ):
                    yield event

                yield {
                    "type": "done",
                    "message": full_msg,
                    "data": [item_data],
                    "data_type": "component",
                }

                return

            # ------------------------------------------------
            # GENERAL PRODUCT
            # ------------------------------------------------

            status = (
                "⚠ Low Stock"
                if product.stock
                <= product.min_stock
                else "✓ In Stock"
            )

            full_msg = (
                f"**{product.name}**\n\n"
                f"- **Category:** "
                f"{product.category}\n"
                f"- **Current Stock:** "
                f"{product.stock} units\n"
                f"- **Minimum Stock:** "
                f"{product.min_stock} units\n"
                f"- **Supplier:** "
                f"{product.supplier}\n"
                f"- **Status:** {status}"
            )

            async for event in _stream_text(
                full_msg
            ):
                yield event

            yield {
                "type": "done",
                "message": full_msg,
                "data": [item_data],
                "data_type": "component",
            }

            return

    # ========================================================
    # 5. IMPORTANT:
    # INVENTORY QUESTION BUT PRODUCT NOT FOUND
    # ========================================================

    if _has_keyword(
        lower,
        STOCK_KEYWORDS,
    ):

        logger.info(
            "Inventory question but "
            "no product resolved."
        )

        full_msg = (
            "I couldn't identify a specific "
            "inventory product in your request. "
            "Please provide the product name."
        )

        async for event in _stream_text(
            full_msg
        ):
            yield event

        yield {
            "type": "done",
            "message": full_msg,
            "data": [],
            "data_type": "inventory",
        }

        return

    # ========================================================
    # 6. GEMINI / RAG FALLBACK
    # ========================================================

    logger.info(
        "Intent: LangChain Gemini "
        "streaming / knowledge"
    )

    knowledge_results = retrieve(
        message
    )

    knowledge_context = ""

    if knowledge_results:

        knowledge_context = "\n\n".join(
            [
                (
                    f"Source ({result['source']}): "
                    f"{result['text']}"
                )
                for result in knowledge_results
            ]
        )

    messages = [
        SystemMessage(
            content=SYSTEM_PROMPT
        )
    ]

    if knowledge_context:

        messages.append(
            SystemMessage(
                content=(
                    "Relevant Knowledge Base "
                    "Information:\n"
                    f"{knowledge_context}"
                )
            )
        )

    # Conversation memory.
    if conversation_history:

        for turn in conversation_history[-8:]:

            role = turn.get("role")

            content = turn.get(
                "content",
                "",
            )

            if not content:
                continue

            if role == "user":

                messages.append(
                    HumanMessage(
                        content=content
                    )
                )

            elif role == "assistant":

                messages.append(
                    AIMessage(
                        content=content
                    )
                )

    messages.append(
        HumanMessage(
            content=message
        )
    )

    full_response_text = ""

    try:

        llm = get_llm()

        async for chunk in llm.astream(
            messages
        ):

            token_text = (
                _extract_chunk_text(
                    chunk.content
                )
            )

            if token_text:

                full_response_text += (
                    token_text
                )

                yield {
                    "type": "token",
                    "content": token_text,
                }

    except Exception as exc:

        logger.exception(
            "LangChain streaming error"
        )

        full_response_text = (
            "I encountered an issue "
            "processing your request with "
            "the AI model. Please try again."
        )

        yield {
            "type": "token",
            "content": full_response_text,
        }

    yield {
        "type": "done",
        "message": full_response_text,
        "data": [],
        "data_type": "ai",
    }


# ============================================================
# COMPATIBILITY WRAPPER
# ============================================================

async def ask_agent(
    message: str,
    db: Session,
    conversation_history: list[dict] | None = None,
) -> dict:

    history = (
        conversation_history
        or []
    )

    full_text = ""
    final_data = []
    final_type = "ai"

    async for event in stream_agent_response(
        message,
        history,
        db,
    ):

        if event["type"] == "done":

            full_text = event.get(
                "message",
                "",
            )

            final_data = event.get(
                "data",
                [],
            )

            final_type = event.get(
                "data_type",
                "ai",
            )

    return {
        "type": final_type,
        "message": full_text,
        "answer": full_text,
        "data": final_data,
        "sources": [
            "live_inventory",
            "knowledge_base",
        ],
        "mode": "agent",
    }