from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.http import JsonResponse
from .models import User, Livre, Emprunt, Penalite, Abonnement, PlanAbonnement
from .utils import get_book_metadata_by_isbn, download_image_from_url, admin_required, bibliothecaire_required


# ============================================================
# 1. AUTHENTIFICATION (Login / Logout)
# ============================================================

def login_view(request):
    """Gère la connexion sécurisée des utilisateurs"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Ravi de vous revoir, {user.username} !')
            return redirect('dashboard')
        else:
            messages.error(request, 'Identifiants invalides. Veuillez réessayer.')
    
    return render(request, 'core/login.html')


def logout_view(request):
    """Déconnecte l'utilisateur et nettoie la session"""
    logout(request)
    messages.info(request, 'Vous avez été déconnecté avec succès.')
    return redirect('login')


# ============================================================
# 2. DASHBOARD (Point d'entrée selon le rôle)
# ============================================================

@login_required
def dashboard(request):
    """
    Affiche les KPIs selon le rôle. 
    Personnel -> Global | Adhérent -> Personnel.
    """
    user = request.user
    context = {'today': timezone.now()}
    
    if user.est_bibliothecaire():
        # Statistiques Globales pour le Personnel
        context.update({
            'total_livres': Livre.objects.count(),
            'emprunts_actifs': Emprunt.objects.filter(statut='en_cours').count(),
            'total_adherents': User.objects.filter(role='adherent').count(),
            'penalites_impayees': Penalite.objects.filter(est_reglee=False).count(),
            'retards_critiques': Emprunt.objects.filter(statut='en_cours', date_retour_prevue__lt=timezone.now()).count(),
            'demandes_en_attente': Emprunt.objects.filter(statut='demande').count(),
            # Nouveaux KPIs "Haute Qualité"
            'recettes_totales': Penalite.objects.filter(est_reglee=True).aggregate(Sum('montant'))['montant__sum'] or 0,
            'stock_critique': Livre.objects.filter(quantite_disponible__lte=1).count(),
            'derniers_emprunts': Emprunt.objects.select_related('adherent', 'livre').order_by('-date_emprunt')[:5],
        })
    else:
        # Statistiques Personnelles pour l'Adhérent
        mes_emprunts = Emprunt.objects.filter(adherent=user, statut__in=['demande', 'en_cours'])
        abonnement = user.get_abonnement_actif()
        
        context.update({
            'nb_mes_livres': mes_emprunts.filter(statut='en_cours').count(),
            'ma_dette': user.get_dette_totale(),
            'jours_abonnement': (abonnement.date_fin - timezone.now()).days if abonnement else 0,
            'statut_compte': user.peut_emprunter()[0],
            'message_statut': user.peut_emprunter()[1],
            'mes_demandes': mes_emprunts.filter(statut='demande').count(),
        })
    
    return render(request, 'core/dashboard.html', context)


# ============================================================
# 3. GESTION DU PROFIL
# ============================================================

@login_required
def profile_view(request):
    """Permet à l'utilisateur de mettre à jour ses infos et sa photo"""
    if request.method == 'POST':
        user = request.user
        user.email = request.POST.get('email')
        user.telephone = request.POST.get('telephone')
        user.adresse = request.POST.get('adresse')
        
        if request.FILES.get('photo_profil'):
            user.photo_profil = request.FILES.get('photo_profil')
            
        user.save()
        messages.success(request, 'Votre profil a été mis à jour.')
        return redirect('profile')
    
    abonnement = request.user.get_abonnement_actif()
    penalites_impayees = Penalite.objects.filter(adherent=request.user, est_reglee=False)
    
    context = {
        'abonnement': abonnement,
        'penalites_impayees': penalites_impayees,
    }
    
    return render(request, 'core/profile.html', context)


# ============================================================
# 4. CATALOGUE LIVRES (J4)
# ============================================================

