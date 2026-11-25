# -*- coding: utf-8 -*-
"""Inscrit des élèves (avec parent lié) dans les classes de 1ère à 9ème.

Usage :
    python manage.py seed_students_1_to_9 --per-class 20

Idempotent : relancer la commande ne crée aucun doublon (recherche par nom,
prénom, date de naissance pour l'élève et par téléphone pour le parent).
Les classes du lycée (10ᵉ et plus) ne sont jamais concernées.

Par défaut, les comptes de connexion ne sont pas créés : les signaux
``post_save`` de Student/Parent sont temporairement déconnectés pour éviter
360 hachages de mot de passe inutiles. Utilisez ``--with-accounts`` pour les
générer quand même.
"""
import re
import weakref
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.db.models.signals import post_save

from academics.models import AcademicYear, ClassRoom
from students.models import Enrollment, Parent, ParentStudent, Student


FIRST_NAMES = [
    'Awa', 'Sékou', 'Fatou', 'Ibrahim', 'Aminata', 'Oumar', 'Kadiatou', 'Moussa',
    'Hawa', 'Adama', 'Bintou', 'Lassana', 'Nana', 'Youssouf', 'Rokia', 'Seydou',
    'Mariame', 'Boubacar', 'Aïcha', 'Mamadou',
]
LAST_NAMES = [
    'Koné', 'Diarra', 'Touré', 'Bah', 'Cissé', 'Sylla', 'Ouattara', 'Dembélé',
    'Traoré', 'Keïta', 'Camara', 'Sangaré', 'Coulibaly', 'Niaré', 'Fofana',
    'Kanté', 'Sidibé', 'Doumbia', 'Guindo', 'Bamba',
]

# Uniquement le 1er et le 2ème cycle (1ère → 9ème année).
LEVEL_PREFIXES = []
for number in range(1, 10):
    for suffix in ('ère', 'eme', 'ème', 'er', 'e'):
        LEVEL_PREFIXES.append(f'{number}{suffix}')

AUTO_USER_SIGNALS = (
    ('auto_user_student', Student),
    ('auto_user_parent', Parent),
)


class Command(BaseCommand):
    help = 'Inscrit 20 élèves par classe de 1ère à 9ème, chacun avec un parent lié'

    def add_arguments(self, parser):
        parser.add_argument(
            '--per-class', type=int, default=20,
            help='Nombre d’élèves à inscrire dans chaque classe (défaut : 20)',
        )
        parser.add_argument(
            '--with-accounts', action='store_true',
            help='Créer aussi un compte de connexion pour chaque élève/parent',
        )

    def handle(self, *args, **options):
        per_class = options['per_class']
        if per_class < 1:
            raise CommandError('--per-class doit être supérieur à 0.')

        year = AcademicYear.objects.filter(is_current=True).first()
        if not year:
            raise CommandError('Aucune année scolaire en cours.')

        query = Q()
        for prefix in LEVEL_PREFIXES:
            query |= Q(level__name__istartswith=prefix)
        rooms = ClassRoom.objects.filter(academic_year=year).filter(query).select_related(
            'level'
        ).order_by('level__order', 'name')
        if not rooms:
            raise CommandError('Aucune classe de 1ère à 9ème pour cette année.')

        skip_accounts = not options['with_accounts']
        captured_receivers = []
        if skip_accounts:
            # On conserve une référence forte aux récepteurs : Django les stocke
            # par référence faible, ils disparaîtraient sinon après reconnexion.
            for uid, sender in AUTO_USER_SIGNALS:
                for entry in list(post_save.receivers):
                    lookup_key, receiver_ref = entry[0], entry[1]
                    if lookup_key[0] != uid:
                        continue
                    receiver = (receiver_ref() if isinstance(receiver_ref, weakref.ReferenceType)
                                else receiver_ref)
                    if receiver is None:
                        continue
                    captured_receivers.append((uid, sender, receiver))
                    post_save.disconnect(
                        receiver=receiver_ref, sender=sender, dispatch_uid=uid
                    )

        created_students = created_parents = created_links = created_enrollments = 0
        seq = 0
        try:
            with transaction.atomic():
                for room in rooms:
                    match = re.match(r'\d+', room.level.name or '')
                    level_number = int(match.group()) if match else 1
                    birth_year = date.today().year - (level_number + 5)
                    before = created_students
                    for index in range(per_class):
                        seq += 1
                        last = LAST_NAMES[seq % len(LAST_NAMES)]
                        first = FIRST_NAMES[(seq * 3) % len(FIRST_NAMES)]
                        birth = date(birth_year, (seq % 12) + 1, (seq % 28) + 1)
                        gender = 'F' if seq % 2 else 'M'
                        phone = (f'76 {level_number:02d} {index + 1:02d} '
                                 f'{seq % 100:02d} {(seq * 7) % 100:02d}')

                        student, student_created = Student.objects.get_or_create(
                            last_name=last, first_name=first, date_of_birth=birth,
                            defaults={
                                'gender': gender,
                                'status': 'actif',
                                'enrollment_date': year.start_date or date.today(),
                                'place_of_birth': 'Bamako',
                                'address': 'Bamako',
                                'phone': phone,
                            },
                        )
                        created_students += int(student_created)

                        parent, parent_created = Parent.objects.get_or_create(
                            phone=phone,
                            defaults={
                                'last_name': last,
                                'first_name': FIRST_NAMES[(seq + 7) % len(FIRST_NAMES)],
                                'profession': 'Commerçant' if seq % 2 else 'Cultivateur',
                                'address': 'Bamako',
                            },
                        )
                        created_parents += int(parent_created)

                        _, link_created = ParentStudent.objects.get_or_create(
                            parent=parent, student=student,
                            defaults={
                                'relation': 'mere' if gender == 'F' else 'pere',
                                'is_primary': True,
                            },
                        )
                        created_links += int(link_created)

                        _, enrollment_created = Enrollment.objects.get_or_create(
                            student=student, academic_year=year,
                            defaults={
                                'classroom': room,
                                'enrollment_date': year.start_date or date.today(),
                                'is_active': True,
                            },
                        )
                        created_enrollments += int(enrollment_created)
                    self.stdout.write(
                        f'  {room.name} : {created_students - before} élève(s) créé(s) '
                        f'(total visé {per_class})'
                    )
        finally:
            for uid, sender, receiver in captured_receivers:
                post_save.connect(receiver, sender=sender, dispatch_uid=uid)

        self.stdout.write(self.style.SUCCESS(
            f'\nInscription terminée pour {year.name} :\n'
            f'  • {rooms.count()} classe(s) de 1ère à 9ème\n'
            f'  • {created_students} élève(s) créé(s)\n'
            f'  • {created_parents} parent(s) créé(s)\n'
            f'  • {created_links} liaison(s) parent-élève\n'
            f'  • {created_enrollments} inscription(s) créée(s)'
        ))
