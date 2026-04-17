from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import uuid
import smtplib
from email.mime.text import MIMEText
import random
from openai import AsyncOpenAI
import json
import asyncio
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import db
import json

load_dotenv()

app = FastAPI()

# Mount frontend as static files
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/static/signup.html")

# Enable CORS for local HTML file development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)
MODEL = os.getenv("MODEL_NAME") if os.getenv("MODEL_NAME") else "glm-4.7-flash"

# Temporary OTP store
otp_store = {}

class UserSignup(BaseModel):
    email: str
    password: str
    name: str

class UserLogin(BaseModel):
    email: str
    password: str

class ChatUpdate(BaseModel):
    chat_id: str
    title: str

class ChatMessage(BaseModel):
    role: str
    content: str
    tool_calls: Optional[List] = None

class ChatHistory(BaseModel):
    chat_id: str
    messages: List[ChatMessage]

class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None

@app.post("/signup/send-otp")
async def send_otp(email: str = Body(..., embed=True)):
    # Check if user already exists
    if db.validate_login(email, "") is not None or db.register_user(email, "", "") == False:
        # Note: register_user with empty password/name is just a check here, 
        # but let's use a cleaner check.
        pass
    
    # Better: let's add a specific check function or use existing ones
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE email = %s", (email,))
    exists = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if exists:
        raise HTTPException(status_code=400, detail="User already exists")

    otp = str(random.randint(100000, 999999))

    otp_store[email] = otp
    
    # SMTP Logic
    try:
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASS")
        if not smtp_user or not smtp_pass:
            print(f"DEBUG: OTP for {email} is {otp}")
            return {"status": "success", "message": "OTP printed to console (Mock mode)"}
            
        msg = MIMEText(f"Your OTP is: {otp}")
        msg['Subject'] = 'Login OTP'
        msg['From'] = smtp_user
        msg['To'] = email
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/signup/verify")
async def verify_signup(data: UserSignup = Body(...), otp: str = Body(..., embed=True)):
    stored_otp = otp_store.get(data.email)
    print(f"DEBUG: Verifying for {data.email}. Stored: {stored_otp}, Received: {otp}")
    if stored_otp == otp:
        success = db.register_user(data.email, data.password, data.name)
        if success:
            # Clear OTP after successful verification
            otp_store.pop(data.email, None)
            return {"status": "success"}
        raise HTTPException(status_code=400, detail="User already exists")
    raise HTTPException(status_code=400, detail="Invalid OTP")


@app.post("/login")
async def login(data: UserLogin):
    name = db.validate_login(data.email, data.password)
    if name:
        return {"status": "success", "name": name, "email": data.email}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/chats/{email}")
async def get_chats(email: str):
    return db.get_user_chats(email)

@app.post("/chats/save/{email}")
async def save_chat(email: str, chat: ChatHistory):
    # Retrieve current messages to get the first one for title
    existing_chats = db.get_user_chats(email)
    title = "New Chat"
    if chat.chat_id in existing_chats:
        title = existing_chats[chat.chat_id]["title"]
    else:
        user_msgs = [m for m in chat.messages if m.role == "user"]
        if user_msgs:
            first = user_msgs[0].content
            title = first[:25] + "..." if len(first) > 25 else first

    db.save_chat(email, chat.chat_id, title, [m.dict() for m in chat.messages])
    return {"status": "success"}

@app.delete("/chats/{email}/{chat_id}")
async def delete_chat(email: str, chat_id: str):
    db.delete_chat(email, chat_id)
    return {"status": "success"}

@app.put("/chats/rename/{email}")
async def rename_chat(email: str, data: ChatUpdate):
    db.rename_chat(email, data.chat_id, data.title)
    return {"status": "success"}

from tools import run_sql_query, check_data_quality

