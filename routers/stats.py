from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, column, text
from models import Task
from database import get_async_session
from datetime import datetime, timezone
from schemas import TimingStatsResponse


router = APIRouter(
    prefix="/stats",
    tags=["statistics"]
)

@router.get("/", response_model=dict)
async def get_tasks_stats(db: AsyncSession = Depends(get_async_session)) -> dict:
    # Общее количество задач
    total_result = await db.execute(select(func.count(Task.id)))
    total_tasks = total_result.scalar()
    
    # Подсчет по квадрантам (одним запросом)
    quadrant_result = await db.execute(
        select(
            Task.quadrant,
            func.count(Task.id).label('count')
        ).group_by(Task.quadrant)
    )
    by_quadrant = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    for row in quadrant_result:
        by_quadrant[row.quadrant] = row.count
    
    # Подсчет по статусу (одним запросом)
    status_result = await db.execute(
        select(
            func.count(case((Task.completed == True, 1))).label('completed'),
            func.count(case((Task.completed == False, 1))).label('pending')
        )
    )
    status_row = status_result.one()
    by_status = {
        "completed": status_row.completed,
        "pending": status_row.pending
    }

    return {
        "total_tasks": total_tasks,
        "by_quadrant": by_quadrant,
        "by_status": by_status
    }

@router.get("/timing", response_model=TimingStatsResponse)
async def get_deadline_stats(db: AsyncSession = Depends(get_async_session)) -> TimingStatsResponse:    
    now_utc = datetime.now(timezone.utc)  # Получаем текущее время в UTC для сравнения с дедлайнами

    # Формируем SQL-запрос с агрегацией (COUNT + CASE)
    # Сгенерированный SQL (примерно, SQLAlchemy может добавлять алиасы и типы):
    # SELECT
    #   SUM(CASE WHEN (tasks.completed = true AND tasks.completed_at <= tasks.deadline_at) THEN 1 ELSE 0 END) AS completed_on_time,
    #   SUM(CASE WHEN (tasks.completed = true AND tasks.completed_at > tasks.deadline_at) THEN 1 ELSE 0 END) AS completed_late,
    #   SUM(CASE WHEN (tasks.completed = false AND tasks.deadline_at IS NOT NULL AND tasks.deadline_at > :now_utc) THEN 1 ELSE 0 END) AS on_plan_pending,
    #   SUM(CASE WHEN (tasks.completed = false AND tasks.deadline_at IS NOT NULL AND tasks.deadline_at <= :now_utc) THEN 1 ELSE 0 END) AS overdue_pending
    # FROM tasks
    statement = select(
        func.sum(
            case(((Task.completed == True) & (Task.completed_at <= Task.deadline_at), 1), else_=0)
        ).label("completed_on_time"),
        func.sum(
            case(((Task.completed == True) & (Task.completed_at > Task.deadline_at), 1), else_=0)
        ).label("completed_late"),
        func.sum(
            case(((Task.completed == False) & (Task.deadline_at != None) & (Task.deadline_at > now_utc), 1), else_=0)
        ).label("on_plan_pending"),
        func.sum(
            case(((Task.completed == False) & (Task.deadline_at != None) & (Task.deadline_at <= now_utc), 1), else_=0)
        ).label("overdue_pending"),
    ).select_from(Task)

    result = await db.execute(statement)
    stats_row = result.one()

    # Возвращаем результат, используя новую Pydantic-схему
    return TimingStatsResponse(
        completed_on_time=stats_row.completed_on_time or 0,
        completed_late=stats_row.completed_late or 0,
        on_plan_pending=stats_row.on_plan_pending or 0,
        overtime_pending=stats_row.overdue_pending or 0,
    )