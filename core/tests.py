from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import PlanAbonnement, Abonnement, Livre, Emprunt, Penalite

User = get_user_model()


class UserModelTest(TestCase):
    """Tests du modèle User"""
    
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_test',
            password='test123',
            role='admin'
        )
        self.adherent = User.objects.create_user(
            username='adherent_test',
            password='test123',
            role='adherent'
        )
    
    def test_est_administrateur(self):
        self.assertTrue(self.admin.est_administrateur())
        self.assertFalse(self.adherent.est_administrateur())
    
    def test_est_adherent(self):
        self.assertTrue(self.adherent.est_adherent())
        self.assertFalse(self.admin.est_adherent())


class PlanAbonnementTest(TestCase):
    """Tests des plans d'abonnement"""
    
    def setUp(self):
        self.standard = PlanAbonnement.objects.create(
            nom='Standard',
            limite_emprunts_physiques=2,
            acces_e_library=False
        )
        self.premium = PlanAbonnement.objects.create(
            nom='Premium',
            limite_emprunts_physiques=5,
            acces_e_library=True
        )
    
    def test_limites_standard(self):
        self.assertEqual(self.standard.limite_emprunts_physiques, 2)
        self.assertFalse(self.standard.acces_e_library)
    
    def test_limites_premium(self):
        self.assertEqual(self.premium.limite_emprunts_physiques, 5)
        self.assertTrue(self.premium.acces_e_library)


class LivreModelTest(TestCase):
    """Tests du modèle Livre"""
    
    def setUp(self):
        self.livre = Livre.objects.create(
            titre='Test Livre',
            auteur='Test Auteur',
            isbn='9782070541270',
            quantite_totale=3,
            quantite_disponible=3
        )
    
    def test_est_disponible(self):
        self.assertTrue(self.livre.est_disponible_physique())
    
    def test_decrementer_stock(self):
        self.livre.decrementer_stock()
        self.assertEqual(self.livre.quantite_disponible, 2)
    
    def test_incrementer_stock(self):
        self.livre.quantite_disponible = 1
        self.livre.save()
        self.livre.incrementer_stock()
        self.assertEqual(self.livre.quantite_disponible, 2)


class EmpruntWorkflowTest(TestCase):
    """Tests du workflow d'emprunt"""
    
    def setUp(self):
        # Créer un adhérent
        self.adherent = User.objects.create_user(
            username='emprunteur',
            password='test123',
            role='adherent'
        )
        
        # Créer un plan Standard
        self.plan = PlanAbonnement.objects.create(
            nom='Standard',
            limite_emprunts_physiques=2
        )
        
        # Créer un abonnement
        self.abonnement = Abonnement.objects.create(
            adherent=self.adherent,
            plan=self.plan,
            date_debut=timezone.now(),
            date_fin=timezone.now() + timedelta(days=30),
            est_actif=True
        )
        
        # Créer un livre
        self.livre = Livre.objects.create(
            titre='Livre Test',
            auteur='Auteur Test',
            quantite_totale=2,
            quantite_disponible=2
        )
    
    def test_peut_emprunter(self):
        peut, message = self.adherent.peut_emprunter()
        self.assertTrue(peut)
    
    def test_creer_emprunt(self):
        emprunt = Emprunt.objects.create(
            adherent=self.adherent,
            livre=self.livre,
            statut='demande'
        )
        self.assertEqual(emprunt.statut, 'demande')
        self.assertIsNotNone(emprunt.date_emprunt)
    
    def test_approuver_emprunt(self):
        emprunt = Emprunt.objects.create(
            adherent=self.adherent,
            livre=self.livre,
            statut='demande'
        )
        success, msg = emprunt.approuver()
        self.assertTrue(success)
        self.assertEqual(emprunt.statut, 'en_cours')


class PenaliteTest(TestCase):
    """Tests des pénalités"""
    
    def setUp(self):
        self.adherent = User.objects.create_user(
            username='test_penalite',
            password='test123',
            role='adherent'
        )
        
        self.plan = PlanAbonnement.objects.create(nom='Standard')
        Abonnement.objects.create(
            adherent=self.adherent,
            plan=self.plan,
            date_debut=timezone.now(),
            date_fin=timezone.now() + timedelta(days=30),
            est_actif=True
        )
        
        self.livre = Livre.objects.create(
            titre='Livre Test',
            auteur='Auteur Test',
            quantite_totale=1,
            quantite_disponible=1
        )
    
    def test_calcul_penalite(self):
        # Créer un emprunt qui aurait dû être rendu il y a 5 jours
        # Emprunt fait il y a 20 jours, retour prévu à J+15
        emprunt = Emprunt.objects.create(
            adherent=self.adherent,
            livre=self.livre,
            date_emprunt=timezone.now() - timedelta(days=20),
            statut='en_cours'
        )
        # Calcul manuel de la date de retour prévue pour le test
        emprunt.date_retour_prevue = emprunt.date_emprunt + timedelta(days=15)
        emprunt.save()
        
        penalite = emprunt.calculer_penalite()
        self.assertGreater(penalite, 0)
    
    def test_retour_sans_penalite(self):
        emprunt = Emprunt.objects.create(
            adherent=self.adherent,
            livre=self.livre,
            date_emprunt=timezone.now(),
            statut='demande'
        )
        # Approuver pour définir la date de retour prévue
        emprunt.approuver()
        success, msg = emprunt.retourner_livre()
        self.assertTrue(success)
        self.assertEqual(emprunt.statut, 'rendu')
