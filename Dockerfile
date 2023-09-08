# Utilisez une image de base Python 3.8
FROM python:3.8

# Définissez la variable d'environnement pour éviter que Python n'écrive des fichiers .pyc
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Installez les dépendances
COPY requirements.txt /usr/src/app/
WORKDIR /usr/src/app/
RUN pip install --no-cache-dir -r requirements.txt

# Copiez le reste de l'application
COPY . /usr/src/app/

# Exposez le port sur lequel l'application sera exécutée
EXPOSE 8000

# Définissez la commande pour exécuter l'application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
