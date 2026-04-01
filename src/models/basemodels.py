from pydantic import BaseModel


class Question(BaseModel):
    """Question class."""

    question: str
    n_predict: int = 64
