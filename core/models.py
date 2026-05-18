from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError

# ==============================================================================
# 1. CLASSE MÉTIER : USER (Gestion des Acteurs et de la Sécurité)
# ==============================================================================
class User(AbstractUser):
    """
    RÔLE : Centraliser l'identité et les droits d'accès (RBAC).
    POURQUOI : Surcharger le modèle User permet de gérer les 3 rôles (Admin, Biblio, Adhérent)
    demandés dans le point 2 du Cahier des Charges.
    """
    
    # Validateur pour numéro de téléphone (format marocain)
    telephone_validator = RegexValidator(
        regex=r'^(06|07|05)\d{8}$',
        message="Le numéro de téléphone doit être un numéro marocain valide (ex: 0612345678)"
    )
    
    telephone = models.CharField(
        max_length=10,
        validators=[telephone_validator],
        blank=True, 
        null=True,
        help_text="Numéro marocain à 10 chiffres"
    )
    adresse = models.TextField(blank=True, null=True)
    
    # Système de rôles (Point 2 du CDC)
    ROLE_CHOICES = (
        ('admin', 'Administrateur'),
        ('bibliothecaire', 'Bibliothécaire'),
        ('adherent', 'Adhérent'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='adherent')
    photo_profil = models.ImageField(upload_to='profiles/', blank=True, null=True)
    
    # Privilège Admin (Override)
    debloque_par_admin = models.BooleanField(default=False, help_text="Permet à l'admin de gracier un blocage automatique")
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    # --- LOGIQUE D'AUTORISATION ---
    
    def est_administrateur(self):
        return self.role == 'admin' or self.is_superuser

    class Meta:
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['role']),
        ]
    
    def est_bibliothecaire(self):
        return self.role == 'bibliothecaire' or self.est_administrateur()
    
    def est_adherent(self):
        return self.role == 'adherent'
    
    # --- LOGIQUE MÉTIER (Règles J10 du CDC) ---
    
    def get_dette_totale(self):
        """
        Somme de TOUT ce que l'adhérent doit :
        Pénalités enregistrées (impayées) + Retards sur les livres non rendus.
        """
        dette_reelle = sum(p.montant for p in self.penalites.filter(est_reglee=False))
        
        dette_latente = 0
        for e in self.emprunts.filter(est_retourne=False):
            dette_latente += e.calculer_penalite()
            
        return dette_reelle + dette_latente

    def a_penalite_impayee(self):
        """
        Condition de blocage :
        - True si une pénalité réelle (livre rendu) est impayée.
        - True si le retard cumulé en cours dépasse 30 MAD (10 jours à 3 MAD/j).
        """
        # 1. Bloqué si une pénalité réelle traîne
        if self.penalites.filter(est_reglee=False).exists():
            return True
            
        # 2. Bloqué si le retard "en direct" devient trop gros (10 jours)
        dette_latente = sum(e.calculer_penalite() for e in self.emprunts.filter(est_retourne=False))
        return dette_latente >= 30

    def est_suspendu_totalement(self):
        """Bloqué si une pénalité impayée a plus de 10 jours."""
        limite = timezone.now() - timedelta(days=10)
        return self.penalites.filter(est_reglee=False, date_creation__lte=limite).exists()

    def get_abonnement_actif(self):
        """Récupère l'abonnement valide à l'instant T."""
        aujourdhui = timezone.now()
        return self.abonnements.filter(est_actif=True, date_debut__lte=aujourdhui, date_fin__gte=aujourdhui).first()

    def peut_emprunter(self):
        """Vérification centralisée des droits d'emprunt (J8)."""
        if self.debloque_par_admin:
            return True, "DÉBLOCAGE ADMINISTRATIF ACTIF"

        if self.est_suspendu_totalement():
            return False, "ACCÈS AUX ARCHIVES REFUSÉ : Session suspendue par sanction majeure."
            
        if self.a_penalite_impayee():
            return False, f"ACCÈS AUX ARCHIVES BLOQUÉ : Veuillez régulariser votre solde de {self.get_dette_totale()} MAD."
        
        abonnement = self.get_abonnement_actif()
        if not abonnement:
            return False, "AUCUN SCEAU DE PRIVILÈGE ACTIF : Veuillez souscrire à un plan."
        
        # On compte les emprunts actifs ET les demandes en attente
        emprunts_actifs = self.emprunts.filter(statut__in=['demande', 'en_cours']).count()
        limite = abonnement.plan.limite_emprunts_physiques
        if emprunts_actifs >= limite:
            return False, f"CAPACITÉ MAXIMALE ATTEINTE : Votre plan {abonnement.plan.nom} est limité à {limite} ouvrages simultanés."
            
        return True, "ACCÈS AUTORISÉ"
    
    def peut_acceder_e_library(self):
        """Vérifie l'accès à la E-Library selon le plan actif (Point 8 du CDC)."""
        if self.debloque_par_admin or self.est_bibliothecaire():
            return True, "ACCÈS PRIVILÉGIÉ PERSONNEL"

        if self.est_suspendu_totalement():
            return False, "ACCÈS E-LIBRARY RÉVOQUÉ : Compte suspendu."
            
        if self.a_penalite_impayee():
            return False, "ACCÈS E-LIBRARY BLOQUÉ : Solde débiteur détecté."
        
        abonnement = self.get_abonnement_actif()
        if not abonnement:
            return False, "AUCUN SCEAU ACTIF : Souscription requise."
            
        if not abonnement.plan.acces_e_library:
            return False, f"PRIVILÈGE INSUFFISANT : Le plan {abonnement.plan.nom} ne couvre pas l'accès numérique. Passez au Premium."
        
        return True, "ACCÈS AUTORISÉ"


