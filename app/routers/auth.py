from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import timedelta
from ..database import get_db, User
from ..models import UserCreate, UserResponse, Token
from ..auth import authenticate_user, create_access_token, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES
from ..language import get_language, get_translation, get_direction, get_all_translations

templates = Jinja2Templates(directory="templates")

router = APIRouter(prefix="/auth", tags=["authentication"])

def get_template_context(request: Request, **kwargs):
    """Get template context with language support"""
    context = {
        "request": request,
        "get_language": get_language,
        "get_translation": get_translation,
        "get_direction": get_direction,
        "get_all_translations": get_all_translations,
        **kwargs
    }
    return context

# API endpoints (JSON)
@router.post("/api/register", response_model=UserResponse)
def api_register(user: UserCreate, db: Session = Depends(get_db)):
    """API registration endpoint (JSON)"""
    # Check if user already exists
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )
    
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

@router.post("/api/login", response_model=Token)
def api_login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """API login endpoint (JSON)"""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Web endpoints (HTML forms)
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("owa/login.html", get_template_context(request))

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    """Register page"""
    return templates.TemplateResponse("owa/register.html", get_template_context(request))

@router.post("/login", response_class=HTMLResponse)
async def web_login(request: Request, db: Session = Depends(get_db)):
    """Web login form handler"""
    try:
        form_data = await request.form()
        username = form_data.get("username")
        password = form_data.get("password")
        
        user = authenticate_user(db, username, password)
        if not user:
            return templates.TemplateResponse("owa/login.html", get_template_context(
                request, 
                error="Invalid username or password"
            ))
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        
        response = RedirectResponse(url="/owa/", status_code=302)
        response.set_cookie(key="access_token", value=access_token, httponly=True)
        return response
        
    except Exception as e:
        return templates.TemplateResponse("owa/login.html", get_template_context(
            request, 
            error=f"Login failed: {str(e)}"
        ))

@router.post("/register", response_class=HTMLResponse)
async def web_register(request: Request, db: Session = Depends(get_db)):
    """Web register form handler"""
    try:
        form_data = await request.form()
        
        # Check if user already exists
        db_user = db.query(User).filter(User.username == form_data.get("username")).first()
        if db_user:
            return templates.TemplateResponse("owa/register.html", get_template_context(
                request, 
                error="Username already registered"
            ))
        
        db_user = db.query(User).filter(User.email == form_data.get("email")).first()
        if db_user:
            return templates.TemplateResponse("owa/register.html", get_template_context(
                request, 
                error="Email already registered"
            ))
        
        # Create new user
        hashed_password = get_password_hash(form_data.get("password"))
        db_user = User(
            username=form_data.get("username"),
            email=form_data.get("email"),
            hashed_password=hashed_password,
            full_name=form_data.get("full_name")
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        # Auto-login after registration
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": db_user.username}, expires_delta=access_token_expires
        )
        
        response = RedirectResponse(url="/owa/", status_code=302)
        response.set_cookie(key="access_token", value=access_token, httponly=True)
        return response
        
    except Exception as e:
        return templates.TemplateResponse("owa/register.html", get_template_context(
            request, 
            error=f"Registration failed: {str(e)}"
        ))
