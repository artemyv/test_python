import json
import os
import tkinter as tk
from tkinter import simpledialog

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

def open_second_form():
    second_form = tk.Toplevel(root)
    second_form.title("Second Form")
    second_form.geometry("300x100")

    tk.Label(second_form, text="Enter some text:").pack(pady=10)
    entry = tk.Entry(second_form)
    entry.pack(pady=5)

    def on_close():
        entered_text.set(entry.get())
        second_form.destroy()

    tk.Button(second_form, text="Submit", command=on_close).pack(pady=10)

root = tk.Tk()
root.title("First Form")
root.geometry("300x100")

entered_text = tk.StringVar()

tk.Button(root, text="Open Second Form", command=open_second_form).pack(pady=20)
tk.Label(root, textvariable=entered_text).pack(pady=10)

root.mainloop()