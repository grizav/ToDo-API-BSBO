from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
from database import init_db, get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from routers import tasks, stats
from scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Код ДО yield выполняется при ЗАПУСКЕ
    print("🚀 Запуск приложения...")
    print("🔄 Инициализация базы данных...")

    # Создаем таблицы (если их нет)
    await init_db()
    print("✅ База данных инициализирована!")

    # Запускаем планировщик фоновых задач
    scheduler = start_scheduler()
    print("✅ Приложение готово к работе!")
    yield  # Здесь приложение работает
    
    # Код ПОСЛЕ yield выполняется при ОСТАНОВКЕ
    print("👋 Остановка планировщика...")
    scheduler.shutdown()
    print("👋 Остановка приложения...")

app = FastAPI(
    title="ToDo лист API",
    description="API для управления задачами с использованием матрицы Эйзенхауэра",
    version="2.1.0",
    contact={
        "name": "Ваше Имя",
    },
    lifespan=lifespan  # Подключаем lifespan
)

app.include_router(tasks.router, prefix="/api/v2") # подключение роутера к приложению
app.include_router(stats.router, prefix="/api/v2")

@app.get("/")
async def read_root() -> dict:
    return {
        "message": "Task Manager API - Управление задачами по матрице Эйзенхауэра",
        "version": "2.1.0",
        "database": "PostgreSQL (Supabase)",
        "docs": "/docs",
        "redoc": "/redoc",
    }

@app.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_async_session)
) -> dict:
    """
    Проверка здоровья API и динамическая проверка подключения к БД.
    """
    try:
        # Пытаемся выполнить простейший запрос к БД
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy",
        "database": db_status
    }