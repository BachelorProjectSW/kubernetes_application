from fastapi import APIRouter, HTTPException
from ..services.start_test import start_test, start_test_test, stop_test, get_test_status
from ..services.test_results import get_test_results
from ...models.basemodels import Config
from ...db.postgres import read_all_configs
router = APIRouter()


# TODO Lav experiments tests med test om at det er "noglelunde deterministisk."
# TODO Sørg for at alle logs gir mening og ikke bare spam.
# TODO LAV DOCSTRINGS TIL ALLE FUNKTIONER!!!
# TODO Sikre sig at CROM Data virker
# TODO få API til at kører hver klokkeslæt time og ikke hver time fra test start.
# TODO calculate cost/gco2 if idle (Jeg tror ikke det er korrekt ift idle times)
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


@router.post("/stop_test")
def stop_test_endpoint():
    """Stop the test."""
    try:
        return stop_test()
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test_status")
def test_status_endpoint():
    """Return current test status: idle, running, or stopping."""
    return get_test_status()


@router.get("/test_results")
def test_results_endpoint(config_id: str):
    """Return stored test results and graph-ready summary data for one config id."""
    try:
        return get_test_results(config_id)
    except HTTPException:
        raise
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_configs")
def get_config_endpoint():
    """Return all configs in the DB as a list."""
    try:
        return [config.model_dump(mode="json") for config in read_all_configs()]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