@login_required
def livre_liste(request):
    """
    Affiche la liste de tous les livres avec recherche.
    """
    livres = Livre.objects.all().order_by('-date_ajout')
    
    search_query = request.GET.get('q', '')
    if search_query:
        livres = livres.filter(
            Q(titre__icontains=search_query) |
            Q(auteur__icontains=search_query) |
            Q(isbn__icontains=search_query)
        )
    
    context = {
        'livres': livres,
        'search_query': search_query,
    }
    return render(request, 'core/livre_liste.html', context)


@login_required
def livre_detail(request, pk):
    """
    Affiche les détails d'un livre spécifique avec biographie de l'auteur.
    """
    livre = get_object_or_404(Livre, pk=pk)
    
    # Vérifier si l'utilisateur peut emprunter (pour afficher le bouton)
    peut_emprunter, message_emprunt = request.user.peut_emprunter()
    
    context = {
        'livre': livre,
        'peut_emprunter': peut_emprunter,
        'message_emprunt': message_emprunt,
    }
    return render(request, 'core/livre_detail.html', context)


@login_required
@bibliothecaire_required
def livre_ajouter(request):
    """
    Ajouter un nouveau livre (Admin ou Bibliothécaire uniquement)
    """
    if request.method == 'POST':
        titre = request.POST.get('titre')
        auteur = request.POST.get('auteur')
        isbn = request.POST.get('isbn')
        editeur = request.POST.get('editeur')
        annee_publication = request.POST.get('annee_publication')
        resume = request.POST.get('resume')
        auteur_biographie = request.POST.get('auteur_biographie')
        quantite_totale = request.POST.get('quantite_totale', 0)
        a_version_numerique = request.POST.get('a_version_numerique') == 'on'
        
        fichier_pdf = request.FILES.get('fichier_pdf')
        couverture = request.FILES.get('couverture')
        auteur_photo = request.FILES.get('auteur_photo')
        
        livre = Livre.objects.create(
            titre=titre,
            auteur=auteur,
            isbn=isbn if isbn else None,
            editeur=editeur,
            annee_publication=annee_publication if annee_publication else None,
            resume=resume,
            auteur_biographie=auteur_biographie,
            quantite_totale=int(quantite_totale),
            quantite_disponible=int(quantite_totale),
            a_version_numerique=a_version_numerique,
            fichier_pdf=fichier_pdf,
            couverture=couverture,
            auteur_photo=auteur_photo,
        )
        
        messages.success(request, f'Le livre "{titre}" a été ajouté avec succès !')
        return redirect('livre_detail', pk=livre.pk)
    
    return render(request, 'core/livre_form.html', {'mode': 'ajouter'})


@login_required
@bibliothecaire_required
def livre_modifier(request, pk):
    """
    Modifier un livre existant (Admin ou Bibliothécaire uniquement)
    """
    livre = get_object_or_404(Livre, pk=pk)
    
    if request.method == 'POST':
        livre.titre = request.POST.get('titre')
        livre.auteur = request.POST.get('auteur')
        livre.isbn = request.POST.get('isbn') or None
        livre.editeur = request.POST.get('editeur')
        livre.annee_publication = request.POST.get('annee_publication') or None
        livre.resume = request.POST.get('resume')
        livre.auteur_biographie = request.POST.get('auteur_biographie')
        
        # Gestion intelligente des quantités
        ancienne_totale = livre.quantite_totale
        nouvelle_totale = int(request.POST.get('quantite_totale', 0))
        diff = nouvelle_totale - ancienne_totale
        
        livre.quantite_totale = nouvelle_totale
        livre.quantite_disponible += diff
        
        livre.a_version_numerique = request.POST.get('a_version_numerique') == 'on'
        
        if request.FILES.get('fichier_pdf'):
            livre.fichier_pdf = request.FILES.get('fichier_pdf')
        if request.FILES.get('couverture'):
            livre.couverture = request.FILES.get('couverture')
        if request.FILES.get('auteur_photo'):
            livre.auteur_photo = request.FILES.get('auteur_photo')
            
        livre.save()
        
        messages.success(request, f'Le livre "{livre.titre}" a été modifié avec succès !')
        return redirect('livre_detail', pk=livre.pk)
    
    context = {
        'livre': livre,
        'mode': 'modifier',
    }
    return render(request, 'core/livre_form.html', context)


