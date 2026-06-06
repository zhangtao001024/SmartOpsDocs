from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models.entities import User


def init_database() -> None:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == settings.initial_admin_username).first():
            db.add(
                User(
                    username=settings.initial_admin_username,
                    password_hash=hash_password(settings.initial_admin_password),
                    role="admin",
                )
            )
            db.commit()
    finally:
        db.close()


settings = get_settings()
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

app = FastAPI(title="SmartOpsDocs API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_database()


@app.get("/health")
def health():
    return {"ok": True}


app.include_router(router)
