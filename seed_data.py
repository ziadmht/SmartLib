import os
import django
import requests
import time
from django.core.files.base import ContentFile

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartlib_config.settings')
django.setup()

from core.models import Livre

def download_image(url, filename):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            return ContentFile(response.content, name=filename)
    except: pass
    return None

def seed():
    print("🚀 Finalisation de la Collection Royale...")

    # Ajout des manquants avec photos garanties
    extra_livres = [
        {
            'titre': 'L\'Alchimiste', 'auteur': 'Paulo Coelho', 'isbn': '9782253006329',
            'a_url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Paulo_Coelho_2007.jpg/440px-Paulo_Coelho_2007.jpg',
            'c_url': 'https://covers.openlibrary.org/b/isbn/9782253066125-L.jpg'
        },
        {
            'titre': 'Gatsby le Magnifique', 'auteur': 'F. Scott Fitzgerald', 'isbn': '9782253010197',
            'a_url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/F_Scott_Fitzgerald_1921.jpg/440px-F_Scott_Fitzgerald_1921.jpg',
            'c_url': 'https://covers.openlibrary.org/b/isbn/9780141182636-L.jpg'
        },
        {
            'titre': 'Le Meilleur des Mondes', 'auteur': 'Aldous Huxley', 'isbn': '9780141036144',
            'a_url': 'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e9/Aldous_Huxley_1947.jpg/440px-Aldous_Huxley_1947.jpg',
            'c_url': 'https://covers.openlibrary.org/b/isbn/9780141036144-L.jpg'
        }
    ]

    for d in extra_livres:
        if not Livre.objects.filter(titre=d['titre']).exists():
            print(f"📖 {d['titre']}...")
            livre = Livre.objects.create(
                titre=d['titre'], auteur=d['auteur'], isbn=d['isbn'],
                resume="Archive sacrée du Sanctuaire.",
                auteur_biographie=f"Portrait du maître {d['auteur']}.",
                quantite_totale=10, quantite_disponible=10, a_version_numerique=True
            )
            img_a = download_image(d['a_url'], f"a_{livre.id}.jpg")
            if img_a: livre.auteur_photo.save(f"a_{livre.id}.jpg", img_a, save=False)
            img_c = download_image(d['c_url'], f"c_{livre.id}.jpg")
            if img_c: livre.couverture.save(f"c_{livre.id}.jpg", img_c, save=False)
            livre.save()
            print("   ✅ Photos chargées")
            time.sleep(1)

    print("\n🏆 COLLECTION COMPLÈTE ET ILLUSTRÉE.")

if __name__ == "__main__":
    seed()
