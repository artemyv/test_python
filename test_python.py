import json
import os

class SimpleObject:
    def __init__(self, json_str):
        data = json.loads(json_str)
        self.__dict__.update(data)


# Read json_str from file
print("Current working directory:", os.getcwd())
with open('data.json', 'r') as file:
    json_str = file.read()
    #json_str = '{"name": "John", "age": 30}'


obj = SimpleObject(json_str)
print(obj.name)  # Output: John
print(obj.age)   # Output: 30