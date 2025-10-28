# Главный файл приложения
from fastapi import FastAPI
from routers import tasks 


app = FastAPI(
    title="ToDo лист API",
    description="API для управления задачами с использованием матрицы Эйзенхауэра",
    version="1.0.0",
    contact={
        "name": "Ваше Имя",
    }
)

app.include_router(tasks.router) # подключение роутера к приложению

@app.get("/")
async def welcome() -> dict:
    return { "message": "Привет, студент!",
            "api_title": app.title,
            "api_description": app.description,
            "api_version": app.version,
            "api_author": app.contact["name"]}