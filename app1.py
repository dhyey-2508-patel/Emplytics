import streamlit as st
import json
import os
import uuid
import random
import smtplib
import user_db
from email.mime.text import MIMEText
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from tools import run_sql_query
from memory import add_question, get_first_question, get_last_questions
import re
from fpdf import FPDF

def generate_chat_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    title = st.session_state.get("current_user_name", "User") + " - Chat Export"
    title = re.sub(r'[^\x20-\x7E]', '', title)
    
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, title, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    
    msgs = st.session_state.messages
    i = 0
    while i < len(msgs):
        msg = msgs[i]
        role = msg.get("role", "")
        if role in ["system", "tool"]:
            i += 1
            continue
            
        content = msg.get("content", "") or ""
        
        if role == "user":
            pdf.set_font("helvetica", "B", 11)
            pdf.cell(0, 8, "User:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("helvetica", "", 11)
            pdf.multi_cell(0, 6, re.sub(r'[^\x20-\x7E\r\n\t]', '', content))
            pdf.ln(5)
            i += 1
        elif role == "assistant":
            tool_calls = msg.get("tool_calls")
            final_answer = ""
            
            if tool_calls:
                j = i + 1
                while j < len(msgs):
                    next_msg = msgs[j]
                    if next_msg.get("role") == "user":
                        break
                    if next_msg.get("role") == "assistant" and not next_msg.get("tool_calls"):
                        final_answer = next_msg.get("content", "") or ""
                        break
                    j += 1
                
                query_blocks = []
                for tc in tool_calls:
                    func = tc.get("function", {})
                    args_data = func.get("arguments", "{}")
                    try:
                        args_dict = json.loads(args_data) if isinstance(args_data, str) else args_data
                        query_str = args_dict.get("query", str(args_dict))
                        query_blocks.append(f"[Executing Database Query]:\n{query_str}")
                    except Exception:
                        query_blocks.append(f"[Executing Action]:\n{args_data}")
                
                tool_text = "\n\n".join(query_blocks)
                
                if final_answer:
                    content = tool_text + "\n\n" + final_answer
                    i = j + 1
                else:
                    content = tool_text
                    i += 1
            else:
                i += 1
                
            pdf.set_font("helvetica", "B", 11)
            pdf.cell(0, 8, "AI Agent:", new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_font("helvetica", "", 11)
            pdf.multi_cell(0, 6, re.sub(r'[^\x20-\x7E\r\n\t]', '', content))
            pdf.ln(5)
        
    return bytes(pdf.output())

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

MODEL = os.getenv("MODEL_NAME")

# ---------------- TOOL DEFINITION ----------------
tools = [
    {
        "type": "function",
        "function": {
            "name": "run_sql_query",
            "description": "Execute SQL query on employee database",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# ---------------- SESSION STATE ----------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = {}

if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None

if "rename_chat_id" not in st.session_state:
    st.session_state.rename_chat_id = None

if "rename_new_title" not in st.session_state:
    st.session_state.rename_new_title = ""

if "messages" not in st.session_state:
    st.session_state.messages = []

if "show_history" not in st.session_state:
    st.session_state.show_history = False

if "sidebar_visible" not in st.session_state:
    st.session_state.sidebar_visible = True

# ---------------- AUTHENTICATION STATE ----------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "auth_step" not in st.session_state:
    st.session_state.auth_step = "email"
if "sent_otp" not in st.session_state:
    st.session_state.sent_otp = None
if "auth_email" not in st.session_state:
    st.session_state.auth_email = ""

def send_otp_email(user_email, otp_code):
    try:
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASS")
        
        if not smtp_user or not smtp_pass:
            st.warning("⚠️ SMTP Credentials not configured in .env! (Using offline bypass OTP: 123456)")
            st.session_state.sent_otp = "123456" 
            return True
        
        msg = MIMEText(f"Your secure login OTP for Employee AI Agent is: {otp_code}")
        msg['Subject'] = 'Employee AI Agent - Secure Login OTP'
        msg['From'] = smtp_user
        msg['To'] = user_email
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

def init_new_chat():
    """Save current chat if exists, then create new"""
    if st.session_state.current_chat_id and st.session_state.messages:
        user_msgs = [m for m in st.session_state.messages if m.get("role") == "user"]
        title = "New Chat"
        if user_msgs:
            first = user_msgs[0]["content"]
            title = first[:25] + "..." if len(first) > 25 else first
        
        # Save to session
        timestamp = datetime.now().strftime("%H:%M")
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        st.session_state.chat_history[st.session_state.current_chat_id] = {
            "title": title,
            "messages": st.session_state.messages.copy(),
            "timestamp": timestamp,
            "date": date_str
        }
        # Save to SQLite DB permanently
        if getattr(st.session_state, "authenticated", False):
            user_db.save_chat(st.session_state.auth_email, st.session_state.current_chat_id, title, st.session_state.messages, timestamp, date_str)
    
    chat_id = str(uuid.uuid4())
    st.session_state.current_chat_id = chat_id
    st.session_state.messages = [
        {
        "role": "system",
        "content": """
You are an AI assistant designed ONLY to answer questions about an employee database.

Database details:
Table name: employees

Columns:
id
name
email
mobile
location
department
salary

Your responsibilities:
- Answer questions ONLY related to the employee database.
- Generate SQL queries when required and call the tool `run_sql_query` to retrieve information.
- Explain results clearly to the user when necessary.

STRICT RULES:
1. Do NOT answer questions that are unrelated to the employee database.
2. If the user asks anything outside the employee database, you must refuse.
3. When refusing, respond ONLY with this sentence:

"I am an Employee Database AI Agent and can only answer questions related to the employees database."

4. Do not give explanations, guesses, or additional information for unrelated questions.
5. Do not attempt to answer using general knowledge.

Examples:

User: What is the weather today?
Assistant: I am an Employee Database AI Agent and can only answer questions related to the employees database.

User: Who are the employees in the sales department?
Assistant: (Generate SQL query and call the run_sql_query tool)

User: What is Python?
Assistant: I am an Employee Database AI Agent and can only answer questions related to the employees database.

Always stay within the employee database domain.
"""
    }
    ]
    st.session_state.show_history = False

def load_chat(chat_id):
    """Load a chat from history"""
    if chat_id in st.session_state.chat_history:
        if st.session_state.current_chat_id:
            user_msgs = [m for m in st.session_state.messages if m.get("role") == "user"]
            title = "New Chat"
            if user_msgs:
                first = user_msgs[0]["content"]
                title = first[:25] + "..." if len(first) > 25 else first
            
            st.session_state.chat_history[st.session_state.current_chat_id] = {
                "title": title,
                "messages": st.session_state.messages.copy(),
                "timestamp": datetime.now().strftime("%H:%M"),
                "date": datetime.now().strftime("%Y-%m-%d")
            }
        
        st.session_state.current_chat_id = chat_id
        st.session_state.messages = st.session_state.chat_history[chat_id]["messages"].copy()
        st.session_state.show_history = False

def clear_current_chat():
    """Clear current chat messages"""
    st.session_state.messages = [
        {
            "role": "system",
            "content": """You are an assistant that answers questions about an employee database.

Table name: employees
Columns: id, name, email, mobile, location, department, salary

If needed, generate SQL queries and call the tool run_sql_query."""
        }
    ]

# Initialize first chat
if not st.session_state.current_chat_id:
    init_new_chat()

# ---------------- CSS ----------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

* { font-family: 'Inter', sans-serif; }

#MainMenu, header, footer {visibility: hidden;}

.stApp {
    background-color: #0b1120;
    color: #e2e8f0;
}

/* Force sidebar visible */
[data-testid="stSidebar"] {
    min-width: 280px !important;
    max-width: 280px !important;
    width: 280px !important;
    transform: none !important;
    transition: none !important;
    background-color: #060a13 !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
    border-right: 1px solid #1a1e2e !important;
    visibility: visible !important;
    display: block !important;
    position: fixed !important;
    left: 0 !important;
    top: 0 !important;
    height: 100vh !important;
    z-index: 100 !important;
}

[data-testid="stSidebar"][aria-expanded="false"] {
    min-width: 280px !important;
    max-width: 280px !important;
    transform: none !important;
}

/* Fix Streamlit sidebar default huge padding */
[data-testid="stSidebarUserContent"], [data-testid="stSidebarContent"] {
    padding-top: 0 !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    padding-bottom: 0 !important;
}

[data-testid="stSidebarHeader"], [data-testid="stSidebarNav"] {
    display: none !important;
    padding: 0 !important;
    min-height: 0 !important;
    height: 0 !important;
}

/* Main content offset for sidebar */
.main .block-container {
    padding-left: 280px !important;
    padding-top: 2rem !important;
    padding-bottom: 1rem !important;
    padding-right: 2rem !important;
    max-width: 100% !important;
}

/* Streamlit layout fixes for sidebar inputs */
div[data-testid="stTextInput"] div[data-baseweb="input"] {
    background-color: #141a29 !important;
    border: 1px solid #1e2536 !important;
    border-radius: 12px !important;
    padding-left: 5px !important;
}

div[data-testid="stTextInput"] input {
    color: #cbd5e1 !important;
    font-size: 13px !important;
    font-family: 'Inter', sans-serif !important;
}

/* Sidebar styles */
.sidebar-content {
    padding: 0 20px;
}

/* Streamlit button overrides */
.stButton > button {
    width: 100% !important;
    border-radius: 12px !important;
    padding: 10px 14px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
    height: auto !important;
    min-height: 40px !important;
    transition: all 0.2s ease !important;
    border: none !important;
    background: transparent !important;
}

/* New Chat - Soft Gradient */
.stButton > button[kind="primary"] {
    background: linear-gradient(90deg, #32255d 0%, #3e306b 100%) !important;
    color: #ffffff !important;
    border: 1px solid #4a3c7a !important;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
    margin-top: 10px;
    margin-bottom: 20px;
}

.stButton > button[kind="primary"]:hover {
    background: linear-gradient(90deg, #4a3c7a 0%, #574691 100%) !important;
}

/* Secondary buttons - Sidebar Items */
.stButton > button[kind="secondary"] {
    background: transparent !important;
    color: #94a3b8 !important;
    border: none !important;
    justify-content: flex-start !important;
    padding-left: 15px !important;
    border-radius: 8px !important;
}

.stButton > button[kind="secondary"]:hover {
    background: #141a29 !important;
    color: #ffffff !important;
}

/* History list */
.history-section {
    flex: 1;
    overflow-y: auto;
    background: transparent;
    padding: 14px;
}

/* Hide scrollbar for history container */
.history-section::-webkit-scrollbar { width: 6px; }
.history-section::-webkit-scrollbar-track { background: transparent; }
.history-section::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.05); border-radius: 4px; }

.history-item {
    width: 100%;
    padding: 14px 20px;
    border: none;
    background: transparent;
    text-align: left;
    cursor: pointer;
    font-size: 13px;
    color: #cbd5e1;
    transition: all 0.2s ease;
    border-radius: 10px;
    margin-bottom: 6px;
    border: 1px solid transparent;
}

.history-item:hover {
    background: rgba(255, 255, 255, 0.03);
    transform: translateX(4px);
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.05);
}

.history-item.active {
    background: linear-gradient(90deg, rgba(99, 102, 241, 0.15) 0%, transparent 100%);
    border-left: 3px solid #8b5cf6;
    color: #ffffff;
}

.empty-history {
    padding: 40px 20px;
    text-align: center;
    color: #64748b;
    font-size: 13px;
}

/* Main content */
.main-content {
    background: transparent;
    max-width: 1000px;
    margin: 0 auto;
    padding: 0 20px;
    display: flex;
    flex-direction: column;
}

.chat-container {
    flex: 1;
    padding: 10px 0 100px 0;
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.welcome {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: #ffffff;
    text-align: center;
    gap: 16px;
    animation: fadeIn 0.8s ease-out;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.welcome h1 {
    font-size: 38px;
    font-weight: 700;
    font-family: 'Consolas', 'Courier New', monospace;
    background: linear-gradient(90deg, #00f2fe 0%, #4facfe 50%, #00f2fe 100%);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    letter-spacing: 1px;
    animation: flowGradient 3s linear infinite;
    text-shadow: 0 0 20px rgba(0, 242, 254, 0.2);
}

@keyframes flowGradient {
    to { background-position: 200% center; }
}

.welcome p {
    color: #00f2fe;
    margin: 0;
    font-size: 15px;
    font-family: 'Consolas', 'Courier New', monospace;
    opacity: 0.8;
    letter-spacing: 2px;
    text-transform: uppercase;
}

/* Messages */
.message-user {
    align-self: flex-end;
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
    color: #ffffff;
    padding: 14px 20px;
    border-radius: 12px 12px 0px 12px;
    font-size: 14px;
    display: inline-block;
}

.message-assistant {
    align-self: flex-start;
    background: #141B2D;
    color: #e2e8f0;
    padding: 20px 24px;
    border-radius: 16px;
    width: 100%;
    max-width: 85%;
    font-size: 14px;
    line-height: 1.6;
    border: 1px solid #1e263d;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
}

.assistant-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
}

.assistant-header .name {
    font-size: 12px;
    font-weight: 600;
    color: #94a3b8;
}

.assistant-header .badge {
    background: rgba(59, 130, 246, 0.1);
    color: #3b82f6;
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 10px;
    font-weight: bold;
}

@keyframes slideInRight {
    from { opacity: 0; transform: translateX(20px); }
    to { opacity: 1; transform: translateX(0); }
}

@keyframes slideInLeft {
    from { opacity: 0; transform: translateX(-20px); }
    to { opacity: 1; transform: translateX(0); }
}

/* Input area wrapper */
.input-area {
    padding: 0 0 20px 0;
    border-top: none;
    position: relative;
    z-index: 10;
}

/* Streamlit Input Container Override for beautiful styling */
.stChatInput {
    max-width: 1000px !important;
}

.stChatInput > div {
    background: transparent !important;
    backdrop-filter: none !important;
    -webkit-backdrop-filter: none !important;
    border: 1px solid #232b45 !important;
    border-radius: 20px !important;
    box-shadow: 0 0 20px rgba(59, 130, 246, 0.1), inset 0 0 10px rgba(59, 130, 246, 0.05) !important;
    transition: all 0.3s ease !important;
}

.stChatInput > div:focus-within {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 25px rgba(59, 130, 246, 0.2) !important;
}

.stChatInput input {
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
    padding: 16px 20px !important;
}

.stChatInput input::placeholder {
    color: #475569 !important;
}

/* Hide streamlit input area default borders if any */
div[data-testid="stChatInput"] {
    background: transparent !important;
    padding-bottom: 10px !important;
}

/* Top bar for mobile/small screens */
.top-bar {
    display: none;
    background: rgba(15, 23, 42, 0.9);
    backdrop-filter: blur(12px);
    padding: 12px 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 99;
}

@media (max-width: 768px) {
    [data-testid="stSidebar"] {
        display: none !important;
    }
    .main .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-top: 70px !important;
    }
    .top-bar {
        display: flex;
        gap: 12px;
    }
}
</style>
""", unsafe_allow_html=True)

# ---------------- LOGIN SCREEN GATE ----------------
if not st.session_state.authenticated:
    st.markdown("""<style>
    [data-testid="stSidebar"] { display: none !important; }
    .main .block-container { 
        padding-left: 20px !important; 
        max-width: 500px !important;
        margin: 0 auto;
        padding-top: 5vh !important;
        background: #141a29;
        margin-top: 10vh;
        border-radius: 20px;
        border: 1px solid #1e2536;
        box-shadow: 0 0 30px rgba(59, 130, 246, 0.15);
        padding: 40px !important;
    }
    
    /* Reset background for streamlit elements inside the block to transparent */
    div[data-testid="stAppViewBlockContainer"] {
        background: transparent !important;
    }
    </style>""", unsafe_allow_html=True)
    
    st.markdown("""
        <div style="text-align: center;">
            <div style="background: #e2e8f0; width: 60px; height: 60px; border-radius: 12px; margin: 0 auto 20px auto; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 20px rgba(255,255,255,0.1);">
                <span style="font-size: 32px;">🤖</span>
            </div>
            <h1 style="background: linear-gradient(90deg, #4da4fc, #b763fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 5px; font-size: 28px; font-weight: bold;">Employee AI Agent</h1>
            <p style="color: #64748b; font-size: 14px; margin-bottom: 30px;">Secure Access Portal</p>
        </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.auth_step == "email":
        tab1, tab2 = st.tabs(["Log In", "Sign Up"])
        with tab1:
            login_email = st.text_input("Email", placeholder="", key="li_email")
            if st.button("Log In", type="primary", use_container_width=True):
                user = user_db.get_user(login_email)
                if not user:
                    st.error("No account found! Please sign up first.")
                elif login_email:
                    st.session_state.auth_email = login_email
                    st.session_state.authenticated = True
                    st.session_state.current_user_name = user[1]
                    st.session_state.chat_history = user_db.get_user_chats(login_email)
                    if not st.session_state.chat_history:
                        init_new_chat()
                    else:
                        latest_chat_id = list(st.session_state.chat_history.keys())[0]
                        st.session_state.current_chat_id = latest_chat_id
                        st.session_state.messages = st.session_state.chat_history[latest_chat_id]["messages"]
                    st.success("Successfully Logged In!")
                    st.rerun()
        with tab2:
            st.markdown('<div style="margin-top: -10px;"></div>', unsafe_allow_html=True)
            signup_name = st.text_input("Full Name", placeholder="", key="su_name")
            signup_email = st.text_input("Email", placeholder="", key="su_email")
            if st.button("Send Signup OTP", type="primary", use_container_width=True):
                user = user_db.get_user(signup_email)
                if user:
                    st.error("Account already exists! Please log in.")
                elif signup_email and signup_name:
                    otp = str(random.randint(100000, 999999))
                    st.session_state.sent_otp = otp
                    st.session_state.auth_email = signup_email
                    st.session_state.signup_name = signup_name
                    if send_otp_email(signup_email, otp):
                        st.session_state.auth_step = "otp"
                        st.success("OTP sent to your email!")
                        st.rerun()
                else:
                    st.error("Please fill in all fields.")
                
    elif st.session_state.auth_step == "otp":
        st.markdown(f"<p style='color: #cbd5e1; font-size: 14px;' >Verification code sent to <b>{st.session_state.auth_email}</b></p>", unsafe_allow_html=True)
        otp_inp = st.text_input("Enter 6-digit OTP", type="password", placeholder="••••••")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Verify & Sign Up", type="primary", use_container_width=True):
                if otp_inp == st.session_state.sent_otp:
                    user_db.create_user(st.session_state.auth_email, st.session_state.signup_name)
                    st.session_state.auth_step = "email"
                    st.success("Account successfully created! Please log in to continue.")
                    st.rerun()
                else:
                    st.error("Invalid OTP. Try again.")
        with col2:
            if st.button("Cancel", type="secondary", use_container_width=True):
                st.session_state.auth_step = "email"
                st.rerun()
    st.stop()


# ---------------- SIDEBAR (Force it open) ----------------
with st.sidebar:
    st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 20px 15px 20px; margin-top: -10px;">
        <h2 style="color: #4da4fc; font-size: 16px; margin: 0; display: flex; align-items: center;"><span style="font-size: 18px; margin-right: 8px;">💬</span> Conversations</h2>
        <span style="color: #64748b; font-size: 20px; font-weight: bold; cursor: pointer;">≡</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="sidebar-top">', unsafe_allow_html=True)
    search_query = st.text_input("Search chats...", placeholder="🔍 Search chats...", label_visibility="collapsed")
    
    if st.button("➕ New Chat", type="primary", use_container_width=True):
        init_new_chat()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Render Real Chat History within a scrollable container
    st.markdown('<div class="scrollable-chat-list">', unsafe_allow_html=True)
    if not st.session_state.chat_history:
        st.markdown('<div style="color: #64748b; font-size: 13px; text-align: center; margin-top: 30px;">No chat history yet.<br>Start a conversation!</div>', unsafe_allow_html=True)
    else:
        sorted_chats = sorted(
            st.session_state.chat_history.items(),
            key=lambda x: x[1].get("timestamp", ""),
            reverse=True
        )
        
        for chat_id, chat_data in sorted_chats:
            is_active = chat_id == st.session_state.current_chat_id
            title = chat_data['title']
            
            # Rename Mode Check
            if st.session_state.get('rename_chat_id') == chat_id:
                new_title = st.text_input("New title", value=title, key=f"ren_val_{chat_id}", label_visibility="collapsed")
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    if st.button("✅", key=f"save_ren_{chat_id}", use_container_width=True):
                        st.session_state.chat_history[chat_id]['title'] = new_title
                        user_db.save_chat(st.session_state.auth_email, chat_id, new_title, chat_data['messages'], chat_data.get('timestamp',''), chat_data.get('date',''))
                        st.session_state.rename_chat_id = None
                        st.rerun()
                with col_r2:
                    if st.button("❌", key=f"cancel_ren_{chat_id}", use_container_width=True):
                        st.session_state.rename_chat_id = None
                        st.rerun()
                continue

            c1, c2, c3 = st.columns([0.7, 0.15, 0.15])
            with c1:
                if is_active:
                    st.markdown(f"""
                    <div style="background: #141a29; border-radius: 8px; padding: 10px 14px; margin-bottom: 5px; color: #ffffff; font-size: 13px; font-weight: 500; display: flex; align-items: center; border: 1px solid #1e2536;">
                        <span style="margin-right: 10px;">💬</span> {title}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    if st.button(f"💬 {title}", key=f"load_{chat_id}", type="secondary", use_container_width=True):
                        st.session_state.current_chat_id = chat_id
                        st.session_state.messages = chat_data["messages"]
                        st.rerun()
            with c2:
                if st.button("✏️", key=f"ren_{chat_id}", help="Rename Chat", use_container_width=True):
                    st.session_state.rename_chat_id = chat_id
                    st.rerun()
            with c3:
                if st.button("🗙", key=f"del_{chat_id}", help="Delete Chat", use_container_width=True):
                    user_db.delete_chat(st.session_state.auth_email, chat_id)
                    if chat_id in st.session_state.chat_history:
                        del st.session_state.chat_history[chat_id]
                    if is_active:
                        init_new_chat()
                    st.rerun()
                    
    st.markdown('</div>', unsafe_allow_html=True) # End scrollable-chat-list
    
    # Bottom Section - Always Visible
    st.markdown('<div class="sidebar-footer">', unsafe_allow_html=True)
    
    if st.session_state.get('show_pdf_export', False):
        st.markdown("""
            <div style="border-left: 4px solid #3b82f6; background: #1e2536; padding: 12px; border-radius: 4px; margin-bottom: 10px;">
                <p style='margin:0; font-size:12px; font-weight: bold; color:#fff;'>Export this chat to PDF?</p>
            </div>
        """, unsafe_allow_html=True)
        ex_1, ex_2 = st.columns(2)
        with ex_1:
            try:
                pdf_bytes = generate_chat_pdf()
                st.download_button("👍 Yes", data=pdf_bytes, file_name=f"chat_{st.session_state.current_chat_id[:8]}.pdf", mime="application/pdf", use_container_width=True, key="confirm_pdf_yes")
                if st.session_state.get("confirm_pdf_yes"):
                    st.session_state.show_pdf_export = False
            except Exception as e:
                st.error("Error generating PDF.")
        with ex_2:
            if st.button("❌ No", use_container_width=True):
                st.session_state.show_pdf_export = False
                st.rerun()
        
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("📥 Export", type="secondary", use_container_width=True):
            st.session_state.show_pdf_export = True
            st.rerun()
    with c_btn2:
        if st.button("🚪 Logout", type="secondary", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.current_user_name = None
            st.session_state.auth_email = None
            st.rerun()
            
    st.markdown('</div>', unsafe_allow_html=True) # End sidebar-footer
    
    st.markdown("""
    <style>
    .scrollable-chat-list {
        max-height: calc(100vh - 350px);
        overflow-y: auto;
        padding-right: 10px;
        margin-bottom: 20px;
    }
    .scrollable-chat-list::-webkit-scrollbar {
        width: 4px;
    }
    .scrollable-chat-list::-webkit-scrollbar-thumb {
        background: #1e2536;
        border-radius: 10px;
    }
    .sidebar-footer {
        border-top: 1px solid #1e2536;
        padding-top: 20px;
    }
    
    /* Aggressive Ghost button override for sidebar icons */
    section[data-testid="stSidebar"] button {
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        border-color: transparent !important;
        box-shadow: none !important;
        outline: none !important;
        color: #94a3b8 !important;
        background-image: none !important;
    }
    
    section[data-testid="stSidebar"] button:hover {
        background-color: rgba(255, 255, 255, 0.05) !important;
        color: #fff !important;
    }
    
    section[data-testid="stSidebar"] button[key*="del_"]:hover {
        background-color: rgba(239, 68, 68, 0.2) !important;
        color: #ef4444 !important;
    }
    
    section[data-testid="stSidebar"] button[key*="ren_"]:hover {
        background-color: rgba(59, 130, 246, 0.2) !important;
        color: #3b82f6 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------- MAIN CONTENT ----------------
st.markdown('<div class="main-content">', unsafe_allow_html=True)

st.markdown('<div class="chat-container">', unsafe_allow_html=True)

has_messages = len([m for m in st.session_state.messages if m.get("role") in ["user", "assistant"]]) > 0

if not has_messages:
    # Match the image exactly
    st.markdown(f"""
    <div style="text-align: center; margin-top: 2rem; margin-bottom: 3rem;">
        <div style="background: #e2e8f0; width: 60px; height: 60px; border-radius: 12px; margin: 0 auto 15px auto; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 20px rgba(255,255,255,0.1);">
            <span style="font-size: 32px;">🤖</span>
        </div>
        <h1 style="background: linear-gradient(90deg, #4da4fc, #b763fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 5px; font-size: 32px; font-weight: bold;">Hello {st.session_state.get('current_user_name', 'User')}, welcome to employee chat agent.</h1>
        <p style="color: #64748b; font-size: 14px;">Ask questions about employee database</p>
    </div>
    """, unsafe_allow_html=True)

if has_messages:
    msgs = st.session_state.messages
    i = 0
    while i < len(msgs):
        msg = msgs[i]
        role = msg.get("role")
        content = msg.get("content", "")
        
        if role == "system" or role == "tool":
            i += 1
            continue
            
        if role == "user":
            st.markdown(f'<div style="display: flex; gap: 15px; justify-content: flex-end; margin-bottom: 20px; align-items: flex-start;"><div class="message-user">{content}</div><div style="font-size: 32px;">🧑</div></div>', unsafe_allow_html=True)
            i += 1
        elif role == "assistant":
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                # Look ahead for the answering assistant message
                final_answer = ""
                j = i + 1
                while j < len(msgs):
                    next_msg = msgs[j]
                    if next_msg.get("role") == "user":
                        break
                    if next_msg.get("role") == "assistant" and not next_msg.get("tool_calls"):
                        final_answer = next_msg.get("content", "")
                        break
                    j += 1
                
                query_blocks = []
                for tc in tool_calls:
                    func = tc.get("function", {})
                    args_data = func.get("arguments", "{}")
                    try:
                        args_dict = json.loads(args_data) if isinstance(args_data, str) else args_data
                        query_str = args_dict.get("query", str(args_dict))
                        query_blocks.append(f'<div style="background: #0b1120; border: 1px solid #1e2536; border-radius: 6px; padding: 12px; margin-top: 8px; margin-bottom: 12px; font-family: monospace; font-size: 13px; color: #4da4fc; overflow-x: auto;">{query_str}</div>')
                    except Exception:
                        query_blocks.append(f'<div style="background: #0b1120; border: 1px solid #1e2536; border-radius: 6px; padding: 12px; margin-top: 8px; margin-bottom: 12px; font-family: monospace; font-size: 13px; color: #4da4fc; overflow-x: auto;">{args_data}</div>')
                        
                formatted_queries = "<div style='color: #94a3b8; font-size: 13px; font-weight: 500;'>Executing Action:</div>" + "".join(query_blocks)
                
                # Compress query block and final text logic natively into identical box
                if final_answer:
                    formatted_content = formatted_queries + f"<div style='margin-top: 10px; border-top: 1px solid #1e2536; padding-top: 14px;'>{final_answer}</div>"
                    i = j + 1
                else:
                    formatted_content = formatted_queries
                    i += 1
                
                st.markdown(f"""
                <div style="display: flex; gap: 15px; margin-bottom: 20px; align-items: flex-start;">
                    <div style="font-size: 32px;">🤖</div>
                    <div class="message-assistant">
                        <div class="assistant-header">
                            <span class="name">Employee AI Agent</span>
                            <span class="badge">AI</span>
                        </div>
                        {formatted_content}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="display: flex; gap: 15px; margin-bottom: 20px; align-items: flex-start;">
                    <div style="font-size: 32px;">🤖</div>
                    <div class="message-assistant">
                        <div class="assistant-header">
                            <span class="name">Employee AI Agent</span>
                            <span class="badge">AI</span>
                        </div>
                        {content}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                i += 1

spinner_placeholder = st.container()
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="input-area">', unsafe_allow_html=True)
user_input = st.chat_input("Type your message...")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ---------------- PROCESSING ----------------
if user_input:
    add_question(user_input)
    
    if "first question" in user_input.lower():
        answer = get_first_question()
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()
        
    elif "last questions" in user_input.lower():
        answer = str(get_last_questions())
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()
        
    else:
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        with spinner_placeholder:
            st.markdown(f'<div style="display: flex; gap: 15px; justify-content: flex-end; margin-bottom: 20px; align-items: flex-start;"><div class="message-user">{user_input}</div><div style="font-size: 32px;">🧑</div></div>', unsafe_allow_html=True)
            with st.spinner("🤖 Agent is working on it..."):
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=st.session_state.messages,
                    tools=tools,
                    tool_choice="auto"
                )
        
        message = response.choices[0].message
        
        if message.tool_calls:
            st.session_state.messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in message.tool_calls
                ]
            })
            
            for tool_call in message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                result = run_sql_query(**args)
                
                st.session_state.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": str(result)
                })
            
            with spinner_placeholder:
                st.markdown(f'<div style="display: flex; gap: 15px; justify-content: flex-end; margin-bottom: 20px; align-items: flex-start;"><div class="message-user">{user_input}</div><div style="font-size: 32px;">🧑</div></div>', unsafe_allow_html=True)
                with st.spinner("🤖 Extracting SQL records and formulating answer..."):
                    second_response = client.chat.completions.create(
                        model=MODEL,
                        messages=st.session_state.messages
                    )
            
            final_answer = second_response.choices[0].message.content
            st.session_state.messages.append({
                "role": "assistant",
                "content": final_answer
            })
        else:
            st.session_state.messages.append({
                "role": "assistant",
                "content": message.content
            })
            
        # Guarantee dynamic autosave into User DB on every response block
        if getattr(st.session_state, 'authenticated', False) and st.session_state.current_chat_id:
            user_msgs = [m for m in st.session_state.messages if m.get("role") == "user"]
            title = "New Chat"
            if user_msgs:
                first = user_msgs[0]["content"]
                title = first[:25] + "..." if len(first) > 25 else first
            
            timestamp = datetime.now().strftime("%H:%M")
            date_str = datetime.now().strftime("%Y-%m-%d")
            
            st.session_state.chat_history[st.session_state.current_chat_id] = {
                "title": title,
                "messages": st.session_state.messages.copy(),
                "timestamp": timestamp,
                "date": date_str
            }
            user_db.save_chat(st.session_state.auth_email, st.session_state.current_chat_id, title, st.session_state.messages, timestamp, date_str)
        
        st.rerun()