@login_required
@admin_required
def livre_supprimer(request, pk):
    """
    Supprimer un livre (Admin uniquement)
    """
    livre = get_object_or_404(Livre, pk=pk)
    
    if request.method == 'POST':
        titre = livre.titre
        livre.delete()
        messages.success(request, f'Le livre "{titre}" a été supprimé avec succès !')
        return redirect('livre_liste')
    
    return render(request, 'core/livre_confirm_delete.html', {'livre': livre})


# ============================================================
# API SMART FILL (J5)
# ============================================================

@login_required
@bibliothecaire_required
def api_isbn_lookup(request, isbn):
    """
    API endpoint pour rechercher un livre par ISBN.
    Retourne les métadonnées au format JSON.
    Utilisé par AJAX dans le formulaire d'ajout.
    """
    # Récupérer les métadonnées
    metadata = get_book_metadata_by_isbn(isbn)
    
    if metadata is None:
        return JsonResponse({'error': 'Aucun livre trouvé pour cet ISBN'}, status=404)
    
    return JsonResponse(metadata)


# ============================================================
# 5. GESTION DES EMPRUNTS (J6)
# ============================================================

from django.utils import timezone
from datetime import timedelta

@login_required
def emprunt_ajouter(request, livre_id):
    """
    Permet à un adhérent de DEMANDER l'emprunt d'un livre.
    L'emprunt restera en attente jusqu'à validation par le bibliothécaire.
    """
    if not request.user.est_adherent():
        messages.error(request, "Seuls les adhérents peuvent demander des livres.")
        return redirect('livre_detail', pk=livre_id)
    
    livre = get_object_or_404(Livre, pk=livre_id)
    
    # Vérification 1 : L'utilisateur peut-il emprunter ?
    peut_emprunter, message = request.user.peut_emprunter()
    if not peut_emprunter:
        messages.error(request, message)
        return redirect('livre_detail', pk=livre_id)
    
    # Vérification 2 : Le livre est-il disponible physiquement ?
    if not livre.est_disponible_physique():
        messages.error(request, "Ce livre n'est pas disponible actuellement.")
        return redirect('livre_detail', pk=livre_id)
    
    # Vérification 3 : L'utilisateur a-t-il déjà une demande ou un emprunt en cours pour ce livre ?
    deja_demande = Emprunt.objects.filter(
        adherent=request.user,
        livre=livre,
        statut__in=['demande', 'en_cours']
    ).exists()
    if deja_demande:
        messages.error(request, "Vous avez déjà une demande ou un emprunt actif pour ce livre.")
        return redirect('livre_detail', pk=livre_id)
    
    # Créer la DEMANDE d'emprunt
    Emprunt.objects.create(
        adherent=request.user,
        livre=livre,
        statut='demande'
    )
    
    messages.success(
        request, 
        f'Votre demande pour "{livre.titre}" a été envoyée. '
        f'Veuillez vous présenter à la bibliothèque pour récupérer l\'ouvrage.'
    )
    
    return redirect('mes_emprunts')


@login_required
@bibliothecaire_required
def emprunt_approuver(request, emprunt_id):
    """
    Le bibliothécaire approuve la demande quand l'adhérent récupère le livre.
    """
    emprunt = get_object_or_404(Emprunt, pk=emprunt_id)
    success, message = emprunt.approuver()
    
    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)
        
    return redirect('emprunt_liste')


@login_required
@bibliothecaire_required
def emprunt_refuser(request, emprunt_id):
    """
    Le bibliothécaire refuse la demande.
    """
    emprunt = get_object_or_404(Emprunt, pk=emprunt_id)
    if emprunt.refuser():
        messages.warning(request, f"La demande de {emprunt.adherent.username} a été refusée.")
    else:
        messages.error(request, "Impossible de refuser cette demande.")
        
    return redirect('emprunt_liste')


