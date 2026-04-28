import os
import django
import sys
from datetime import timedelta
from django.utils import timezone

# Configuration de Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartlib_config.settings')
django.setup()

from core.models import User, Livre, Emprunt, Penalite, PlanAbonnement, Abonnement

def tester_cycle_sanction():
    print("--- DÉBUT DU TEST DU CYCLE DE SANCTION ---")
    
    # 1. Préparation des données
    User.objects.filter(username='test_user').delete()
    user = User.objects.create_user(username='test_user', password='password123', role='adherent')
    
    plan, _ = PlanAbonnement.objects.get_or_create(nom='Premium', defaults={'limite_emprunts_physiques': 5, 'acces_e_library': True})
    Abonnement.objects.create(adherent=user, plan=plan, date_debut=timezone.now(), date_fin=timezone.now() + timedelta(days=30))
    
    livre = Livre.objects.create(titre="Livre Test Sanction", auteur="Auteur Test", quantite_totale=1, quantite_disponible=1)
    
    print(f"Étape 1 : Utilisateur '{user.username}' créé avec abonnement Premium.")
    
    # 2. Création d'un emprunt en retard (il y a 20 jours)
    date_emprunt = timezone.now() - timedelta(days=20)
    emprunt = Emprunt.objects.create(
        adherent=user, 
        livre=livre, 
        date_emprunt=date_emprunt,
        date_retour_prevue=date_emprunt + timedelta(days=15)
    )
    livre.decrementer_stock()
    
    print(f"Étape 2 : Emprunt créé il y a 20 jours. Date retour prévue : {emprunt.date_retour_prevue}")
    print(f"Retard actuel : {emprunt.calculer_penalite()} MAD")
    
    # Vérification blocage
    # Le retard seul ne bloque plus (nouveau système simplifié)
    peut, msg = user.peut_emprunter()
    print(f"Compte bloqué par retard en cours ? {'NON' if peut else 'OUI'} ({msg})")
    
    # 3. Clôture de l'emprunt (Retour du livre)
    print("Étape 3 : Le Bibliothécaire clôture l'emprunt...")
    emprunt.retourner_livre()
    
    # Une pénalité doit avoir été créée
    penalite = Penalite.objects.get(adherent=user, est_reglee=False)
    print(f"Pénalité enregistrée en BDD : {penalite.montant} MAD")
    
    # Vérification blocage réel
    peut, msg = user.peut_emprunter()
    print(f"Compte bloqué après retour ? {'NON' if peut else 'OUI'} ({msg})")
    
    # 4. Paiement de la pénalité
    print("Étape 4 : L'Adhérent paie sa pénalité...")
    penalite.regler()
    
    # Vérification déblocage
    peut, msg = user.peut_emprunter()
    print(f"Compte débloqué après paiement ? {'OUI' if peut else 'NON'} ({msg})")
    
    print("--- TEST TERMINÉ AVEC SUCCÈS ---")

if __name__ == "__main__":
    tester_cycle_sanction()
