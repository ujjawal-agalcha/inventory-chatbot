# 🤖 AI Inventory Management Chatbot

An AI-powered Inventory Management System for electronic and IoT components, built with **FastAPI, SQLite, SQLAlchemy, Google Gemini, RAG, FAISS, and JavaScript**.

The system combines a traditional inventory management backend with an AI chatbot that allows users to interact with inventory using natural language.

Instead of manually searching through inventory tables, users can ask questions such as:

> "How many ESP32-CAM are in stock?"

> "Which components are low in stock?"

> "Who supplies the Arduino Uno?"

> "Reorder ESP32-CAM."

The chatbot understands the request, identifies the relevant product and intent, retrieves live information from the database when required, and returns the result through the web interface.

---

## ✨ Features

### 💬 AI Inventory Chatbot

Users can interact with the inventory system using natural language.

Examples:

```text
How many ESP32-CAM are in stock?
How many ESP32 development boards are available?
What is the stock of Arduino Uno?
Which items are low in stock?
Who supplies ESP32-CAM?
Show me all inventory.
Reorder ESP32-CAM.
```

---

### 📦 Live Inventory Information

Stock-related questions are answered using the **actual inventory database**, rather than relying on the AI's general knowledge.

The system can provide:

* Product name
* Category
* Current stock
* Minimum stock level
* Stock status
* Supplier
* Last updated information

This prevents the AI from inventing stock quantities.

---

### ⚠️ Low-Stock Monitoring

The system automatically identifies items where:

```text
Current Stock <= Minimum Stock
```

Users can ask:

```text
Which components are low in stock?
```

or:

```text
Is ESP32-CAM low in stock?
```

The chatbot retrieves the result directly from the database.

---

### 🔄 Reorder Management

The system supports inventory reorder requests.

Typical workflow:

```text
Low Stock Detected
        ↓
User Requests Reorder
        ↓
Product Identified
        ↓
Reorder Quantity Calculated
        ↓
Reorder Request Created
        ↓
Stored in Database
```

Reorder requests can be tracked through the backend.

---

### 🧠 AI + RAG

The chatbot uses **Google Gemini** for natural-language understanding and generation.

For product/company/general knowledge, the system uses **Retrieval-Augmented Generation (RAG)**.

The RAG pipeline is:

```text
User Question
      ↓
Embedding Generation
      ↓
FAISS Similarity Search
      ↓
Relevant Knowledge Chunks
      ↓
Gemini
      ↓
Natural Language Response
```

This allows the chatbot to answer questions using the project's knowledge base.

---

### 🔎 Product Recognition

The chatbot supports multiple ways of referring to the same product.

For example:

```text
ESP32-CAM
ESP32 Cam
ESP32CAM
```

are recognized as:

```text
ESP32-CAM
```

Similarly:

```text
ESP32 DevKit
ESP32 Dev Board
ESP32 Development Board
ESP32 DevKit V1
```

are mapped to:

```text
ESP32 DevKit V1
```

This is handled through the product alias and detection system.

---

## 🧩 Architecture

The application follows a layered architecture:

```text
                         ┌───────────────┐
                         │     USER      │
                         └───────┬───────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │     Web Dashboard      │
                    │     HTML/CSS/JS        │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │        FastAPI         │
                    │         app.py         │
                    └────────────┬───────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │    Inventory Agent     │
                    │   agent_service.py     │
                    └────────────┬───────────┘
                                 │
                     ┌───────────┴───────────┐
                     │                       │
                     ▼                       ▼
          ┌───────────────────┐    ┌───────────────────┐
          │ Live Inventory DB │    │   RAG Knowledge   │
          │ SQLite + SQLAlchemy│    │ FAISS + Embeddings│
          └─────────┬─────────┘    └─────────┬─────────┘
                    │                        │
                    └───────────┬────────────┘
                                ▼
                       ┌────────────────┐
                       │  Google Gemini │
                       └───────┬────────┘
                               │
                               ▼
                       ┌────────────────┐
                       │ Final Response │
                       └────────────────┘
```