@login_required
@bibliothecaire_required
def emprunt_retour(request, emprunt_id):
    """
    Permet au bibliothécaire ou à l'admin d'enregistrer le retour d'un livre.
    """
    emprunt = get_object_or_404(Emprunt.objects.select_related('adherent', 'livre'), pk=emprunt_id)
    
    if emprunt.statut == 'rendu':
        messages.warning(request, "Ce livre a déjà été retourné.")
        return redirect('emprunt_liste')
    
    success, message = emprunt.retourner_livre()
    
    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)
    
    return redirect('emprunt_liste')


@login_required
@bibliothecaire_required
def emprunt_liste(request):
    """
    Liste toutes les demandes et emprunts en cours (pour bibliothécaires et admin)
    """
    demandes = Emprunt.objects.filter(statut='demande').select_related('adherent', 'livre').order_by('date_emprunt')
    
    emprunts_actifs = Emprunt.objects.filter(
        statut='en_cours'
    ).select_related('adherent', 'livre').order_by('date_retour_prevue')
    
    emprunts_historique = Emprunt.objects.filter(
        statut__in=['rendu', 'refuse']
    ).select_related('adherent', 'livre').order_by('-date_retour_reelle', '-id')[:50]
    
    context = {
        'demandes': demandes,
        'emprunts_actifs': emprunts_actifs,
        'emprunts_historique': emprunts_historique,
        'aujourdhui': timezone.now(),
    }
    return render(request, 'core/emprunt_liste.html', context)


@login_required
def mes_emprunts(request):
    """
    Hub de l'Adhérent : Centralise réservations, prêts en cours et historique.
    Inclut le calcul dynamique des jours restants pour la maniabilité.
    """
    aujourdhui = timezone.now()
    
    # 1. Réservations en attente
    demandes = Emprunt.objects.filter(adherent=request.user, statut='demande').select_related('livre')
    
    # 2. Prêts actifs avec calcul du temps restant
    emprunts_actifs = Emprunt.objects.filter(
        adherent=request.user,
        statut='en_cours'
    ).select_related('livre').order_by('date_retour_prevue')
    
    for e in emprunts_actifs:
        # Calculer jours restants
        if e.date_retour_prevue:
            delta = e.date_retour_prevue - aujourdhui
            e.jours_restants = delta.days
            e.retard = delta.days < 0
        else:
            e.jours_restants = 0
            e.retard = False

    # 3. Historique
    emprunts_historique = Emprunt.objects.filter(
        adherent=request.user,
        statut__in=['rendu', 'refuse']
    ).select_related('livre').order_by('-date_retour_reelle')
    
    # 4. Pénalités impayées (pour le résumé en haut de page)
    penalites = Penalite.objects.filter(adherent=request.user, est_reglee=False)
    total_dette = request.user.get_dette_totale()

    context = {
        'demandes': demandes,
        'emprunts_actifs': emprunts_actifs,
        'emprunts_historique': emprunts_historique,
        'penalites': penalites,
        'total_dette': total_dette,
        'aujourdhui': aujourdhui,
    }
    return render(request, 'core/mes_emprunts.html', context)


@login_required
def mes_penalites(request):
    """
    Bureau des Sanctions : Affiche les dettes réelles (enregistrées) 
    ET les dettes latentes (livres en retard non encore rendus).
    """
    aujourdhui = timezone.now()
    
    # 1. Dettes impayées (Pénalités enregistrées après retour)
    penalites_impayees = Penalite.objects.filter(adherent=request.user, est_reglee=False).order_by('-date_creation')
    
    # 2. Dettes latentes (Livres en retard que l'adhérent a encore en main)
    # On calcule cela pour l'affichage transparent
    retards_en_cours = []
    emprunts_actifs = Emprunt.objects.filter(adherent=request.user, statut='en_cours')
    for e in emprunts_actifs:
        montant = e.calculer_penalite()
        if montant > 0:
            e.montant_latente = montant
            retards_en_cours.append(e)
    
    # 3. Historique des paiements
    historique_paiements = Penalite.objects.filter(adherent=request.user, est_reglee=True).order_by('-date_paiement')
    
    context = {
        'penalites_impayees': penalites_impayees,
        'retards_en_cours': retards_en_cours,
        'historique_paiements': historique_paiements,
        'total_impaye': request.user.get_dette_totale(),
    }
    return render(request, 'core/mes_penalites.html', context)


