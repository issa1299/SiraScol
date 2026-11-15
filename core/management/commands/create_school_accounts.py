from django.core.management.base import BaseCommand
from core.account_sync import (
    ensure_user_for_teacher,
    ensure_user_for_student,
    ensure_user_for_parent,
)


class Command(BaseCommand):
    help = "Crée les comptes manquants pour enseignants, élèves et parents"

    def handle(self, *args, **options):
        from teachers.models import Teacher
        from students.models import Student, Parent

        n_t = n_s = n_p = 0
        for t in Teacher.objects.all():
            u, created, pwd = ensure_user_for_teacher(t)
            if created:
                n_t += 1
                self.stdout.write(f"  Ens: {t} → {u.username} / {pwd}")
        for s in Student.objects.all():
            u, created, pwd = ensure_user_for_student(s)
            if created:
                n_s += 1
                self.stdout.write(f"  Élève: {s} → {u.username} / {pwd}")
        for p in Parent.objects.all():
            u, created, pwd = ensure_user_for_parent(p)
            if created:
                n_p += 1
                self.stdout.write(f"  Parent: {p} → {u.username} / {pwd}")
        self.stdout.write(self.style.SUCCESS(
            f"Comptes créés : {n_t} enseignants, {n_s} élèves, {n_p} parents"
        ))
