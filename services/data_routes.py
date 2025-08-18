from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
def test_data():
    return {"message": "Data Service OK"}
