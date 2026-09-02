# Inventory Management Chatbot

An AI-powered inventory management system that combines **Excel-based inventory data, MongoDB, Gemini AI, RAG, real-time WebSocket chat, analytics, and inventory management** in a single application.

The system is designed for company employees to easily check inventory, manage stock, view analytics, and interact with inventory data using a natural-language AI assistant.

## Features

- AI-powered inventory assistant using Gemini
- Real-time chatbot using WebSockets
- Multiple chat conversations
- Persistent conversation history
- Employee authentication
- Inventory dashboard
- Inventory search and management
- Edit inventory items from the application
- Excel file integration
- Multiple Excel sheet support
- Automatic category and subcategory identification
- Data normalization and duplicate detection
- MongoDB integration
- Inventory analytics and KPIs
- Low-stock monitoring
- RAG-based company knowledge retrieval
- Master Sheet generation and download

## Data Flow

Excel is used as the main source of inventory data.

```text
Excel Files
    ↓
Excel Parser
    ↓
Normalization & Categorization
    ↓
Duplicate Detection
    ↓
MongoDB
    ↓
Inventory Dashboard / Analytics / AI Assistant
```

Multiple Excel sheets can be processed and consolidated into a single Master Sheet.

## AI Assistant

The AI Assistant allows employees to interact with inventory using normal language.

Example:

```text
User: How many ESP32 DevKit units are available?

Assistant: There are 24 ESP32 DevKit units currently available.
```

The chatbot uses:

- Gemini AI
- Inventory data
- Conversation memory
- RAG
- FAISS
- WebSocket streaming

The AI decides when inventory information is required and retrieves the relevant information before generating the response.

## Real-Time Chat

Chat communication is handled through WebSockets.

```text
User
 ↓
WebSocket
 ↓
Chat Service
 ↓
AI / Inventory / RAG
 ↓
Gemini
 ↓
Streaming Response
 ↓
User
```

WebSocket endpoint:

```text
/ws/chat
```

Each employee can create multiple conversations and access their previous conversation history.

## Inventory Dashboard

The dashboard provides access to:

- Total inventory items
- Current stock levels
- Low-stock items
- Categories
- Suppliers
- Inventory analytics
- Inventory search
- Product details

Inventory items can also be edited directly from the application.

## Excel Integration

The application supports multiple Excel sheets and inventory categories.

Example:

```text
Inventory.xlsx

├── Electronics
├── Sensors
├── Cables
├── Nuts & Bolts
└── Mechanical
```

The Excel processing system handles:

- Parsing
- Normalization
- Category detection
- Subcategory detection
- Duplicate detection
- Data validation
- MongoDB synchronization
- Master Sheet generation

## Master Sheet

The Master Sheet combines inventory information from multiple Excel sheets into a single consolidated inventory view.

It can include:

- Component name
- Category
- Subcategory
- Supplier
- Price
- Current stock
- Minimum stock
- Status

The Master Sheet can also be downloaded from the application.

## Project Structure

```text
inventory-chatbot/
│
├── ai/                  # Gemini, RAG, prompts, memory and AI tools
├── database/            # MongoDB and database repositories
├── excel/               # Excel parsing and processing
├── frontend/            # HTML, CSS and JavaScript frontend
├── routes/              # FastAPI HTTP and WebSocket routes
├── services/            # Application business logic
├── data/                # Application and knowledge data
│
├── app.py               # FastAPI application entry point
├── config.py            # Application configuration
├── requirements.txt     # Python dependencies
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Technology Stack

### Backend

- Python
- FastAPI
- WebSockets

### Database

- MongoDB

### AI

- Google Gemini
- LangChain
- FAISS
- Embeddings
- RAG

### Data Processing

- Pandas
- OpenPyXL

### Frontend

- HTML
- CSS
- JavaScript

## Installation

Clone the repository:

```powershell
git clone https://github.com/ujjawal-agalcha/inventory-chatbot.git
cd inventory-chatbot
```

Create a virtual environment:

```powershell
python -m venv venv
```

Activate it on Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

## Environment Variables

Create/configure the `.env` file using `.env.example`.

Example:

```env
GEMINI_API_KEY=your_gemini_api_key

MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=inventory_chatbot

JWT_SECRET_KEY=your_secret_key
JWT_ALGORITHM=HS256
```

Do not commit API keys, passwords, database credentials, or other secrets to GitHub.

## Run the Application

Start MongoDB and then run:

```powershell
python -m uvicorn app:app --reload --port 8001
```

Open:

```text
http://127.0.0.1:8001
```

## Basic User Workflow

```text
Employee Login
      ↓
Dashboard
      ↓
AI Assistant / Inventory
      ↓
Ask Questions or View Inventory
      ↓
Inventory Data + AI Processing
      ↓
Real-Time Response / Analytics
```

Employees can also create multiple conversations, open previous conversations, search inventory, view stock levels, access analytics, and work with the consolidated Master Sheet.

## Repository

https://github.com/ujjawal-agalcha/inventory-chatbot

## Project Status

**Completed**

The application provides an integrated inventory management platform with Excel-based data processing, MongoDB, real-time AI chat, inventory management, analytics, conversation history, and Master Sheet functionality.