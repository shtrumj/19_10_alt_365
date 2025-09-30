from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..auth import get_current_user_from_cookie
from ..database import User, get_db
from ..language import (
    get_all_translations,
    get_direction,
    get_language,
    get_translation,
)
from ..models import ContactFolderTree, ContactResponse
from ..services.contact_service import ContactService

router = APIRouter(prefix="/contacts", tags=["contacts"])
templates = Jinja2Templates(directory="templates")


def ctx(request: Request, **kwargs):
    return {
        "request": request,
        "get_language": get_language,
        "get_translation": get_translation,
        "get_direction": get_direction,
        "get_all_translations": get_all_translations,
        **kwargs,
    }


def _service(db: Session, user: User) -> ContactService:
    return ContactService(db, user.id)


@router.get("/test")
def contacts_test():
    return {"message": "Contacts router is working"}


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def contacts_home(
    request: Request,
    current_user: Union[User, HTMLResponse, RedirectResponse] = Depends(
        get_current_user_from_cookie
    ),
    db: Session = Depends(get_db),
):
    if not isinstance(current_user, User):
        return current_user

    service = _service(db, current_user)
    folders = service.build_folder_tree()
    default_folder_uuid = None
    for node in folders:
        if node.get("is_default"):
            default_folder_uuid = node["uuid"]
            break
        for child in node.get("children", []):
            if child.get("is_default"):
                default_folder_uuid = child["uuid"]
                break
        if default_folder_uuid:
            break

    contacts = service.list_contacts(default_folder_uuid)
    return templates.TemplateResponse(
        "owa/contacts.html",
        ctx(
            request,
            user=current_user,
            folders=folders,
            active_folder_uuid=default_folder_uuid,
            contacts=contacts,
        ),
    )


@router.get("/folders", response_model=List[ContactFolderTree])
def list_folders(
    current_user: Union[User, JSONResponse, RedirectResponse] = Depends(
        get_current_user_from_cookie
    ),
    db: Session = Depends(get_db),
):
    if not isinstance(current_user, User):
        if isinstance(current_user, RedirectResponse):
            return current_user
        raise HTTPException(status_code=401, detail="Unauthorized")
    service = _service(db, current_user)
    return service.build_folder_tree()


@router.post("/folders")
def create_folder(
    payload: Dict[str, Any],
    current_user: Union[User, JSONResponse, RedirectResponse] = Depends(
        get_current_user_from_cookie
    ),
    db: Session = Depends(get_db),
):
    if not isinstance(current_user, User):
        if isinstance(current_user, RedirectResponse):
            return current_user
        raise HTTPException(status_code=401, detail="Unauthorized")
    display_name = payload.get("display_name")
    if not display_name:
        raise HTTPException(status_code=400, detail="display_name required")
    service = _service(db, current_user)
    folder = service.create_subfolder(
        display_name=display_name,
        parent_uuid=payload.get("parent_uuid"),
        well_known_name=payload.get("well_known_name"),
        description=payload.get("description"),
    )
    return {
        "uuid": folder.uuid,
        "display_name": folder.display_name,
        "parent_uuid": (
            service.get_folder_by_uuid(folder.uuid).parent.uuid
            if folder.parent
            else None
        ),
    }


@router.get("/list", response_model=List[ContactResponse])
def list_contacts_endpoint(
    folder_uuid: Optional[str] = None,
    current_user: Union[User, JSONResponse, RedirectResponse] = Depends(
        get_current_user_from_cookie
    ),
    db: Session = Depends(get_db),
):
    if not isinstance(current_user, User):
        if isinstance(current_user, RedirectResponse):
            return current_user
        raise HTTPException(status_code=401, detail="Unauthorized")
    service = _service(db, current_user)
    contacts = service.list_contacts(folder_uuid)
    return contacts


@router.post("/create")
async def create_contact(
    request: Request,
    current_user: Union[User, HTMLResponse, RedirectResponse] = Depends(
        get_current_user_from_cookie
    ),
    db: Session = Depends(get_db),
):
    if not isinstance(current_user, User):
        return current_user
    form = await request.form()
    data = {k: v for k, v in form.items() if v}
    service = _service(db, current_user)
    contact = service.create_contact(data)
    return {"status": "ok", "uuid": contact.uuid}


@router.get("/{contact_uuid}", response_model=ContactResponse)
def get_contact(
    contact_uuid: str,
    current_user: Union[User, JSONResponse, RedirectResponse] = Depends(
        get_current_user_from_cookie
    ),
    db: Session = Depends(get_db),
):
    if not isinstance(current_user, User):
        if isinstance(current_user, RedirectResponse):
            return current_user
        raise HTTPException(status_code=401, detail="Unauthorized")
    service = _service(db, current_user)
    contact = service.get_contact(contact_uuid)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.put("/{contact_uuid}")
def update_contact(
    contact_uuid: str,
    payload: Dict[str, Any],
    current_user: Union[User, JSONResponse, RedirectResponse] = Depends(
        get_current_user_from_cookie
    ),
    db: Session = Depends(get_db),
):
    if not isinstance(current_user, User):
        if isinstance(current_user, RedirectResponse):
            return current_user
        raise HTTPException(status_code=401, detail="Unauthorized")
    service = _service(db, current_user)
    try:
        contact = service.update_contact(contact_uuid, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return contact


@router.delete("/{contact_uuid}")
def delete_contact(
    contact_uuid: str,
    current_user: Union[User, JSONResponse, RedirectResponse] = Depends(
        get_current_user_from_cookie
    ),
    db: Session = Depends(get_db),
):
    if not isinstance(current_user, User):
        if isinstance(current_user, RedirectResponse):
            return current_user
        raise HTTPException(status_code=401, detail="Unauthorized")
    service = _service(db, current_user)
    if not service.delete_contact(contact_uuid):
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"status": "deleted"}