@login_required
@bibliothecaire_required
def emprunt_manuel(request):
    """
    Espace dédié au bibliothécaire pour enregistrer un prêt direct (comptoir).
    Le prêt est actif immédiatement sans passer par le statut 'demande'.
    """
    if request.method == 'POST':
        adherent_id = request.POST.get('adherent')
        livre_id = request.POST.get('livre')
        
        adherent = get_object_or_404(User, pk=adherent_id)
        livre = get_object_or_404(Livre, pk=livre_id)
        
        # 1. Vérifications de base (Pénalités, Quotas)
        peut_emprunter, message = adherent.peut_emprunter()
        if not peut_emprunter:
            messages.error(request, f"ERREUR : {message}")
            return redirect('emprunt_manuel')
            
        # 2. Vérification Stock
        if not livre.est_disponible_physique():
            messages.error(request, "ERREUR : Cet ouvrage n'est pas disponible en stock.")
            return redirect('emprunt_manuel')
            
        # 3. Création DIRECTE du prêt actif
        emprunt = Emprunt.objects.create(
            adherent=adherent, 
            livre=livre,
            statut='en_cours',
            date_emprunt=timezone.now()
        )
        
        # 4. Mise à jour immédiate du stock
        livre.decrementer_stock()
        
        messages.success(request, f"PRÊT ENREGISTRÉ : '{livre.titre}' confié à {adherent.username}. Retour prévu le {emprunt.date_retour_prevue.strftime('%d/%m/%Y')}.")
        return redirect('emprunt_liste')

    adherents = User.objects.filter(role='adherent')
    livres = Livre.objects.filter(quantite_disponible__gt=0)
    
    return render(request, 'core/emprunt_form.html', {
        'adherents': adherents,
        'livres': livres,
        'aujourdhui': timezone.now()
    })

@login_required
def penalite_payer(request, pk):
    """Payer une amende déjà enregistrée (ex: les 50 MAD)."""
    penalite = get_object_or_404(Penalite, pk=pk)
    if request.user == penalite.adherent or request.user.est_bibliothecaire():
        penalite.regler()
        messages.success(request, f"Paiement de {penalite.montant} MAD validé. Vous êtes en règle.")
    else:
        messages.error(request, "Action non autorisée.")
    return redirect('mes_penalites')


@login_required
def payer_dette_en_cours(request, emprunt_id):
    """Payer le retard d'un livre que j'ai encore en main pour me débloquer."""
    emprunt = get_object_or_404(Emprunt, pk=emprunt_id, adherent=request.user)
    montant = emprunt.calculer_penalite()
    
    if montant > 0:
        # On crée la pénalité et on la marque payée direct
        Penalite.objects.create(
            adherent=request.user,
            emprunt=emprunt,
            montant=montant,
            est_reglee=True,
            date_paiement=timezone.now()
        )
        # TRÊVE : On repousse l'échéance à demain pour que le solde affiche 0 MAD
        emprunt.date_retour_prevue = timezone.now() + timedelta(days=1)
        emprunt.save()
        messages.success(request, f"Régularisation de {montant} MAD effectuée. Trêve accordée jusqu'à demain !")
    return redirect('mes_penalites')


@login_required
@bibliothecaire_required
def simuler_retard(request, emprunt_id):
    """
    OUTIL DE DÉMO : Force un retard massif sur un prêt.
    """
    emprunt = get_object_or_404(Emprunt, pk=emprunt_id)
    
    # On recule la date d'emprunt de 30 jours (Retard de 15 jours garanti)
    emprunt.date_emprunt = timezone.now() - timedelta(days=30)
    emprunt.date_retour_prevue = emprunt.date_emprunt + timedelta(days=15)
    emprunt.statut = 'en_cours'
    emprunt.est_retourne = False
    emprunt.save()
    
    messages.warning(request, f"🚀 SIMULATION : {emprunt.adherent.username} est maintenant en retard de 15 jours.")
    return redirect('emprunt_liste')


