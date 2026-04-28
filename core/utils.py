import requests
import json
from django.core.files.base import ContentFile
from django.core.files.temp import NamedTemporaryFile
from urllib.parse import urlparse


from django.core.exceptions import PermissionDenied
from functools import wraps

def admin_required(view_func):
    """Vérifie si l'utilisateur est un Administrateur."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.est_administrateur():
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view

def bibliothecaire_required(view_func):
    """Vérifie si l'utilisateur est au moins un Bibliothécaire."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.est_bibliothecaire() or request.user.est_administrateur()):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied
    return _wrapped_view


def get_book_metadata_by_isbn(isbn):
    """
    Récupère les métadonnées d'un livre depuis Google Books API via son ISBN.
    
    Args:
        isbn (str): Numéro ISBN du livre (10 ou 13 chiffres)
    
    Returns:
        dict: Dictionnaire contenant les infos du livre ou None si erreur
    """
    
    # Nettoyer l'ISBN (enlever les espaces et tirets)
    isbn_clean = isbn.replace(' ', '').replace('-', '')
    
    # Construire l'URL de l'API Google Books
    url = f'https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn_clean}&country=FR'
    
    try:
        # Envoyer la requête
        response = requests.get(url, timeout=5)
        response.raise_for_status()  # Lève une exception si erreur HTTP
        
        # Parser le JSON
        data = response.json()
        
        # Vérifier si des résultats ont été trouvés
        if not data.get('items'):
            return None
        
        # Prendre le premier résultat
        book = data['items'][0]['volumeInfo']
        
        # Extraire les informations
        metadata = {
            'titre': book.get('title', ''),
            'auteur': ', '.join(book.get('authors', ['Auteur inconnu'])),
            'editeur': book.get('publisher', ''),
            'annee_publication': book.get('publishedDate', '').split('-')[0] if book.get('publishedDate') else '',
            'resume': book.get('description', ''),
            'couverture_url': book.get('imageLinks', {}).get('thumbnail', ''),
        }
        
        return metadata
        
    except requests.exceptions.RequestException as e:
        # Erreur réseau ou API indisponible
        print(f"Erreur API Google Books: {e}")
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        # Erreur de parsing JSON
        print(f"Erreur parsing réponse: {e}")
        return None


def download_image_from_url(url):
    """
    Télécharge une image depuis une URL et retourne un ContentFile.
    
    Args:
        url (str): URL de l'image
    
    Returns:
        ContentFile: Fichier image prêt à être sauvegardé, ou None si erreur
    """
    if not url:
        return None
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        # Extraire l'extension et le nom du fichier
        parsed_url = urlparse(url)
        path = parsed_url.path
        extension = path.split('.')[-1] if '.' in path else 'jpg'
        
        # Créer un fichier temporaire
        img_temp = NamedTemporaryFile(delete=True, suffix=f'.{extension}')
        img_temp.write(response.content)
        img_temp.flush()
        
        return ContentFile(response.content, name=f'couverture.{extension}')
        
    except Exception as e:
        print(f"Erreur téléchargement image: {e}")
        return None
