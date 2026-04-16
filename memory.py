from collections import deque

question_memory = deque(maxlen=10)

def add_question(question):
    question_memory.append(question)

def get_first_question():
    if len(question_memory) == 0:
        return "No questions asked yet."
    return question_memory[0]

def get_last_questions():
    return list(question_memory)