# ==============================================================================
# 2. CLASSE MÉTIER : PLAN D'ABONNEMENT (Standard / Premium)
# ==============================================================================
class PlanAbonnement(models.Model):
    """
    RÔLE : Définir les offres et les quotas (Point 8 du CDC).
    POURQUOI : Architecture flexible permettant de modifier les limites sans toucher au code.
    """
    nom = models.CharField(max_length=50, choices=[('Standard', 'Standard'), ('Premium', 'Premium')], unique=True)
    prix_mensuel = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    limite_emprunts_physiques = models.IntegerField(default=2, help_text="Nombre max de livres physiques simultanés")
    acces_e_library = models.BooleanField(default=True)
    prix_annuel = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    
    def __str__(self):
        return f"{self.nom} - {self.limite_emprunts_physiques} livres max"
    
    class Meta:
        verbose_name = "Plan d'abonnement"
        verbose_name_plural = "Plans d'abonnement"


# ==============================================================================
# 3. CLASSE MÉTIER : ABONNEMENT (Validité temporelle)
# ==============================================================================
class Abonnement(models.Model):
    """
    RÔLE : Gérer la durée d'accès d'un adhérent à un plan spécifique.
    LOGIQUE : Calcule automatiquement la date de fin à J+30 ou J+365 selon la durée choisie.
    """
    DUREE_CHOICES = (
        ('mensuel', 'Mensuel'),
        ('annuel', 'Annuel'),
    )
    
    adherent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='abonnements')
    plan = models.ForeignKey(PlanAbonnement, on_delete=models.SET_NULL, null=True)
    date_debut = models.DateTimeField(default=timezone.now)
    date_fin = models.DateTimeField()
    duree_choisie = models.CharField(max_length=10, choices=DUREE_CHOICES, default='mensuel')
    est_actif = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.adherent.username} - {self.plan.nom} ({self.get_duree_choisie_display()})"
    
    def save(self, *args, **kwargs):
        # Automatisation : Calcul de la date de fin selon la durée choisie
        if not self.date_fin:
            if self.duree_choisie == 'annuel':
                self.date_fin = self.date_debut + timedelta(days=365)
            else:
                self.date_fin = self.date_debut + timedelta(days=30)
        super().save(*args, **kwargs)
    
    def est_valide(self):
        return self.est_actif and self.date_fin > timezone.now()


# ==============================================================================
# 4. CLASSE MÉTIER : AUTEUR (Gestion des Écrivains)
# ==============================================================================
class Auteur(models.Model):
    """
    RÔLE : Centraliser les informations sur les auteurs.
    POURQUOI : Permet de modifier la biographie et la photo une seule fois pour tous les livres.
    """
    nom = models.CharField(max_length=100, unique=True)
    biographie = models.TextField(blank=True, null=True)
    photo = models.ImageField(upload_to='authors/', blank=True, null=True)
    
    def __str__(self):
        return self.nom