@app.post("/chat/completions")
async def chat_completion(request: ChatCompletionRequest):
    messages = request.messages
    active_model = request.model or MODEL
    print(f"DEBUG: Using model: {active_model}")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "run_sql_query",
                "description": "Run a SQL query against the employee database.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The SQL query to run."}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_data_quality",
                "description": "Run an audit for data quality issues like invalid emails, missing fields, or salary outliers.",
                "parameters": {"type": "object", "properties": {}}
            }
        }
    ]

    sys_msg = {
        "role": "system", 
        "content": "You are Emplytics, a professional employee database agent. "
                   "Database Context: Table name is 'employees'. Columns are id, name, email, mobile, location, department, salary. "
                   "STRICT OPERATING RULES: "
                   "1. ONLY answer questions related to the employee database or company personnel. "
                   "2. IF a user asks about general knowledge, current events, politics, or anything unrelated to employees (e.g., 'Who is the PM?'), politely decline and state that you are specialized in employee records only. "
                   "3. For simple database questions (e.g., counts, facts), answer in concise natural language. "
                   "4. ONLY use Markdown tables when specifically asked to 'list', 'show details', or 'provide a report' of employees (capped at 15 records). "
                   "5. NEVER show internal steps or SQL code in the final answer."
    }

    
    # FAST PATH Optimization: Check for simple greetings to skip tool overhead
    import re
    clean_msg = re.sub(r'[^\w\s]', '', messages[-1].content.lower().strip())
    greetings = {"hi", "hello", "hey", "hola", "bye", "goodbye", "thanks", "thank you", "kya", "nihao"}
    
    # HARD BYPASS: For absolute fastest response to dead-simple greetings
    if clean_msg in {"hi", "hello", "hey"}:
        async def fast_response():
            yield "Hello! How can I help you with the employee data today?"
        return StreamingResponse(fast_response(), media_type="text/plain")

    if any(q in clean_msg for q in ["who are you", "your name", "what are you"]):
        async def identity_response():
            yield "I am Emplytics who can answer anything about the employees data."
        return StreamingResponse(identity_response(), media_type="text/plain")

    skip_tools = clean_msg in greetings or len(clean_msg) < 3

    # Context reduction: Only take last 10 messages to keep latency low
    history = messages[-10:] if len(messages) > 10 else messages
    req_messages = [sys_msg] + [m.dict() for m in history]

    async def stream_generator():
        try:
            # First pass
            response = await client.chat.completions.create(
                model=active_model,
                messages=req_messages,
                tools=None if skip_tools else tools,
                tool_choice="none" if skip_tools else "auto",
                stream=True
            )
            
            tool_calls_chunks = {}
            content_yielded = False
            
            async for chunk in response:
                if not chunk.choices:
                    continue
                    
                delta = chunk.choices[0].delta
                
                # Handle tool calls in stream
                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_chunks:
                            tool_calls_chunks[idx] = {"id": "", "name": "", "arguments": ""}
                            
                        if tc.id: tool_calls_chunks[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name: tool_calls_chunks[idx]["name"] = tc.function.name
                            if tc.function.arguments: tool_calls_chunks[idx]["arguments"] += tc.function.arguments
                
                # Handle direct content in stream
                if hasattr(delta, "content") and delta.content:
                    content_yielded = True
                    yield delta.content
            
            # If we had tool calls, execute them and start second pass
            if tool_calls_chunks:
                tool_calls = []
                for idx in sorted(tool_calls_chunks.keys()):
                    tc = tool_calls_chunks[idx]
                    tool_calls.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]}
                    })
                
                assistant_msg_obj = {
                    "role": "assistant",
                    "tool_calls": tool_calls
                }
                
                tool_results = []
                for tc in tool_calls:
                    try:
                        args = json.loads(tc["function"]["arguments"] or "{}")
                        if tc["function"]["name"] == "check_data_quality":
                            result = check_data_quality()
                        else:
                            query = args.get("query", "")
                            result = run_sql_query(query)
                        
                        # SPEED BYPASS: If result is a single value (e.g. COUNT) or very small list
                        if isinstance(result, list) and len(result) > 0:
                            # Handling single value counts
                            if len(result) == 1 and len(result[0]) == 1:
                                key = list(result[0].keys())[0]
                                val = result[0][key]
                                yield f"\n\nThe total is **{val}**."
                                return
                            
                            # Handling small simple lists (e.g. finding a specific name)
                            if len(result) <= 2:
                                header = "| " + " | ".join(result[0].keys()) + " |\n"
                                separator = "| " + " | ".join(["---"] * len(result[0])) + " |\n"
                                rows = ""
                                for r in result:
                                    rows += "| " + " | ".join(str(v) for v in r.values()) + " |\n"
                                yield f"\n\nHere are the details:\n\n{header}{separator}{rows}"
                                return

                    except Exception as te:
                        result = [{"error": str(te)}]
                        
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tc["function"]["name"],
                        "content": json.dumps(result)
                    })
                
                req_messages.append(assistant_msg_obj)
                req_messages.extend(tool_results)
                
                second_response = await client.chat.completions.create(
                    model=active_model,
                    messages=req_messages,
                    stream=True
                )
                
                async for chunk in second_response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content_yielded = True
                        yield chunk.choices[0].delta.content
            
            if not content_yielded:
                yield "I processed your request but have no further information to display."
                        
        except Exception as e:
            print(f"DEBUG Error in stream: {str(e)}")
            yield f"\n[System Error: {str(e)}]"

    return StreamingResponse(stream_generator(), media_type="text/plain")
