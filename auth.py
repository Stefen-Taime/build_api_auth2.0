from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv


def get_db(request: Request):
    return request.app.mongodb

# Charger les variables d'environnement
load_dotenv()

MONGO_DETAILS = os.getenv('MONGO_DETAILS')
SECRET_KEY = os.getenv('SECRET_KEY')  
ALGORITHM = os.getenv('ALGORITHM')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES'))

# Modèles
class UserBase(BaseModel):
    username: str
    email: Optional[str] = None

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: str
    class Config:
        from_attributes = True

class TokenData(BaseModel):
    username: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

# CryptContext pour le hashage du mot de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Fonctions d'authentification
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

async def authenticate_user(db, username: str, password: str):
    user = await db["users"].find_one({"username": username})
    if user:
        if verify_password(password, user["password"]):
            return user
    return None

# Création du routeur
router = APIRouter()

async def get_user(db, username: str):
    user = await db["users"].find_one({"username": username})
    if user:
        user["id"] = str(user["_id"])  # Convertir l'ID de l'utilisateur en une chaîne
        del user["_id"]  # Supprimer le champ _id original
    return user


# Fonction pour créer un token d'accès
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Routes
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncIOMotorClient = Depends(get_db)):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/users/", response_model=User)
async def create_user(user: UserCreate, db: AsyncIOMotorClient = Depends(get_db)):
    hashed_password = get_password_hash(user.password)
    db_user = {"username": user.username, "password": hashed_password}
    collection = db["users"]
    user_id = await collection.insert_one(db_user)
    new_user = await collection.find_one({"_id": user_id.inserted_id})
    new_user["id"] = str(new_user["_id"])
    del new_user["_id"]
    return new_user
