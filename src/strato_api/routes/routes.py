from fastapi import APIRouter, HTTPException
from ..services.start_test import start_test, start_test_test
from ...models.basemodels import Config
router = APIRouter()

#TODO Lav experiments tests med test om at det er "noglelunde deterministisk."
#TODO Sørg for at alle logs gir mening og ikke bare spam. 
#TODO LAV DOCSTRINGS TIL ALLE FUNKTIONER!!!
@router.post("/start_test")
def start_test_endpoint(config: Config):
    """Start the test."""
    try:
        return start_test(config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start_test_test")
def start_test_test_endpoint():
    """Start the test test."""
    try:
        return start_test_test()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