---

## 🔄 Chatbot Request Flow

For a live inventory question:

```text
User:
"How many ESP32-CAM are in stock?"
        ↓
Frontend JavaScript
        ↓
POST /api/chat
        ↓
FastAPI
        ↓
agent_service.py
        ↓
Intent Detection
        ↓
Product Detection
        ↓
Inventory Service
        ↓
SQLite Database
        ↓
Actual Stock Information
        ↓
Response
        ↓
Frontend Chat Interface
```

For a general knowledge question:

```text
User Question
      ↓
Inventory Agent
      ↓
RAG Service
      ↓
FAISS Search
      ↓
Relevant Knowledge
      ↓
Google Gemini
      ↓
AI Response
```

---

# 📁 Project Structure

```text
inventory-chatbot/
│
├── app.py
├── agent_service.py
├── models.py
├── database.py
├── config.py
├── auth.py
├── rag_service.py
├── mcp_server.py
├── inventory_data.py
├── seed_data.py
│
├── services/
│   └── inventory_service.py
│
├── static/
│   └── script.js
│
├── templates/
│   └── chat.html
│
├── data/
│   └── knowledge/
│
├── requirements.txt
├── docker-compose.yml
├── .env.example
└── README.md
```

---

# 📄 File Responsibilities

| File                            | Purpose                                             |
| ------------------------------- | --------------------------------------------------- |
| `app.py`                        | Main FastAPI application and API routes             |
| `agent_service.py`              | AI agent, intent detection and product detection    |
| `models.py`                     | SQLAlchemy database models and sessions             |
| `database.py`                   | Database initialization/schema utilities            |
| `config.py`                     | Environment variables and application configuration |
| `auth.py`                       | Authentication/OAuth configuration                  |
| `rag_service.py`                | RAG, embeddings and FAISS knowledge retrieval       |
| `mcp_server.py`                 | MCP tools for AI-based inventory access             |
| `inventory_data.py`             | Inventory data definitions                          |
| `seed_data.py`                  | Initial database inventory                          |
| `services/inventory_service.py` | Inventory business logic and database operations    |
| `static/script.js`              | Frontend JavaScript and API communication           |
| `templates/chat.html`           | Main chatbot/dashboard interface                    |
| `data/knowledge/`               | Documents used by the RAG system                    |

---

# 🛠️ Technology Stack

## Backend

* Python
* FastAPI
* SQLAlchemy
* SQLite
* Pydantic

## AI

* Google Gemini
* Retrieval-Augmented Generation (RAG)
* Sentence Transformers
* FAISS

## Frontend

* HTML
* CSS
* JavaScript
* Jinja2

## Authentication

* Authentik
* OAuth / OpenID Connect

## AI Integration

* Model Context Protocol (MCP)
* FastMCP

---

# 📦 Inventory Categories

The seeded inventory contains IoT and electronic components across multiple categories.

### ESP Modules

* ESP32-CAM
* ESP32 DevKit V1
* ESP8266 NodeMCU
* ESP32 WROOM
* ESP32-S3 DevKit

### Arduino Boards

* Arduino Uno R3
* Arduino Nano
* Arduino Mega 2560
* Arduino Leonardo

### Motor Drivers

* L298N Motor Driver
* BTS7960 Motor Driver
* TB6612FNG Motor Driver

### Motors

* DC Gear Motor 12V
* SG90 Servo Motor
* MG996R Servo Motor
* NEMA 17 Stepper Motor

### Sensors

* HC-SR04 Ultrasonic Sensor
* PIR Motion Sensor
* DHT11 Temperature Sensor
* DHT22 Temperature Sensor
* IR Obstacle Sensor
* MPU6050 Gyroscope

### Batteries

* 18650 Li-ion Battery
* 3.7V LiPo Battery
* 9V Rechargeable Battery

### Displays

* 16x2 LCD Display
* 0.96 inch OLED Display
* 2.4 inch TFT Display

### Relay Modules

* 1 Channel Relay Module
* 4 Channel Relay Module

### Communication Modules

