import os
import django
import requests
from django.core.files.base import ContentFile

# Configuration de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartlib_config.settings')
django.setup()

from core.models import Livre

def download_image(url):
    """Télécharge une image depuis une URL et retourne un ContentFile Django."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        r = requests.get(url, timeout=15, headers=headers)
        if r.status_code == 200:
            return ContentFile(r.content)
    except Exception as e:
        print(f"Erreur téléchargement image {url}: {e}")
    return None

def seed():
    print("🚀 Transformation de la bibliothèque en mode 'Prestige'...")
    
    books_data = [
        {
            "isbn": "9782070408504",
            "titre": "L'Alchimiste",
            "cover_url": "https://m.media-amazon.com/images/I/71n5v-jIidL._AC_UF1000,1000_QL80_.jpg",
            "author_url": "https://upload.wikimedia.org/wikipedia/commons/0/0b/Paulo_Coelho_2013.jpg"
        },
        {
            "isbn": "9782070368224",
            "titre": "1984",
            "cover_url": "https://m.media-amazon.com/images/I/91SZSW8qSsL._AC_UF1000,1000_QL80_.jpg",
            "author_url": "https://upload.wikimedia.org/wikipedia/commons/7/7e/George_Orwell_press_photo.jpg"
        },
        {
            "isbn": "9782253006329",
            "titre": "Le Petit Prince",
            "cover_url": "https://m.media-amazon.com/images/I/71Odf8iN4vL._AC_UF1000,1000_QL80_.jpg",
            "author_url": "https://upload.wikimedia.org/wikipedia/commons/7/7e/Antoine_de_Saint-Exup%C3%A9ry.jpg"
        },
        {
            "isbn": "9780141036144",
            "titre": "Le Meilleur des Mondes",
            "cover_url": "https://m.media-amazon.com/images/I/81zEf2AU0pL._AC_UF1000,1000_QL80_.jpg",
            "author_url": "https://upload.wikimedia.org/wikipedia/commons/e/e9/Aldous_Huxley_1947.jpg"
        }
    ]

    for data in books_data:
        livre = Livre.objects.filter(isbn=data['isbn']).first()
        if livre:
            print(f"🏛️ Restauration des archives pour : {data['titre']}...")
            
            # Couverture vintage
            cover_file = download_image(data['cover_url'])
            if cover_file:
                livre.couverture.save(f"vintage_cover_{data['isbn']}.jpg", cover_file, save=False)
            
            # Photo auteur prestige
            author_file = download_image(data['author_url'])
            if author_file:
                livre.auteur_photo.save(f"prestige_author_{data['isbn']}.jpg", author_file, save=False)
                
            livre.save()
            print(f"✅ {data['titre']} mis à jour.")

    print("\n✨ La métamorphose est terminée. SmartLib est maintenant un sanctuaire du savoir.")

if __name__ == "__main__":
    seed()
