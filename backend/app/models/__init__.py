# Import all models here so Alembic's autogenerate can see them.
from app.models.course import Course  # noqa: F401
from app.models.flashcard import Flashcard  # noqa: F401
from app.models.review import ReviewConfig, ReviewLog  # noqa: F401
from app.models.user import User  # noqa: F401
