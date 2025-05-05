from fastapi import FastAPI
from typing import Union


app = FastAPI(title="Kira", version="0.0.1") 
# start the FastAPI application with 
# fastapi dev main.py


#####################
### test endpoint ###
#####################
@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/items/{item_id}/{q}")
def read_item(item_id: int, q: int = None):
    return {"item_id": item_id, "q": q}