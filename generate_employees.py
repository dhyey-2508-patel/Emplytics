from faker import Faker
import pandas as pd
import random

fake = Faker()

departments = ["HR","IT","Finance","Sales","Marketing"]
locations = ["Mumbai","Delhi","Ahmedabad","Bangalore","Pune"]

data = []

for i in range(1000):
    data.append({
        "id": i+1,
        "name": fake.name(),
        "email": fake.email(),
        "mobile": fake.phone_number(),
        "location": random.choice(locations),
        "department": random.choice(departments),
        "salary": random.randint(30000,150000)
    })

df = pd.DataFrame(data)
df.to_csv("employees.csv", index=False)

print("Employee dataset created")