# 🚀 Emplytics: AI-Powered Employee Analytics

Emplytics is a premium, high-fidelity AI chat application designed for professional employee data management and natural language analytics. It combines a sleek, modern "Apple-esque" monochrome interface with a powerful AI backend capable of executing SQL queries and managing complex chat histories.

![Emplytics Preview](https://via.placeholder.com/800x400?text=Emplytics+AI+Chat+Interface)

## ✨ Key Features

- **🧠 Natural Language SQL Agent**: Ask questions about your employees (e.g., "Show me the top 5 earners in IT") and get instant, accurately formatted results.
- **🔐 Secure Authentication**: Full user lifecycle management including Signup, Login, and **OTP verification** via email.
- **💾 Cloud-Native Storage**: Powered by **Supabase (PostgreSQL)** for reliable, persistent data storage across deployments.
- **🎨 Premium UI/UX**: High-contrast monochrome design system with smooth animations, glassmorphism effects, and a mobile-responsive layout.
- **💬 Persistent Chat History**: Cloud-saved chat sessions with title generation and message memory.
- **📊 Data Export**: Export chat results and data reports directly to PDF.

## 🛠️ Tech Stack

- **Frontend**: HTML5, Vanilla CSS (Modern Design Tokens), JavaScript (ES6+)
- **Backend**: Python, FastAPI, Uvicorn
- **Database**: PostgreSQL (Supabase)
- **AI Engine**: OpenAI / GLM-4 / DeepSeek (LLM with Tool Calling)
- **Deployment**: Render-ready configuration

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.9+
- A Supabase Project (PostgreSQL)
- OpenAI-compatible API Key

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/dhyey-2508-patel/Emplytics.git
cd Emplytics

# Install dependencies
pip install -r new_app/backend/requirements.txt
```

### 3. Environment Setup
Create a `.env` file in the root directory:
```env
DATABASE_URL=your_supabase_connection_string
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.yourprovider.com/v1
MODEL_NAME=glm-4.7:cloud
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
```

### 4. Data Migration
To move your local data to the cloud database:
```bash
python migrate_to_supabase.py
```

### 5. Running Locally
```bash
cd new_app/backend
uvicorn main:app --reload
```
Visit `http://127.0.0.1:8000` in your browser.

## 📂 Project Structure

```text
├── new_app/
│   ├── backend/         # FastAPI Server, SQL Tools, DB Config
│   └── frontend/        # Premium HTML/CSS/JS files
├── migrate_to_supabase.py # Data migration utility
├── .env                 # Environment variables (secret)
└── requirements.txt     # Python dependencies
```

## ☁️ Deployment
This project is pre-configured for **Render**:
- **Root Directory**: `new_app/backend`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

---
Developed with ❤️ by [Dhyey Patel](https://github.com/dhyey-2508-patel)
