# Inventory Management Chatbot

An AI-powered inventory management system that combines a real-time WebSocket chatbot, Excel-based inventory management, MongoDB, analytics, and employee authentication into a single application.

The system is designed for company employees to check inventory, monitor stock levels, manage conversations, view analytics, and work with continuously synchronized Excel inventory data.

---

## Overview

The Inventory Management Chatbot provides two primary interfaces:

1. **AI Assistant**
   - Natural-language conversations
   - Real-time WebSocket communication
   - Inventory-related queries
   - Previous conversation history
   - Multiple conversations per employee
   - AI-powered responses using Gemini
   - RAG support for company knowledge

2. **Inventory Dashboard**
   - Current inventory
   - Stock levels
   - Low-stock monitoring
   - Supplier information
   - Inventory editing
   - KPIs and analytics
   - On-demand charts
   - Master Sheet generation/download

### Data Source

**Excel is the single source of truth for inventory data.**

MongoDB is used as the application's operational database and synchronized working store.

```text
Excel Files
    │
    ▼
Excel Synchronization
    │
    ▼
Data Validation / Normalization
    │
    ▼
MongoDB
    │
    ├── Inventory Dashboard
    ├── Analytics
    └── AI Assistant