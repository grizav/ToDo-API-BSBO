# Главный файл приложения
from fastapi import FastAPI, HTTPException, Query
from typing import List, Dict, Any
from datetime import datetime

app = FastAPI(
    title="ToDo лист API",
    description="API для управления задачами с использованием матрицы Эйзенхауэра",
    version="1.0.0",
    contact={
        "name": "Ваше Имя",
    }
)

# Временное хранилище (позже будет заменено на PostgreSQL)
tasks_db: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "Сдать проект по FastAPI",
        "description": "Завершить разработку API и написать документацию",
        "is_important": True,
        "is_urgent": True,
        "quadrant": "Q1",
        "completed": False,
        "created_at": datetime.now()
    },
    {
        "id": 2,
        "title": "Изучить SQLAlchemy",
        "description": "Прочитать документацию и попробовать примеры",
        "is_important": True,
        "is_urgent": False,
        "quadrant": "Q2",
        "completed": False,
        "created_at": datetime.now()
    },
    {
        "id": 3,
        "title": "Сходить на лекцию",
        "description": None,
        "is_important": False,
        "is_urgent": True,
        "quadrant": "Q3",
        "completed": False,
        "created_at": datetime.now()
    },
    {
        "id": 4,
        "title": "Посмотреть сериал",
        "description": "Новый сезон любимого сериала",
        "is_important": False,
        "is_urgent": False,
        "quadrant": "Q4",
        "completed": True,
        "created_at": datetime.now()
    },
]

@app.get("/")
async def welcome() -> dict:
    return { "message": "Привет, студент!",
            "api_title": app.title,
            "api_description": app.description,
            "api_version": app.version,
            "api_author": app.contact["name"]}

@app.get("/tasks")
async def get_all_tasks() -> dict:
    return {
        "count": len(tasks_db),  # считает количество записей в хранилище
        "tasks": tasks_db # выводит всё, чта есть в хранилище
    }

@app.get("/tasks/quadrant/{quadrant}")
async def get_tasks_by_quadrant(quadrant: str) -> dict:
    if quadrant not in ["Q1", "Q2", "Q3", "Q4"]:
        raise HTTPException(    # специальный класс в FastAPI для возврата HTTP ошибок. Не забудьте добавть его импорт в 1 строке
            status_code=400, 
            detail="Неверный квадрант. Используйте: Q1, Q2, Q3, Q4"  # текст, который будет выведен пользователю 
        )
    
    filtered_tasks = [
        task                          # ЧТО добавляем в список
        for task in tasks_db          # ОТКУДА берем элементы
        if task["quadrant"] == quadrant  # УСЛОВИЕ фильтрации
    ]
    
    return {
        "quadrant": quadrant,
        "count": len(filtered_tasks),
        "tasks": filtered_tasks
    }

@app.get("/tasks/stats")
async def get_tasks_stats() -> dict:
    total_tasks = len(tasks_db)
    by_quadrant = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    by_status = {"completed": 0, "pending": 0}

    for task in tasks_db:
        if task["quadrant"] in by_quadrant:
            by_quadrant[task["quadrant"]] += 1
        if task["completed"]:
            by_status["completed"] += 1
        else:
            by_status["pending"] += 1

    return {
        "total_tasks": total_tasks,
        "by_quadrant": by_quadrant,
        "by_status": by_status
    }

@app.get("/tasks/search")
async def search_tasks(q: str = Query(..., min_length=2)) -> dict:
    keyword = q.lower()
    filtered_tasks = [
        task for task in tasks_db
        if keyword in task["title"].lower() or
            (task["description"] and keyword in task["description"].lower())
    ]

    if not filtered_tasks:
        raise HTTPException(status_code=404, detail="По данному запросу ничего не найдено")

    return {
        "query": q,
        "count": len(filtered_tasks),
        "tasks": filtered_tasks
    }

@app.get("/tasks/status/{status}")
async def get_tasks_by_status(status: str) -> dict:
    if status not in ["completed", "pending"]:
        raise HTTPException(status_code=404, detail="Недопустимый статус. Используйте: completed или pending")

    is_completed = status == "completed"
    filtered_tasks = [task for task in tasks_db if task["completed"] == is_completed]

    return {
        "status": status,
        "count": len(filtered_tasks),
        "tasks": filtered_tasks
    }

@app.get("/tasks/{task_id}")
async def get_task_by_id(task_id: int) -> dict:
    task = next((
        task for task in tasks_db 
        if task["id"] == task_id), 
        None
    )
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task