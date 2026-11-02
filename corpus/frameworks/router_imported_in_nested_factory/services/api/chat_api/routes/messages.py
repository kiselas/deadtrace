import fastapi

from chat_api.models import MessageRequest

router = fastapi.APIRouter()


@router.post("/messages")
def deliver_note(request: MessageRequest) -> str:
    return request.text
