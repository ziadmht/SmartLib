import os
import django
import sys
from datetime import timedelta
from django.utils import timezone

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartlib_config.settings')
django.setup()

from core.models import User, Livre, Emprunt, Penalite

def setup_demo_user():
    u, _ = User.objects.get_or_create(username='adherent_test')
    u.penalites.all().delete()
    u.emprunts.all().delete()
    u.debloque_par_admin = False
    u.save()
    return u

def scenario_petit_retard():
    print("--- SCÉNARIO A : PETIT RETARD (Tolérance) ---")
    u = setup_demo_user()
    l = Livre.objects.first()
    date_e = timezone.now() - timedelta(days=16) 
    e = Emprunt.objects.create(adherent=u, livre=l, date_emprunt=date_e, date_retour_prevue=date_e + timedelta(days=15))
    print(f"RÉSULTAT : {u.username} a un retard de 3 MAD. Il peut encore utiliser la E-Library.")

def scenario_blocage_total():
    print("--- SCÉNARIO B : NÉGLIGENCE GRAVE (Blocage J10) ---")
    u = setup_demo_user()
    l = Livre.objects.last()
    date_e = timezone.now() - timedelta(days=25) 
    e = Emprunt.objects.create(adherent=u, livre=l, date_emprunt=date_e, date_retour_prevue=date_e + timedelta(days=15))
    print(f"RÉSULTAT : {u.username} dépasse les 7 jours de retard. Son compte est TOTALEMENT BLOQUÉ.")

def scenario_amende_admin():
    print("--- SCÉNARIO C : SANCTION ADMINISTRATIVE ---")
    u = setup_demo_user()
    Penalite.objects.create(adherent=u, montant=100, est_reglee=False)
    print("RÉSULTAT : L'Admin a infligé une amende de 100 MAD. Accès suspendu.")

def scenario_treve_paiement():
    print("--- SCÉNARIO D : RÉGULARISATION AVEC TRÊVE ---")
    u = setup_demo_user()
    l = Livre.objects.first()
    # Créer un retard de 40 MAD (donc bloqué)
    date_e = timezone.now() - timedelta(days=23)
    e = Emprunt.objects.create(adherent=u, livre=l, date_emprunt=date_e, date_retour_prevue=date_e + timedelta(days=15))
    print(f"ÉTAT INITIAL : Dette de {e.calculer_penalite()} MAD. Compte BLOQUÉ.")
    print("ACTION : L'adhérent paye sans rendre le livre...")
    # On simule l'appel à payer_dette_en_cours
    e.date_retour_prevue = timezone.now() + timedelta(days=1)
    e.save()
    Penalite.objects.create(adherent=u, montant=40, est_reglee=True, date_paiement=timezone.now())
    print("RÉSULTAT : Dette latente retombe à 0 MAD. Compte DÉBLOQUÉ pour 24h.")

def scenario_override_admin():
    print("--- SCÉNARIO E : PRIVILÈGE ADMINISTRATEUR ---")
    u = setup_demo_user()
    Penalite.objects.create(adherent=u, montant=500, est_reglee=False)
    print("ÉTAT : Dette de 500 MAD. Théoriquement bloqué.")
    u.debloque_par_admin = True
    u.save()
    print("RÉSULTAT : L'Admin a forcé le déblocage. L'adhérent a accès à tout malgré sa dette.")

def scenario_multi_retards():
    print("--- SCÉNARIO F : ACCUMULATION DE PETITS RETARDS ---")
    u = setup_demo_user()
    livres = Livre.objects.all()[:3]
    for idx, l in enumerate(livres):
        # Chaque livre a 2 jours de retard (6 MAD chacun)
        date_e = timezone.now() - timedelta(days=17)
        Emprunt.objects.create(adherent=u, livre=l, date_emprunt=date_e, date_retour_prevue=date_e + timedelta(days=15))
    print(f"RÉSULTAT : 3 livres en retard = {u.get_dette_totale()} MAD. Toujours ACTIF car < 35 MAD.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].upper()
        scenarios = {
            'A': scenario_petit_retard,
            'B': scenario_blocage_total,
            'C': scenario_amende_admin,
            'D': scenario_treve_paiement,
            'E': scenario_override_admin,
            'F': scenario_multi_retards,
        }
        if cmd in scenarios:
            scenarios[cmd]()
        else:
            print(f"Scénario {cmd} inconnu.")
    else:
        print("Usage: python demo_scenarios.py [A|B|C|D|E|F]")
