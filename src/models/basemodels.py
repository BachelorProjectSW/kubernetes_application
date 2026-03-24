from pydantic import BaseModel


class Question(BaseModel):
    """Question class."""

    question: str
