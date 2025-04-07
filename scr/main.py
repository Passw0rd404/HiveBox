from endpoints import version
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"Hello": "World"}

@app.get("/version")
async def get_version():
    return {"version": version.get_version()}

@app.get("/temperature")
async def get_temprature():
    return {"Hello": "World"}