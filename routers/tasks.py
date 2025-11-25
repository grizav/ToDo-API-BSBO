from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime
from schemas import TaskCreate, TaskUpdate, TaskResponse
from models import Task
from database import get_async_session
from utils import calculate_urgency, determine_quadrant, calculate_days_until_deadline


router = APIRouter(
    prefix="/tasks", # все endpoints роутера будут начинаться с /tasks
    tags=["tasks"], # группировка в Swagger UI
    responses={404: {"description": "Task not found"}},
)

@router.get("", response_model=List[TaskResponse])
async def get_all_tasks(
    db: AsyncSession = Depends(get_async_session)) -> List[TaskResponse]:
    result = await db.execute(select(Task))
    tasks = result.scalars().all()
    return tasks

@router.get("/quadrant/{quadrant}", 
            response_model=List[TaskResponse])
async def get_tasks_by_quadrant(
    quadrant: str,
    db: AsyncSession = Depends(get_async_session)
) -> List[TaskResponse]:
    if quadrant not in ["Q1", "Q2", "Q3", "Q4"]:
        raise HTTPException(    # специальный класс в FastAPI для возврата HTTP ошибок. Не забудьте добавть его импорт в 1 строке
            status_code=400, 
            detail="Неверный квадрант. Используйте: Q1, Q2, Q3, Q4"  # текст, который будет выведен пользователю 
        )
    # SELECT * FROM tasks WHERE quadrant = 'Q1'
    result = await db.execute(
        select(Task).where(Task.quadrant == quadrant)
    )
    tasks = result.scalars().all()
    return tasks

@router.get("/search", response_model=List[TaskResponse])
async def search_tasks(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_async_session)                  
) -> List[TaskResponse]:
    keyword = f"%{q.lower()}%"  # %keyword% для LIKE
    # SELECT * FROM tasks 
    # WHERE LOWER(title) LIKE '%keyword%' 
    #    OR LOWER(description) LIKE '%keyword%'
    result = await db.execute(
        select(Task).where(
            (Task.title.ilike(keyword)) | 
            (Task.description.ilike(keyword))
        )
    )
    tasks = result.scalars().all()

    if not tasks:
        raise HTTPException(status_code=404, detail="По данному запросу ничего не найдено")

    return tasks

@router.get("/status/{status}", response_model=List[TaskResponse])
async def get_tasks_by_status(status: str,
    db: AsyncSession = Depends(get_async_session)                          
) -> List[TaskResponse]:
    if status not in ["completed", "pending"]:
        raise HTTPException(status_code=404, detail="Недопустимый статус. Используйте: completed или pending")

    is_completed = (status == "completed")
    # SELECT * FROM tasks WHERE completed = True/False
    result = await db.execute(
        select(Task).where(Task.completed == is_completed)
    )
    
    tasks = result.scalars().all()

    return tasks

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_by_id(
    task_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> TaskResponse:
   # SELECT * FROM tasks WHERE id = task_id
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    # Получаем одну задачу или None
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    days_deadline = calculate_days_until_deadline(task.deadline_at)

    task_dict = task.__dict__.copy()
    task_dict['days_until_deadline'] = days_deadline # Добавляем вычисленное значение
    
    # 2. Проверяем, просрочена ли задача (если дедлайн существует)
    if task.deadline_at is not None and days_deadline is not None and days_deadline < 0:
        task_dict['status_message'] = "Задача просрочена" # <-- ДОБАВЛЯЕМ СООБЩЕНИЕ!
    else:
        task_dict['status_message'] = "Все идет по плану!"
    return TaskResponse(**task_dict)

@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task: TaskCreate,
    db: AsyncSession = Depends(get_async_session)
) -> TaskResponse:
    # Вычисляем срочность на основе дедлайна
    is_urgent = calculate_urgency(task.deadline_at)
    
    # Определяем квадрант
    quadrant = determine_quadrant(task.is_important, is_urgent)

    new_task = Task(
        title=task.title,
        description=task.description,
        is_important=task.is_important,
        is_urgent=is_urgent, # Вычисленное значение
        quadrant=quadrant,
        deadline_at=task.deadline_at, 
        completed=False  # Новая задача всегда не выполнена
    )

    db.add(new_task)  # Добавляем в сессию (еще не в БД!)
    await db.commit()  # Выполняем INSERT в БД
    await db.refresh(new_task)  # Обновляем объект (получаем ID из БД)
    # FastAPI автоматически преобразует Task → TaskResponse    
    return new_task

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int, 
    task_update: TaskUpdate,
    db: AsyncSession = Depends(get_async_session)
) -> TaskResponse:
    # ШАГ 1: по аналогии с GET ищем задачу по ID
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    # Получаем одну задачу или None
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    # ШАГ 2: Получаем и обновляем только переданные поля (exclude_unset=True)
    # Без exclude_unset=True все None поля тоже попадут в БД
    update_data = task_update.model_dump(exclude_unset=True)

    # ШАГ 3: Обновить атрибуты объекта
    for field, value in update_data.items():
        setattr(task, field, value)  # task.field = value

    # ШАГ 4: Пересчитываем квадрант, если изменились важность или срочность
    if "is_important" in update_data or "deadline_at" in update_data:
        task.is_urgent = calculate_urgency(task.deadline_at)
        task.quadrant = determine_quadrant(task.is_important, task.is_urgent)

    await db.commit()  # UPDATE tasks SET ... WHERE id = task_id
    await db.refresh(task)  # Обновить объект из БД
    
    return task

@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> dict:
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    # Сохраняем информацию для ответа
    deleted_task_info = {
        "id": task.id,
        "title": task.title
    }

    await db.delete(task)  # Помечаем для удаления
    await db.commit()  # DELETE FROM tasks WHERE id = task_id

    return {
        "message": "Задача успешно удалена",
        "id": deleted_task_info["id"],
        "title": deleted_task_info["title"]
    }

@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: int,
    db: AsyncSession = Depends(get_async_session)
) -> TaskResponse:
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    task.completed = True
    task.completed_at = datetime.now()
    
    await db.commit()
    await db.refresh(task)
    
    return task