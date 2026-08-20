from fastapi import Depends, HTTPException, Header
from typing import Optional
from .db import get_db
from sqlalchemy.orm import Session
from . import models
import secrets


def create_user(db: Session, username: str, display_name: Optional[str] = None):
    api_key = secrets.token_urlsafe(24)
    user = models.User(username=username, display_name=display_name or username, api_key=api_key)
    db.add(user)
    db.flush()
    return user


def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = parts[1]
    user = db.query(models.User).filter(models.User.api_key == token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API token")
    return user
