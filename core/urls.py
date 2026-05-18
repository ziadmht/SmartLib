from django.urls import path
from . import views

urlpatterns = [
    # --- 1. PORTAIL D'ACCÈS & SESSION ---
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('transition/', views.transition_view, name='transition'),
    path('', views.dashboard, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    
    # --- 2. GESTION DES ARCHIVES (CATALOGUE) ---
    path('livres/', views.livre_liste, name='livre_liste'),
    path('livres/ajouter/', views.livre_ajouter, name='livre_ajouter'),
    path('livres/<int:pk>/', views.livre_detail, name='livre_detail'),
    path('livres/<int:pk>/modifier/', views.livre_modifier, name='livre_modifier'),
    path('livres/<int:pk>/supprimer/', views.livre_supprimer, name='livre_supprimer'),
    path('livres/<int:livre_id>/avis/', views.donner_avis, name='donner_avis'),
    path('api/isbn/<str:isbn>/', views.api_isbn_lookup, name='api_isbn_lookup'),

    # --- 2b. GESTION DES AUTEURS ---
    path('auteurs/', views.auteur_liste, name='auteur_liste'),
    path('auteurs/<int:pk>/modifier/', views.auteur_modifier, name='auteur_modifier'),

    # --- 3. E-LIBRARY (J9) ---
    path('e-library/', views.e_library, name='e_library'),
    path('e-library/lire/<int:livre_id>/', views.lire_livre_numerique, name='lire_livre_numerique'),
    path('e-library/telecharger/<int:livre_id>/', views.telecharger_livre_numerique, name='telecharger_livre_numerique'),

    # --- 3. FLUX DES PRÊTS (LOGISTIQUE) ---
    path('emprunts/', views.emprunt_liste, name='emprunt_liste'),
    path('emprunts/manuel/', views.emprunt_manuel, name='emprunt_manuel'),
    path('emprunts/ajouter/<int:livre_id>/', views.emprunt_ajouter, name='emprunt_ajouter'),
    path('emprunts/approuver/<int:emprunt_id>/', views.emprunt_approuver, name='emprunt_approuver'),
    path('emprunts/refuser/<int:emprunt_id>/', views.emprunt_refuser, name='emprunt_refuser'),
    path('emprunts/retour/<int:emprunt_id>/', views.emprunt_retour, name='emprunt_retour'),
    path('emprunts/simuler-retard/<int:emprunt_id>/', views.simuler_retard, name='simuler_retard'),
    
    # --- 4. HUB ADHÉRENT & MONITORING ---
    path('mon-activite/', views.mon_activite, name='mon_activite'),
    path('mes-emprunts/', views.mes_emprunts, name='mes_emprunts'),
    path('mes-penalites/', views.mes_penalites, name='mes_penalites'),
    path('penalites/payer-tout/', views.payer_penalites, name='payer_penalites'),
    path('penalites/<int:pk>/payer/', views.penalite_payer, name='penalite_payer'),
    path('penalites/regulariser/<int:emprunt_id>/', views.payer_dette_en_cours, name='payer_dette_en_cours'),
    
    # --- 4b. GRÂCE ADMINISTRATIVE ---
    path('sanctions/admin/grace/<int:user_id>/', views.admin_grace, name='admin_grace'),
    path('sanctions/admin/revoquer-grace/<int:user_id>/', views.admin_revoquer_grace, name='admin_revoquer_grace'),
    
    # --- 5. UNITÉ NUMÉRIQUE (E-LIBRARY) ---
    # --- 6. PÔLE ÉCONOMIQUE & ABONNEMENTS (UNIFIÉ) ---
    path('abonnements/souscrire/', views.souscrire_abonnement, name='souscrire_abonnement'),
    path('abonnements/mes-abonnements/', views.mes_abonnements, name='mes_abonnements'),
    path('abonnements/gestion-admin/', views.admin_abonnements, name='admin_abonnements'),

    path('abonnements/annuler/', views.annuler_abonnement, name='annuler_abonnement'),
    path('abonnements/renouveler/<int:abonnement_id>/', views.renouveler_abonnement, name='renouveler_abonnement'),
    
    # --- 7. ADMINISTRATION SYSTÈME ---
    path('utilisateurs/', views.utilisateur_liste, name='utilisateur_liste'),
    path('utilisateurs/ajouter/', views.utilisateur_ajouter, name='utilisateur_ajouter'),
    path('utilisateurs/<int:pk>/role/', views.utilisateur_changer_role, name='utilisateur_changer_role'),
    path('utilisateurs/<int:pk>/gracier/', views.utilisateur_gracier, name='utilisateur_gracier'),
    path('utilisateurs/<int:pk>/assigner-plan/', views.admin_assigner_abonnement, name='admin_assigner_abonnement'),

    # --- 8. STATISTIQUES ET GRAPHIQUES (J11) ---
    path('statistiques/', views.statistiques, name='statistiques'),
    path('api/stats/emprunts-mensuels/', views.api_emprunts_mensuels, name='api_emprunts_mensuels'),
    path('api/stats/top-livres/', views.api_top_livres, name='api_top_livres'),

    # --- 9. NOTIFICATIONS ET AUTOMATISATION ---
    path('notifications/scan-retards/', views.scan_retards, name='scan_retards'),
    path('notifications/<int:pk>/lire/', views.marquer_notif_lue, name='marquer_notif_lue'),
]