@login_required
def e_library(request):
    """E-Library : Accès aux ressources numériques (Point 9)"""
    peut_acceder, message = request.user.peut_acceder_e_library()
    if not peut_acceder:
        messages.warning(request, message)
        return redirect('dashboard')
    
    livres_numeriques = Livre.objects.filter(a_version_numerique=True)
    return render(request, 'core/e_library.html', {'livres': livres_numeriques})


@login_required
@admin_required
def utilisateur_liste(request):
    """
    Gestionnaire de Membres - EXCLUSIF ADMIN.
    Permet de piloter les rôles et de gracier les membres bloqués.
    """
    utilisateurs = User.objects.all().annotate(
        nb_emprunts=Count('emprunts', filter=Q(emprunts__statut='en_cours')),
        dette=Sum('penalites__montant', filter=Q(penalites__est_reglee=False))
    ).order_by('-date_joined')
    
    search_query = request.GET.get('q', '')
    if search_query:
        utilisateurs = utilisateurs.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query)
        )
        
    context = {
        'utilisateurs': utilisateurs,
        'search_query': search_query,
    }
    return render(request, 'core/utilisateur_liste.html', context)

@login_required
@admin_required
def utilisateur_changer_role(request, pk):
    """Changer le rôle d'un utilisateur (Admin seulement)"""
    target_user = get_object_or_404(User, pk=pk)
    nouveau_role = request.POST.get('role')
    
    if nouveau_role in ['adherent', 'bibliothecaire', 'admin']:
        target_user.role = nouveau_role
        target_user.save()
        messages.success(request, f"Le rôle de {target_user.username} est maintenant : {target_user.get_role_display()}")
    
    return redirect('utilisateur_liste')

@login_required
@admin_required
def utilisateur_gracier(request, pk):
    """Accorder un déblocage administratif (Grâce présidentielle)"""
    target_user = get_object_or_404(User, pk=pk)
    target_user.debloque_par_admin = not target_user.debloque_par_admin
    target_user.save()
    
    etat = "débloqué" if target_user.debloque_par_admin else "soumis aux règles auto"
    messages.info(request, f"Le compte de {target_user.username} est désormais {etat}.")
    
    return redirect('utilisateur_liste')


@login_required
def mon_activite(request):
    """
    Page de Suivi Haute Qualité : 
    Affiche les livres en validation et les livres empruntés avec timing précis.
    """
    aujourdhui = timezone.now()
    
    # 1. Livres en cours de validation (Demandes)
    en_validation = Emprunt.objects.filter(
        adherent=request.user, 
        statut='demande'
    ).select_related('livre').order_by('-date_emprunt')
    
    # 2. Livres empruntés (Actifs)
    emprunts_actifs = Emprunt.objects.filter(
        adherent=request.user, 
        statut='en_cours'
    ).select_related('livre').order_by('date_retour_prevue')
    
    # Enrichir les emprunts avec les pénalités spécifiques
    for e in emprunts_actifs:
        e.timestamp_echeance = e.date_retour_prevue.isoformat()
        e.penalite_actuelle = e.calculer_penalite()
        # Calculer le nombre de jours exact pour la transparence
        if e.est_en_retard():
            diff = timezone.now() - e.date_retour_prevue
            import math
            e.nb_jours_retard = math.ceil(diff.total_seconds() / 86400)
        else:
            e.nb_jours_retard = 0
        
    context = {
        'en_validation': en_validation,
        'emprunts_actifs': emprunts_actifs,
        'aujourdhui': aujourdhui,
    }
    return render(request, 'core/mon_activite.html', context)

# ============================================================
# 6. GESTION DES ABONNEMENTS (J8)
# ============================================================