* HC-05 Bluetooth Module
* SIM800L GSM Module
* NEO-6M GPS Module

### Electronic Components

* 220 Ohm Resistor Pack
* 10K Ohm Resistor Pack
* 100uF Capacitor Pack
* LED 5mm Assorted Pack
* Breadboard 830 Point
* Jumper Wire Kit

---

# 💬 Chatbot Capabilities

## Stock Queries

```text
How many ESP32-CAM are in stock?
How many ESP32 DevKit boards do we have?
What is the stock of Arduino Uno?
Is L298N available?
How many sensors are available?
```

## Low-Stock Queries

```text
Which items are low in stock?
Show me low-stock components.
Is ESP32-CAM low in stock?
Which products need to be reordered?
```

## Supplier Queries

```text
Who supplies ESP32-CAM?
Who is the supplier of Arduino Uno?
Show me the supplier for L298N.
```

## Product Information

```text
What is ESP32-CAM?
What is Arduino Uno used for?
Tell me about HC-SR04.
What is the difference between ESP32 and ESP8266?
```

## Reorder Queries

```text
Reorder ESP32-CAM.
I want to reorder Arduino Uno.
Create a reorder request for L298N.
```

---

# 🔌 API Endpoints

## Inventory

### Get all inventory

```http
GET /api/inventory
```

### Get low-stock inventory

```http
GET /api/inventory/low-stock
```

### Get inventory statistics

```http
GET /api/inventory/stats
```

### Get a specific component

```http
GET /api/inventory/component/{name}
```

### Search inventory

```http
GET /api/inventory/search?q={query}
```

### Update stock

```http
PUT /api/inventory/{item_id}/stock
```

---

## Reorders

### Create reorder request

```http
POST /api/reorders
```

### Get reorder requests

```http
GET /api/reorders
```

---

## Chatbot

### Send chatbot message

```http
POST /api/chat
```

Example request:

```json
{
  "message": "How many ESP32-CAM are in stock?"
}
```

---

# 🗄️ Database

The project uses **SQLite** with **SQLAlchemy ORM**.

The main inventory model contains information such as:

```text
id
name
category
stock
min_stock
supplier
created_at
updated_at
```

Reorder requests contain:

```text
id
item_id
quantity
supplier
status
created_at
```

### Low Stock Logic

An item is considered low stock when:

```text
current_stock <= minimum_stock
```

This calculation is performed using live database values.

---

# 🧠 AI Agent Logic

The chatbot does not send every question directly to Gemini.

Instead, it first analyzes the request.

```text
User Message
     ↓
Intent Detection
     ↓
Product Detection
     ↓
 ┌─────────────────────────┐
 │                         │
 ▼                         ▼
Inventory Query        Knowledge Query
 │                         │
 ▼                         ▼
SQLite DB                  RAG
 │                         │
 └─────────────┬───────────┘
               ▼
           Gemini AI
               ↓
          Final Response
```

This approach ensures that dynamic inventory information is retrieved from the database.

---

# 🔍 Product Detection

The agent supports product aliases to handle natural language.

For example:

```text
"ESP32 dev board"
"ESP32 development board"
"ESP32 DevKit"
"ESP32 DevKit V1"
```

are normalized to:

```text
ESP32 DevKit V1
```

Similarly:

```text
"ESP32 cam"
"ESP32-CAM"
"ESP32CAM"
```

are normalized to:

```text
ESP32-CAM
```

The system can also search the inventory database when an exact alias is not found.

---

# 📚 RAG System

The RAG system uses:

* Sentence Transformers
* FAISS
* Knowledge documents
* Google Gemini

The process is:

```text
Knowledge Documents
       ↓
Text Chunking
       ↓
Embeddings
       ↓
FAISS Vector Index
       ↓
Similarity Search
       ↓
Relevant Context
       ↓
Gemini
       ↓
Answer
```

This allows the chatbot to answer questions using information from the project's knowledge base.

---

# 🔧 Setup

## 1. Clone the repository

```bash
git clone https://github.com/ujjawal-agalcha/inventory-chatbot.git
```