# ==============================================================================
# 5. CLASSE MÉTIER : LIVRE (Le Fonds Documentaire Hybride)
# ==============================================================================
class Livre(models.Model):
    """
    RÔLE : Gestion hybride (Physique + Digital) - Point 4 & 9 du CDC.
    POURQUOI : Centralise les métadonnées (ISBN) et les stocks pour le Smart Fill.
    """
    isbn = models.CharField(max_length=13, unique=True, blank=True, null=True)
    titre = models.CharField(max_length=200)
    auteur = models.CharField(max_length=100) # Ancien CharField
    auteur_fk = models.ForeignKey(Auteur, on_delete=models.SET_NULL, null=True, related_name='livres') # Nouveau FK
    
    editeur = models.CharField(max_length=100, blank=True, null=True)
    annee_publication = models.IntegerField(blank=True, null=True)
    resume = models.TextField(blank=True, null=True)
    
    # Informations sur l'auteur (Anciennes colonnes)
    auteur_biographie = models.TextField(blank=True, null=True)
    auteur_photo = models.ImageField(upload_to='authors/', blank=True, null=True)
    
    # Gestion de la version physique
    quantite_totale = models.IntegerField(default=0, help_text="Nombre total possédés")
    quantite_disponible = models.IntegerField(default=0, help_text="Disponibles en rayon")
    
    # Gestion de la version numérique (E-Library)
    a_version_numerique = models.BooleanField(default=False)
    fichier_pdf = models.FileField(upload_to='ebooks/', blank=True, null=True)
    
    couverture = models.ImageField(upload_to='covers/', blank=True, null=True)
    date_ajout = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.titre} - {self.auteur}"
    
    def get_note_moyenne(self):
        """Calcule la moyenne des avis (0 à 5)."""
        avis = self.avis.all()
        if not avis:
            return 0
        return round(sum(a.note for a in avis) / avis.count(), 1)

    def get_etoiles_moyenne(self):
        """Retourne un range pour l'affichage des étoiles en template."""
        return range(int(round(self.get_note_moyenne())))

    def est_disponible_physique(self):
        return self.quantite_disponible > 0
    
    # --- LOGIQUE DE STOCK ---
    def decrementer_stock(self):
        """Appelé lors de la création d'un emprunt."""
        if self.quantite_disponible > 0:
            self.quantite_disponible -= 1
            self.save()
            return True
        return False
    
    def incrementer_stock(self):
        """Appelé lors du retour d'un livre."""
        if self.quantite_disponible < self.quantite_totale:
            self.quantite_disponible += 1
            self.save()
            return True
        return False

    class Meta:
        indexes = [
            models.Index(fields=['isbn']),
            models.Index(fields=['titre']),
            models.Index(fields=['a_version_numerique']),
        ]


# ==============================================================================
# 6. CLASSE MÉTIER : AVIS (Interface Community)
# ==============================================================================
class Avis(models.Model):
    """
    RÔLE : Permettre aux membres de noter et commenter les ouvrages.
    """
    adherent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='avis')
    livre = models.ForeignKey(Livre, on_delete=models.CASCADE, related_name='avis')
    note = models.IntegerField(default=5, help_text="Note de 0 à 5 étoiles")
    commentaire = models.TextField()
    date_publication = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Avis"
        unique_together = ('adherent', 'livre') # Un seul avis par livre par personne

    def __str__(self):
        return f"Avis de {self.adherent.username} sur {self.livre.titre}"


