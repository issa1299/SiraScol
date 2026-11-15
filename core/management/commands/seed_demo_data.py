"""
python manage.py seed_demo_data

Crée des données de démonstration :
- 6 enseignants
- Classes (primaire, secondaire, lycée)
- Élèves inscrits
- Parents liés
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from academics.models import AcademicYear, Cycle, Level, ClassRoom, Subject
from teachers.models import Teacher
from students.models import Student, Parent, ParentStudent, Enrollment
from finance.models import FeeType, Invoice


class Command(BaseCommand):
    help = 'Crée classes, enseignants, élèves et parents de démonstration'

    def handle(self, *args, **options):
        with transaction.atomic():
            year = AcademicYear.objects.filter(is_current=True).first()
            if not year:
                y1 = date.today().year if date.today().month >= 9 else date.today().year - 1
                year = AcademicYear.objects.create(
                    name=f'{y1}-{y1+1}',
                    start_date=date(y1, 9, 1),
                    end_date=date(y1 + 1, 7, 31),
                    is_current=True,
                )
                self.stdout.write(f'Année créée : {year.name}')

            # --- Enseignants ---
            teachers_data = [
                ('ENS001', 'Diallo', 'Amadou', 'M', 'Mathématiques', '70 00 00 01'),
                ('ENS002', 'Traoré', 'Fatoumata', 'F', 'Français', '70 00 00 02'),
                ('ENS003', 'Keita', 'Ibrahim', 'M', 'Anglais', '70 00 00 03'),
                ('ENS004', 'Sangaré', 'Aïssata', 'F', 'Sciences', '70 00 00 04'),
                ('ENS005', 'Coulibaly', 'Moussa', 'M', 'Histoire-Géo', '70 00 00 05'),
                ('ENS006', 'Camara', 'Mariame', 'F', 'Primaire général', '70 00 00 06'),
            ]
            teachers = []
            for mat, last, first, gender, spe, phone in teachers_data:
                t, created = Teacher.objects.get_or_create(
                    matricule=mat,
                    defaults={
                        'last_name': last,
                        'first_name': first,
                        'gender': gender,
                        'speciality': spe,
                        'phone': phone,
                        'is_active': True,
                        'hire_date': date(2020, 9, 1),
                    },
                )
                teachers.append(t)
                self.stdout.write(f'  Enseignant: {t} ({"créé" if created else "existant"})')

            # --- Matières de base ---
            subjects_data = [
                ('FR', 'Français', 3),
                ('MATH', 'Mathématiques', 4),
                ('ANG', 'Anglais', 2),
                ('SVT', 'SVT', 2),
                ('PC', 'Physique-Chimie', 3),
                ('HG', 'Histoire-Géographie', 2),
            ]
            for code, name, coef in subjects_data:
                Subject.objects.get_or_create(
                    code=code,
                    defaults={'name': name, 'coefficient': Decimal(str(coef)), 'is_active': True},
                )

            # --- Classes ---
            classes_spec = [
                # (level_name_contains, class_name, capacity, inscription, tuition, serie, teacher_idx)
                ('1ère année', '1ère A', 35, 15000, 75000, '', 5),
                ('2ème année', '2ème A', 35, 15000, 75000, '', 5),
                ('3ème année', '3ème A', 35, 15000, 80000, '', 5),
                ('5ème année', '5ème A', 35, 15000, 85000, '', 5),
                ('6ème année', '6ème A', 40, 20000, 100000, '', 0),
                ('7ème année', '7ème A', 40, 20000, 110000, '', 1),
                ('8ème année', '8ème A', 40, 20000, 110000, '', 2),
                ('9ème année', '9ème A', 40, 25000, 120000, '', 0),
                ('10ème année', '10ème Sci A', 40, 30000, 150000, 'Scientifique', 0),
                ('11ème année', '11ème Sci A', 40, 30000, 150000, 'Scientifique', 3),
                ('12ème année', '12ème Sci A', 40, 35000, 180000, 'Scientifique', 0),
                ('12ème année', '12ème Litt A', 40, 35000, 180000, 'Littéraire', 1),
            ]

            classrooms = []
            for level_name, cname, capacity, ins, scola, serie, tidx in classes_spec:
                level = Level.objects.filter(name=level_name).first()
                if not level:
                    level = Level.objects.filter(name__iexact=level_name).first()
                if not level:
                    self.stdout.write(self.style.WARNING(f'  Niveau introuvable: {level_name} — saute {cname}'))
                    continue
                room, created = ClassRoom.objects.get_or_create(
                    name=cname,
                    academic_year=year,
                    defaults={
                        'level': level,
                        'capacity': capacity,
                        'inscription_fee': Decimal(str(ins)),
                        'tuition_fee': Decimal(str(scola)),
                        'serie': serie,
                        'main_teacher': teachers[tidx] if tidx < len(teachers) else None,
                    },
                )
                classrooms.append(room)
                self.stdout.write(f'  Classe: {room} ({"créée" if created else "existante"})')

            if not classrooms:
                self.stdout.write(self.style.ERROR(
                    'Aucune classe créée. Lance d\'abord: python manage.py init_school_data'
                ))
                return

            # --- Parents + Élèves ---
            families = [
                # (parent_last, parent_first, phone, relation,
                #  [(student_last, student_first, gender, birth, class_name), ...])
                ('Koné', 'Boubacar', '76 11 11 11', 'pere', [
                    ('Koné', 'Awa', 'F', date(2018, 3, 12), '1ère A'),
                    ('Koné', 'Sékou', 'M', date(2016, 7, 5), '3ème A'),
                ]),
                ('Diarra', 'Aminata', '76 22 22 22', 'mere', [
                    ('Diarra', 'Oumar', 'M', date(2015, 1, 20), '5ème A'),
                ]),
                ('Touré', 'Seydou', '76 33 33 33', 'pere', [
                    ('Touré', 'Fatou', 'F', date(2013, 11, 8), '6ème A'),
                    ('Touré', 'Mamadou', 'M', date(2011, 4, 15), '8ème A'),
                ]),
                ('Bah', 'Rokia', '76 44 44 44', 'mere', [
                    ('Bah', 'Ibrahim', 'M', date(2010, 9, 2), '9ème A'),
                ]),
                ('Cissé', 'Moussa', '76 55 55 55', 'pere', [
                    ('Cissé', 'Aïcha', 'F', date(2009, 6, 18), '10ème Sci A'),
                    ('Cissé', 'Youssouf', 'M', date(2008, 2, 28), '11ème Sci A'),
                ]),
                ('Sylla', 'Hawa', '76 66 66 66', 'mere', [
                    ('Sylla', 'Abdoulaye', 'M', date(2007, 12, 1), '12ème Sci A'),
                ]),
                ('Ouattara', 'Adama', '76 77 77 77', 'pere', [
                    ('Ouattara', 'Mariame', 'F', date(2007, 5, 22), '12ème Litt A'),
                ]),
                ('Dembele', 'Kadiatou', '76 88 88 88', 'mere', [
                    ('Dembele', 'Lassana', 'M', date(2017, 8, 9), '2ème A'),
                    ('Dembele', 'Nana', 'F', date(2014, 10, 30), '5ème A'),
                ]),
            ]

            room_by_name = {c.name: c for c in classrooms}
            student_count = 0
            parent_count = 0

            for plast, pfirst, phone, relation, kids in families:
                parent, pcreated = Parent.objects.get_or_create(
                    phone=phone,
                    defaults={
                        'last_name': plast,
                        'first_name': pfirst,
                        'profession': 'Commerçant',
                        'address': 'Bamako',
                    },
                )
                if pcreated:
                    parent_count += 1
                self.stdout.write(f'  Parent: {parent}')

                for slast, sfirst, gender, birth, cname in kids:
                    # matricule auto via save if blank
                    student, screated = Student.objects.get_or_create(
                        last_name=slast,
                        first_name=sfirst,
                        date_of_birth=birth,
                        defaults={
                            'gender': gender,
                            'status': 'actif',
                            'enrollment_date': date(year.start_date.year, 9, 1),
                            'phone': phone,
                            'address': 'Bamako',
                        },
                    )
                    if screated:
                        student_count += 1
                    self.stdout.write(f'    Élève: {student} ({student.matricule})')

                    ParentStudent.objects.get_or_create(
                        parent=parent,
                        student=student,
                        defaults={'relation': relation, 'is_primary': True},
                    )

                    room = room_by_name.get(cname)
                    if room:
                        enr, ecreated = Enrollment.objects.get_or_create(
                            student=student,
                            academic_year=year,
                            defaults={
                                'classroom': room,
                                'enrollment_date': student.enrollment_date or date(year.start_date.year, 9, 1),
                                'is_active': True,
                            },
                        )
                        # Factures auto si frais définis
                        if ecreated and (room.inscription_fee or room.tuition_fee):
                            for label, amount in [
                                ("Frais d'inscription", room.inscription_fee),
                                ('Scolarité', room.tuition_fee),
                            ]:
                                if not amount or amount <= 0:
                                    continue
                                fee, _ = FeeType.objects.get_or_create(
                                    name=label,
                                    defaults={'default_amount': amount, 'is_active': True},
                                )
                                Invoice.objects.get_or_create(
                                    student=student,
                                    fee_type=fee,
                                    academic_year=year,
                                    defaults={
                                        'amount': amount,
                                        'due_date': date(year.start_date.year, 10, 31),
                                        'status': 'en_attente',
                                    },
                                )

            self.stdout.write(self.style.SUCCESS(
                f'\n✅ Démo prête :\n'
                f'  • {Teacher.objects.count()} enseignants\n'
                f'  • {ClassRoom.objects.filter(academic_year=year).count()} classes\n'
                f'  • {Student.objects.count()} élèves\n'
                f'  • {Parent.objects.count()} parents\n'
                f'\nRafraîchis le dashboard dans le navigateur.'
            ))
