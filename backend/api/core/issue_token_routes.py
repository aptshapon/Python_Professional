from fastapi import APIRouter, Header, HTTPException
from utils.json_web_token import JWTAdmin

router = APIRouter(
    prefix="/core",
    tags=["Core"],
    responses={404: {"description": "Not found"}},
)


@router.post("/issueToken")
async def issue_token(api_key: str = Header(..., alias="X-API-Key")):
    """
    Issues a JWT token from the given API key.

    Parameters:
    - api_key (str): The API key to generate the token from.

    Returns:
    - dict: A dictionary with the status and the generated JWT token.
    """
    try:
        jwt_admin = JWTAdmin(api_key)
        jwt_token = jwt_admin.create_jwt_token()
        return {"status": "success", "token": jwt_token}
    except HTTPException as http_exception:
        raise http_exception
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")