# ==============================================================================
# 5. CLASSE MÉTIER : EMPRUNT (Le Cycle de Prêt Intelligent)
# ==============================================================================
class Emprunt(models.Model):
    """
    RÔLE : Gérer le flux des prêts physiques.
    LOGIQUE : Workflow de validation (Demande -> Validation -> Retour).
    S'aligne sur le Point 6 & 7 du Cahier des Charges.
    """
    STATUT_CHOICES = (
        ('demande', 'En attente de validation'),
        ('en_cours', 'Emprunt actif'),
        ('rendu', 'Livre retourné'),
        ('refuse', 'Demande refusée'),
    )
    
    adherent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='emprunts')
    livre = models.ForeignKey(Livre, on_delete=models.CASCADE, related_name='emprunts')
    date_emprunt = models.DateTimeField(default=timezone.now)
    date_retour_prevue = models.DateTimeField(blank=True, null=True)
    date_retour_reelle = models.DateTimeField(blank=True, null=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='demande')
    est_retourne = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['statut']),
            models.Index(fields=['date_emprunt']),
            models.Index(fields=['est_retourne']),
        ]
    
    def __str__(self):
        return f"{self.adherent.username} - {self.livre.titre} ({self.get_statut_display()})"
    
    def save(self, *args, **kwargs):
        # Règle J+15 : Calculée uniquement lors de la validation du prêt
        if self.statut == 'en_cours' and not self.date_retour_prevue:
            self.date_retour_prevue = timezone.now() + timedelta(days=15)
        super().save(*args, **kwargs)
    
    def approuver(self):
        """Action du Bibliothécaire : Valide le prêt immédiatement."""
        if self.statut == 'demande':
            self.statut = 'en_cours'
            self.est_retourne = False
            self.date_emprunt = timezone.now()
            self.date_retour_prevue = self.date_emprunt + timedelta(days=15)
            # On décrémente seulement si le stock n'est pas déjà à 0
            if self.livre.quantite_disponible > 0:
                self.livre.quantite_disponible -= 1
                self.livre.save()
            self.save()
            return True, "Emprunt validé."
        return False, "Déjà validé ou invalide."

    def refuser(self):
        """
        REFUSER une demande d'emprunt (Bibliothécaire/Admin)
        🔧 CORRECTION : Méthode ajoutée pour résoudre l'AttributeError
        """
        if self.statut == 'demande':
            self.statut = 'refuse'
            self.save()
            return True
        return False

    def peut_etre_approuve(self):
        """Vérifie si la demande peut être approuvée (stock disponible)"""
        return self.livre.quantite_disponible > 0

    def est_en_retard(self):
        if self.statut != 'en_cours' or self.est_retourne:
            return False
        return self.date_retour_prevue and timezone.now() > self.date_retour_prevue

    def calculer_penalite(self):
        """Calcul de la pénalité : 3 MAD par jour de retard."""
        import math
        target_date = self.date_retour_reelle if self.est_retourne else timezone.now()
        if not self.date_retour_prevue or target_date <= self.date_retour_prevue:
            return 0
        diff = target_date - self.date_retour_prevue
        if diff.total_seconds() < 600: return 0
        jours_retard = math.ceil(diff.total_seconds() / 86400)
        return max(0, jours_retard * 3)

    def retourner_livre(self):
        """Action du Bibliothécaire : Clôture le prêt et rend le livre au stock."""
        if self.statut == 'en_cours':
            self.statut = 'rendu'
            self.est_retourne = True
            self.date_retour_reelle = timezone.now()
            
            # Réintégration physique au catalogue
            self.livre.quantite_disponible += 1
            self.livre.save()
            
            # Génération de pénalité si retard
            montant = self.calculer_penalite()
            if montant > 0:
                Penalite.objects.create(adherent=self.adherent, emprunt=self, montant=montant)
            
            self.save()
            return True, "Livre rendu et stock mis à jour."
        return False, "Erreur : Ce livre n'est pas marqué comme 'En cours'."


# ==============================================================================
# 6. CLASSE MÉTIER : PÉNALITÉ (Sanctions et Régularisation)
# ==============================================================================
class Penalite(models.Model):
    """
    RÔLE : Tracer les dettes des adhérents.
    POURQUOI : Sert de levier pour garantir le respect des délais de prêt.
    """
    adherent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='penalites')
    emprunt = models.ForeignKey(Emprunt, on_delete=models.CASCADE, related_name='penalites', blank=True, null=True)
    montant = models.DecimalField(max_digits=6, decimal_places=2)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_paiement = models.DateTimeField(blank=True, null=True)
    est_reglee = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.adherent.username} - {self.montant} MAD ({'Réglée' if self.est_reglee else 'Impayée'})"
    
    def regler(self):
        """Marque la dette comme payée."""
        self.est_reglee = True
        self.date_paiement = timezone.now()
        self.save()


# ==============================================================================
# 7. CLASSE MÉTIER : CONSULTATION (E-Library)
# ==============================================================================
class ConsultationNumerique(models.Model):
    """RÔLE : Tracer l'activité de lecture numérique pour les statistiques."""
    adherent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consultations')
    livre = models.ForeignKey(Livre, on_delete=models.CASCADE, related_name='consultations')
    date_consultation = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.adherent.username} a lu {self.livre.titre} le {self.date_consultation}"

# ==============================================================================
# 8. CLASSE MÉTIER : NOTIFICATION (Communication Adhérent)
# ==============================================================================
class Notification(models.Model):
    """
    RÔLE : Envoyer des alertes et messages aux adhérents (Retards, Validations).
    """
    TYPES = (
        ('retard', 'Alerte Retard'),
        ('info', 'Information'),
        ('succes', 'Validation'),
    )
    adherent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    emprunt = models.ForeignKey(Emprunt, on_delete=models.CASCADE, related_name='notifications', blank=True, null=True)
    titre = models.CharField(max_length=100)
    message = models.TextField()
    type = models.CharField(max_length=20, choices=TYPES, default='info')
    date_creation = models.DateTimeField(auto_now_add=True)
    est_lu = models.BooleanField(default=False)

    def __str__(self):
        return f"Notif for {self.adherent.username} : {self.titre}"

    class Meta:
        ordering = ['-date_creation']