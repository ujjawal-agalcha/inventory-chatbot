# Inventory Management System

A web-based **Inventory Management System with an interactive chatbot interface** built using FastAPI, SQLAlchemy, SQLite, Jinja2, and Authentik authentication.

The system is designed to help users manage electronic components, monitor stock levels, identify low-stock products, search inventory, update stock quantities, and create and track reorder requests through a simple web interface.

---

## 📌 Project Overview

The Inventory Management System provides a centralized platform for managing electronic component inventory.

Instead of navigating through multiple pages or manually searching a database, users can interact with the system through a **chat-based interface** to retrieve inventory information.

The application supports:

- User authentication through Authentik
- Inventory management
- Component search
- Category-based inventory lookup
- Low-stock detection
- Stock quantity updates
- Reorder request creation
- Reorder history
- Inventory statistics
- Chat-based inventory queries
- REST API endpoints for frontend/backend communication

The application uses a SQLite database through SQLAlchemy for storing inventory and reorder information.

---

## ✨ Features

### 🔐 Authentication

Users authenticate through **Authentik OAuth/OpenID Connect**.

After successful authentication, the user is redirected to the inventory chatbot dashboard.

The application stores authenticated user information in a session.

---

### 📦 Inventory Management

The system stores information about inventory components including:

- Component name
- Category
- Current stock
- Minimum required stock
- Supplier
- Last updated timestamp

Example inventory items include:

- ESP32-CAM
- ESP32 DevKit V1
- ESP8266 NodeMCU
- Arduino Uno R3
- Arduino Mega 2560
- L298N Motor Driver
- HC-SR04 Ultrasonic Sensor
- DHT11 Temperature Sensor
- 18650 Li-ion Battery
- OLED Display
- Relay Modules
- Bluetooth and GSM modules
- Resistor and capacitor packs
- Breadboards and jumper wires

---

### 🤖 Inventory Chatbot

The application provides a chatbot-style interface that allows users to ask inventory-related questions.

Examples:

```text
Show low stock items