```bash
cd inventory-chatbot
```

---

## 2. Create a virtual environment

### Windows

```powershell
python -m venv venv
```

Activate it:

```powershell
.\venv\Scripts\Activate.ps1
```

### Linux/macOS

```bash
python3 -m venv venv
```

```bash
source venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure environment variables

Create a `.env` file based on `.env.example`.

Example:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=your_gemini_model

SESSION_SECRET=your_session_secret

AUTHENTIK_BASE_URL=your_authentik_url
AUTHENTIK_CLIENT_ID=your_client_id
AUTHENTIK_CLIENT_SECRET=your_client_secret
AUTHENTIK_REDIRECT_URI=http://127.0.0.1:8001/auth/callback
```

Do not commit `.env` or API keys to GitHub.

---

# 🗃️ Initialize the Database

Run the database/seed setup provided by the project.

The seed process creates the initial inventory data.

After initialization, the database contains the electronic and IoT components used by the application.

---

# ▶️ Run the Application

Start FastAPI with:

```bash
python -m uvicorn app:app --reload --port 8001
```

Then open:

```text
http://127.0.0.1:8001/chat
```

---

# 🧪 Testing the Chatbot

After starting the application, try:

```text
How many ESP32-CAM are in stock?
```

Then:

```text
How many ESP32 dev boards are available?
```

Then:

```text
Which items are low in stock?
```

Then:

```text
Who supplies ESP32-CAM?
```

And:

```text
What is ESP32-CAM?
```

These test different parts of the system:

```text
Live Inventory
Product Detection
Low Stock Logic
Supplier Information
RAG / AI Knowledge
```

---

# 🔐 Security

Sensitive configuration values should be stored in environment variables.

Examples:

* Gemini API key
* Authentik client secret
* Session secret
* OAuth credentials

Never commit these values to the repository.

The `.env` file should remain local.

---

# 🔌 MCP Integration

The project also includes an MCP server that exposes inventory operations as tools for AI agents.

Example capabilities include:

```text
get_product_stock()
search_products()
get_low_stock_products()
get_inventory_statistics()
get_all_products()
```

The MCP tools use the same inventory/database layer, allowing external AI agents to interact with the inventory system without directly accessing the database.

---

# 🏗️ Design Principles

The project follows several important principles:

### 1. Live data comes from the database

The AI does not guess inventory quantities.

```text
Stock Question
      ↓
Database
      ↓
Actual Stock
```

### 2. AI handles natural language

Gemini is used to understand and generate conversational responses.

### 3. RAG handles project knowledge

The knowledge base provides additional context for product and company-related questions.

### 4. Business logic stays outside the frontend

Inventory operations are handled by the backend/service layer.

### 5. Database is the source of truth

The dashboard, chatbot and MCP tools should use the same inventory data.

---

# 🚀 Future Improvements

Potential improvements include:

* Real-time inventory notifications
* Email alerts for low-stock products
* Automated supplier communication
* Purchase order generation
* Advanced inventory analytics
* Role-based access control
* Voice-based inventory assistant
* Barcode/QR-code inventory scanning
* Demand prediction using machine learning
* Automated stock forecasting
* Multi-user inventory management
* Cloud database support
* Deployment using Docker

---

# 👨‍💻 Project Goal

The goal of this project is to demonstrate how **AI can be integrated with a traditional inventory management system**.

Instead of replacing the existing database and business logic with an AI model, the project uses AI as an intelligent interface over reliable backend services.

The key concept is:

```text
                AI
                 │
                 ▼
        Natural Language
                 │
                 ▼
        Inventory Agent
                 │
        ┌────────┴────────┐
        ▼                 ▼
   Live Database       Knowledge Base
        │                 │
        ▼                 ▼
 Actual Inventory       RAG + Gemini
        │                 │
        └────────┬────────┘
                 ▼
           User Response
```

This makes the system more reliable, extensible and suitable for real-world inventory management.

---

# 📄 License

This project is intended for educational, development and demonstration purposes.
