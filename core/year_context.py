"""Année scolaire active dans la session (sélecteur en-tête)."""
from academics.models import AcademicYear


SESSION_KEY = 'selected_academic_year_id'


def get_selected_year(request):
    """
    Année choisie dans le sélecteur, sinon année is_current, sinon la plus récente.
    """
    year = None
    year_id = None
    if request is not None:
        year_id = request.session.get(SESSION_KEY)
    if year_id:
        year = AcademicYear.objects.filter(pk=year_id).first()
    if not year:
        year = AcademicYear.objects.filter(is_current=True).first()
    if not year:
        year = AcademicYear.objects.order_by('-is_current', '-start_date', '-id').first()
    return year


def set_selected_year(request, year_id):
    if year_id:
        request.session[SESSION_KEY] = int(year_id)
    else:
        request.session.pop(SESSION_KEY, None)


def academic_year_context(request):
    """Context processor : years list + selected year everywhere."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}
    try:
        years = list(AcademicYear.objects.order_by('-is_current', '-start_date', '-id'))
        selected = get_selected_year(request)
        return {
            'all_academic_years': years,
            'selected_year': selected,
            'current_year': selected,  # alias used in many templates
        }
    except Exception:
        return {}


def permissions_context(request):
    """Expose can_* dans les templates pour le menu."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}
    from core.permissions import can, get_role, get_role_label
    role = get_role(request.user)
    keys = [
        'nav.dashboard', 'nav.students', 'nav.teachers', 'nav.classrooms', 'nav.parents',
        'nav.promotion', 'nav.grades', 'nav.bulletins', 'nav.finance', 'nav.attendance',
        'nav.timetable', 'nav.announcements', 'nav.messages', 'nav.config', 'nav.settings',
        'nav.admin_tech', 'nav.reports', 'students.create', 'grades.entry', 'finance.pay', 'config.users',
        'personnel.dashboard', 'personnel.list', 'personnel.create', 'personnel.edit',
        'personnel.salaries', 'personnel.contracts', 'personnel.presences', 'personnel.documents',
        'personnel.reports', 'personnel.assign', 'finance.expenses', 'finance.reports',
    ]
    out = {
        'user_role': role,
        'user_role_label': get_role_label(request.user),
    }
    for k in keys:
        # template-friendly: nav_students
        name = 'can_' + k.replace('.', '_').replace('-', '_')
        out[name] = can(request.user, k)
    return out
