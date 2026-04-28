from django.contrib import admin
from .models import User, PlanAbonnement, Abonnement, Livre, Emprunt, Penalite, ConsultationNumerique


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'email', 'role', 'telephone', 'a_penalite_impayee')
    list_filter = ('role', 'is_active')
    search_fields = ('username', 'email', 'telephone')
    list_editable = ('role',)
    fieldsets = (
        ('Informations personnelles', {'fields': ('username', 'email', 'telephone', 'adresse')}),
        ('Rôle et permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser')}),
        ('Dates', {'fields': ('last_login', 'date_joined')}),
    )


@admin.register(PlanAbonnement)
class PlanAbonnementAdmin(admin.ModelAdmin):
    list_display = ('nom', 'limite_emprunts_physiques', 'acces_e_library', 'prix_mensuel', 'prix_annuel')
    list_editable = ('prix_mensuel', 'prix_annuel')


@admin.register(Abonnement)
class AbonnementAdmin(admin.ModelAdmin):
    list_display = ('adherent', 'plan', 'date_debut', 'date_fin', 'est_actif')
    list_filter = ('est_actif', 'plan')
    search_fields = ('adherent__username',)
    raw_id_fields = ('adherent',)


@admin.register(Livre)
class LivreAdmin(admin.ModelAdmin):
    list_display = ('titre', 'auteur', 'isbn', 'quantite_disponible', 'quantite_totale', 'a_version_numerique')
    list_filter = ('a_version_numerique', 'annee_publication')
    search_fields = ('titre', 'auteur', 'isbn')
    list_editable = ('quantite_totale', 'quantite_disponible')


@admin.register(Emprunt)
class EmpruntAdmin(admin.ModelAdmin):
    list_display = ('id', 'adherent', 'livre', 'date_emprunt', 'date_retour_prevue', 'est_retourne', 'est_en_retard')
    list_filter = ('est_retourne',)
    search_fields = ('adherent__username', 'livre__titre')
    raw_id_fields = ('adherent', 'livre')
    
    def est_en_retard(self, obj):
        return obj.est_en_retard()
    est_en_retard.boolean = True
    est_en_retard.short_description = 'En retard ?'


@admin.register(Penalite)
class PenaliteAdmin(admin.ModelAdmin):
    list_display = ('adherent', 'montant', 'est_reglee', 'date_creation', 'date_paiement')
    list_filter = ('est_reglee',)
    search_fields = ('adherent__username',)
    list_editable = ('est_reglee',)


@admin.register(ConsultationNumerique)
class ConsultationNumeriqueAdmin(admin.ModelAdmin):
    list_display = ('adherent', 'livre', 'date_consultation')
    list_filter = ('date_consultation',)
    search_fields = ('adherent__username', 'livre__titre')