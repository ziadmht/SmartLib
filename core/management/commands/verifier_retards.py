from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Emprunt, User, Abonnement, Notification
from django.core.mail import send_mail
from django.conf import settings

class Command(BaseCommand):
    help = 'Vérifie les emprunts en retard et les abonnements expirés.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Démarrage de la vérification globale...'))
        
        aujourdhui = timezone.now()
        
        # 1. GESTION DES EMPRUNTS
        emprunts_en_cours = Emprunt.objects.filter(statut='en_cours', est_retourne=False)
        compteur_retards = 0
        compteur_rappels = 0
        
        for emprunt in emprunts_en_cours:
            if not emprunt.date_retour_prevue:
                continue

            if emprunt.est_en_retard():
                compteur_retards += 1
                penalite = emprunt.calculer_penalite()
                
                # Mise à jour ou création de l'alerte
                notif, created = Notification.objects.get_or_create(
                    adherent=emprunt.adherent,
                    emprunt=emprunt,
                    type='retard',
                    titre=f"RETARD CRITIQUE : {emprunt.livre.titre}"
                )
                
                # On met à jour le message avec la pénalité fraîche et on force le statut "non lu"
                notif.message = f"Votre emprunt du livre '{emprunt.livre.titre}' est en retard de {penalite} MAD. Merci de le rendre immédiatement au Sanctuaire."
                notif.est_lu = False
                notif.save()

                self.stdout.write(self.style.WARNING(
                    f"RETARD : {emprunt.adherent.username} pour '{emprunt.livre.titre}' - Pénalité: {penalite} MAD"
                ))
                
                if emprunt.adherent.email:
                    send_mail(
                        '[SmartLib] Alerte Retard - Livre non rendu',
                        f"Bonjour {emprunt.adherent.username},\n\n"
                        f"Votre emprunt du livre '{emprunt.livre.titre}' est en retard depuis le {emprunt.date_retour_prevue.strftime('%d/%m/%Y')}.\n"
                        f"La pénalité actuelle est de {penalite} MAD.\n\n"
                        f"Merci de le rapporter au plus vite.",
                        settings.DEFAULT_FROM_EMAIL,
                        [emprunt.adherent.email],
                        fail_silently=True,
                    )
            elif (emprunt.date_retour_prevue - aujourdhui).days == 3:
                compteur_rappels += 1
                
                # Rappel interne
                Notification.objects.get_or_create(
                    adherent=emprunt.adherent,
                    emprunt=emprunt,
                    type='info',
                    titre=f"Rappel : Échéance proche",
                    defaults={
                        'message': f"Pensez à rendre '{emprunt.livre.titre}' dans 3 jours pour éviter les pénalités."
                    }
                )

                if emprunt.adherent.email:
                    send_mail(
                        '[SmartLib] Rappel - Échéance d\'emprunt proche',
                        f"Bonjour {emprunt.adherent.username},\n\n"
                        f"Ceci est un rappel : vous devez rendre le livre '{emprunt.livre.titre}' le {emprunt.date_retour_prevue.strftime('%d/%m/%Y')} (dans 3 jours).",
                        settings.DEFAULT_FROM_EMAIL,
                        [emprunt.adherent.email],
                        fail_silently=True,
                    )

        # 2. GESTION DES ABONNEMENTS EXPIRÉS
        abonnements_a_fermer = Abonnement.objects.filter(est_actif=True, date_fin__lt=aujourdhui)
        nb_fermes = abonnements_a_fermer.count()
        abonnements_a_fermer.update(est_actif=False)
        
        if nb_fermes > 0:
            self.stdout.write(self.style.SUCCESS(f"✅ {nb_fermes} abonnements expirés ont été archivés."))

        self.stdout.write(self.style.SUCCESS(
            f"Terminé. {compteur_retards} retards, {compteur_rappels} rappels, {nb_fermes} abonnements clos."
        ))