@login_required
def souscrire_abonnement(request):
    """
    Permet à un adhérent de souscrire un abonnement (Standard ou Premium).
    Prestige UI & Simulation de paiement.
    """
    if not request.user.est_adherent():
        messages.error(request, "Accès restreint aux adhérents.")
        return redirect('dashboard')
    
    plans = PlanAbonnement.objects.all().order_by('prix_mensuel')
    abonnement_actif = request.user.get_abonnement_actif()
    
    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        duree = request.POST.get('duree', 'mensuel')
        
        plan = get_object_or_404(PlanAbonnement, pk=plan_id)
        
        # Calcul de la date de fin
        if duree == 'annuel':
            prix = plan.prix_annuel
            date_fin = timezone.now() + timedelta(days=365)
        else:
            prix = plan.prix_mensuel
            date_fin = timezone.now() + timedelta(days=30)
        
        # On archive l'ancien abonnement
        if abonnement_actif:
            abonnement_actif.est_actif = False
            abonnement_actif.save()
        
        # On crée le nouveau sceau officiel
        Abonnement.objects.create(
            adherent=request.user,
            plan=plan,
            date_debut=timezone.now(),
            date_fin=date_fin,
            est_actif=True
        )
        
        messages.success(request, f"Privilège {plan.nom} accordé. Montant de {prix} MAD simulé avec succès.")
        return redirect('mes_abonnements')
    
    return render(request, 'core/souscrire_abonnement.html', {
        'plans': plans,
        'abonnement_actif': abonnement_actif
    })

@login_required
def mes_abonnements(request):
    """Historique des abonnements de l'adhérent."""
    abonnements = Abonnement.objects.filter(adherent=request.user).order_by('-date_debut')
    abonnement_actif = request.user.get_abonnement_actif()
    
    jours_restants = 0
    if abonnement_actif:
        jours_restants = (abonnement_actif.date_fin - timezone.now()).days
    
    return render(request, 'core/mes_abonnements.html', {
        'abonnements': abonnements,
        'abonnement_actif': abonnement_actif,
        'jours_restants': jours_restants,
        'now': timezone.now()
    })

@login_required
@admin_required
def admin_abonnements(request):
    """Console de pilotage unifiée : KPIs + Gestion des membres + Plans."""
    adherents = User.objects.filter(role='adherent')
    plans = PlanAbonnement.objects.all().order_by('prix_mensuel')
    
    adherents_data = []
    chiffre_affaires = 0
    
    for adh in adherents:
        abo = adh.get_abonnement_actif()
        if abo:
            chiffre_affaires += abo.plan.prix_mensuel
        adherents_data.append({
            'adherent': adh,
            'abonnement_actif': abo,
            'a_penalite': adh.a_penalite_impayee()
        })
    return render(request, 'core/admin_abonnements.html', {
        'adherents_data': adherents_data,
        'plans': plans,
        'total_adherents': adherents.count(),
        'abonnes_actifs': sum(1 for a in adherents_data if a['abonnement_actif']),
        'chiffre_affaires': chiffre_affaires
    })

@login_required
@admin_required
def renouveler_abonnement(request, abonnement_id):
    """Action administrative de renouvellement forcé."""
    abonnement = get_object_or_404(Abonnement, pk=abonnement_id)

    if request.method == 'POST':
        duree = request.POST.get('duree', 'mensuel')
        abonnement.date_fin = timezone.now() + timedelta(days=365 if duree == 'annuel' else 30)
        abonnement.est_actif = True
        abonnement.save()
        messages.success(request, f"Abonnement de {abonnement.adherent.username} prolongé jusqu'au {abonnement.date_fin.strftime('%d/%m/%Y')}.")
        return redirect('admin_abonnements')

    return render(request, 'core/renouveler_abonnement.html', {'abonnement': abonnement})

@login_required
def annuler_abonnement(request):
    """Permet à l'adhérent de mettre fin à son abonnement actuel."""
    abonnement_actif = request.user.get_abonnement_actif()
    if abonnement_actif:
        abonnement_actif.est_actif = False
        abonnement_actif.save()
        messages.warning(request, "Votre abonnement a été annulé. Vos privilèges ont été révoqués.")
    else:
        messages.info(request, "Aucun abonnement actif à annuler.")
    return redirect('mes_abonnements')
