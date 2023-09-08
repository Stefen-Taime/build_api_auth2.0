from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorClient
import pandas as pd
from typing import List, Union
import os
from dotenv import load_dotenv
from auth import router as auth_router, get_user, TokenData, User, get_db


# Charger les variables d'environnement
load_dotenv()
MONGO_DETAILS = os.getenv('MONGO_DETAILS')
SECRET_KEY = os.getenv('SECRET_KEY')  
ALGORITHM = os.getenv('ALGORITHM')  
ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES')
# Lire les données
file_paths = [
    'genome_tags.csv',
    'link.csv',
    'movie.csv',
    'tag.csv',
    'genome_scores.csv'
]

# Un dictionnaire pour stocker les dataframes
dataframes = {}

# Lire les fichiers et stocker dans le dictionnaire
for path in file_paths:
    try:
        file_name = path.split('/')[-1].replace('.csv', '')
        dataframes[file_name] = pd.read_csv(path)
    except FileNotFoundError:
        print(f"Le fichier {path} n'a pas été trouvé.")


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncIOMotorClient = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = await get_user(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


# Créer une instance de FastAPI
app = FastAPI()

# Connexion à MongoDB
@app.on_event("startup")
async def startup():
    app.mongodb_client = AsyncIOMotorClient(MONGO_DETAILS)
    app.mongodb = app.mongodb_client.get_database()

@app.on_event("shutdown")
async def shutdown():
    app.mongodb_client.close()

# Inclure le routeur d'authentification
app.include_router(auth_router)

def filter_movies(genres: Union[str, List[str]] = None, tags: Union[str, List[str]] = None, limit: int = 10):
    if genres:
        if isinstance(genres, str):
            genres = [genres]
        genre_filter = dataframes['movie']['genres'].apply(lambda x: any(genre in x for genre in genres))
    else:
        genre_filter = True

    if tags:
        if isinstance(tags, str):
            tags = [tags]
        tag_ids = dataframes['genome_tags'][dataframes['genome_tags']['tag'].isin(tags)]['tagId']
        movie_ids_with_tags = dataframes['genome_scores'][dataframes['genome_scores']['tagId'].isin(tag_ids)]['movieId']
        tag_filter = dataframes['movie']['movieId'].isin(movie_ids_with_tags)
    else:
        tag_filter = True

    filtered_movies = dataframes['movie'][genre_filter & tag_filter].head(limit)
    
    return filtered_movies

def get_movie_details(movieId: int):
    movie_details = dataframes['movie'][dataframes['movie']['movieId'] == movieId].iloc[0].to_dict()
    links = dataframes['link'][dataframes['link']['movieId'] == movieId].iloc[0].to_dict()
    movie_details.update(links)
    return movie_details

def get_movie_tags(movieId: int, limit: int = 10):
    tag_scores = dataframes['genome_scores'][dataframes['genome_scores']['movieId'] == movieId]
    tag_names = dataframes['genome_tags']
    movie_tags = tag_scores.merge(tag_names, on='tagId').sort_values(by='relevance', ascending=False)
    movie_tags = movie_tags.head(limit)
    return movie_tags

# Définir les routes
@app.get("/filter_movies")
async def filter_movies_endpoint(current_user: User = Depends(get_current_user), genres: str = None, tags: str = None, limit: int = 10):
    result = filter_movies(genres, tags, limit)
    return result.to_dict(orient='records')

@app.get("/movie_details/{movieId}")
async def get_movie_details_endpoint(movieId: int, current_user: User = Depends(get_current_user)):
    try:
        result = get_movie_details(movieId)
        return result
    except IndexError:
        raise HTTPException(status_code=404, detail="Movie not found")

@app.get("/movie_tags/{movieId}")
async def get_movie_tags_endpoint(movieId: int, limit: int = 10, current_user: User = Depends(get_current_user)):
    try:
        result = get_movie_tags(movieId, limit)
        return result.to_dict(orient='records')
    except IndexError:
        raise HTTPException(status_code=404, detail="Movie not found")