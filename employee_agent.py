import json
import os
from openai import OpenAI
from dotenv import load_dotenv
from tools import run_sql_query
from memory import add_question, get_first_question, get_last_questions

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

MODEL = os.getenv("MODEL_NAME")

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
                        "description": "SQL query to execute"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

messages = [
    {
        "role": "system",
        "content": """
You are an assistant that answers questions about an employee database.

Table name: employees

Columns:
id
name
email
mobile
location
department
salary

When needed, generate SQL queries and call the tool run_sql_query.
"""
    }
]

while True:

    user_input = input("\nAsk question: ")

    if user_input == "exit":
        break

    # -------- STORE QUESTION IN MEMORY --------
    add_question(user_input)

    # -------- MEMORY QUESTIONS --------
    if "first question" in user_input.lower():
        print("\nAnswer:", get_first_question())
        continue

    if "last questions" in user_input.lower():
        print("\nAnswer:", get_last_questions())
        continue

    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )

    message = response.choices[0].message

    if message.tool_calls:

        for tool_call in message.tool_calls:

            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            result = run_sql_query(**arguments)

            messages.append(message)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })

        second_response = client.chat.completions.create(
            model=MODEL,
            messages=messages
        )

        final_answer = second_response.choices[0].message.content
        print("\nAnswer:", final_answer)

        messages.append({"role": "assistant", "content": final_answer})

    else:

        print("\nAnswer:", message.content)
        messages.append({"role": "assistant", "content": message.content})