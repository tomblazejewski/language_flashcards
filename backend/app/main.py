from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth as auth_router
from app.api import courses as courses_router
from app.api import imports as imports_router
from app.api import study as study_router
from app.config import settings

app = FastAPI(
    title="Language Flashcards API",
    version="0.1.0",
    description="Backend API for the Language Flashcards spaced-repetition app.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(courses_router.router)
app.include_router(imports_router.router)
app.include_router(study_router.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
