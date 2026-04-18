"""
Template context processor that injects the active tournament and its stages
into every template context. This allows the navbar and footer to be built
dynamically.
"""

from .models import Tournament


def active_tournament(request):
    """Inject active tournament data into all templates."""
    tournament = Tournament.objects.filter(is_active=True).select_related().first()

    if tournament:
        stages = tournament.stages.order_by('order')
        return {
            'active_tournament': tournament,
            'tournament_stages': stages,
        }

    return {
        'active_tournament': None,
        'tournament_stages': [],
    }
