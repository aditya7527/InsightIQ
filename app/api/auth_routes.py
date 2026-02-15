from fastapi import APIRouter, HTTPException, Depends, Form
from passlib.context import CryptContext
from app.models import users
from app.db.session import engine
from app.auth import create_access_token
from sqlalchemy import select, insert

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post('/auth/register')
def register(username: str = Form(...), password: str = Form(...)):
    hashed = pwd_context.hash(password)
    with engine.connect() as conn:
        # check exists
        r = conn.execute(select(users.c.id).where(users.c.username == username)).fetchone()
        if r:
            raise HTTPException(status_code=400, detail='User already exists')
        conn.execute(insert(users).values(username=username, hashed_password=hashed))
        conn.commit()
    token = create_access_token(username)
    return {"access_token": token, "token_type": "bearer"}


@router.post('/auth/login')
def login(username: str = Form(...), password: str = Form(...)):
    with engine.connect() as conn:
        r = conn.execute(select(users).where(users.c.username == username)).fetchone()
        if not r:
            raise HTTPException(status_code=400, detail='Invalid credentials')
        stored = r["hashed_password"]
        if not pwd_context.verify(password, stored):
            raise HTTPException(status_code=400, detail='Invalid credentials')
    token = create_access_token(username)
    return {"access_token": token, "token_type": "bearer"}
