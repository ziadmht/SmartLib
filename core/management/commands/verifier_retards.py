from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Emprunt, User
from django.core.mail import send_mail
from django.conf import settings

class Command(BaseCommand):
    help = 'Vérifie les emprunts en retard et envoie des notifications par email.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Démarrage de la vérification des retards...'))
        
        aujourdhui = timezone.now()
        emprunts_en_cours = Emprunt.objects.filter(est_retourne=False)
        
        compteur_retards = 0
        compteur_rappels = 0
        
        for emprunt in emprunts_en_cours:
            # 1. Gestion des retards avérés
            if emprunt.est_en_retard():
                compteur_retards += 1
                penalite = emprunt.calculer_penalite()
                self.stdout.write(self.style.WARNING(
                    f"RETARD : {emprunt.adherent.username} pour '{emprunt.livre.title if hasattr(emprunt.livre, 'title') else emprunt.livre.titre}' - Pénalité: {penalite} MAD"
                ))
                
                # Notification de retard (une fois par jour via cron)
                if emprunt.adherent.email:
                    send_mail(
                        '[SmartLib] Alerte Retard - Livre non rendu',
                        f"Bonjour {emprunt.adherent.username},\n\n"
                        f"Votre emprunt du livre '{emprunt.livre.titre}' est en retard depuis le {emprunt.date_retour_prevue.strftime('%d/%m/%Y')}.\n"
                        f"La pénalité actuelle est de {penalite} MAD.\n\n"
                        f"Merci de le rapporter au plus vite pour éviter d'augmenter vos frais et de bloquer votre accès à la E-Library.",
                        settings.DEFAULT_FROM_EMAIL,
                        [emprunt.adherent.email],
                        fail_silently=True,
                    )

            # 2. Rappel 3 jours avant (J-3)
            elif (emprunt.date_retour_prevue - aujourdhui).days == 3:
                compteur_rappels += 1
                if emprunt.adherent.email:
                    send_mail(
                        '[SmartLib] Rappel - Échéance d\'emprunt proche',
                        f"Bonjour {emprunt.adherent.username},\n\n"
                        f"Ceci est un rappel : vous devez rendre le livre '{emprunt.livre.titre}' le {emprunt.date_retour_prevue.strftime('%d/%m/%Y')} (dans 3 jours).\n\n"
                        f"À bientôt chez SmartLib !",
                        settings.DEFAULT_FROM_EMAIL,
                        [emprunt.adherent.email],
                        fail_silently=True,
                    )

        self.stdout.write(self.style.SUCCESS(
            f"Terminé. {compteur_retards} retards signalés et {compteur_rappels} rappels envoyés."
        ))
