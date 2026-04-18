"""
Tournament-aware views.

All views scope data to the active tournament. The generic `stage_detail`
view adapts to any stage type (group, knockout, round-robin).
"""

from django.http import Http404
from django.shortcuts import render, get_object_or_404
from .models import (
    Tournament, TournamentStage, Match, PointsTableEntry,
    Group, GroupMembership, Team,
)


def get_active_tournament():
    """Return the active tournament or None."""
    return Tournament.objects.filter(is_active=True).first()


def _get_actual_stage_counts(stage):
    """Get actual team and group counts for a stage from real data."""
    actual_groups = stage.groups.count()

    if stage.stage_type == 'group':
        # Teams assigned to groups in this stage
        actual_teams = Team.objects.filter(
            groupmembership__group__stage=stage
        ).distinct().count()
    else:
        # Teams that appear in matches or points table for this stage
        team_ids = set()
        for m in stage.matches.all().only('team1_id', 'team2_id'):
            team_ids.add(m.team1_id)
            team_ids.add(m.team2_id)
        # Also count from points entries (for teams without matches yet)
        pt_ids = PointsTableEntry.objects.filter(
            stage=stage
        ).values_list('team_id', flat=True)
        team_ids.update(pt_ids)
        actual_teams = len(team_ids)

    return actual_teams, actual_groups


def dashboard(request):
    """Tournament dashboard / home page."""
    tournament = get_active_tournament()

    if not tournament:
        return render(request, 'tournament/no_tournament.html')

    stages = tournament.stages.order_by('order')

    total_teams = tournament.teams.count()
    total_matches = Match.objects.filter(stage__tournament=tournament).count()
    completed_matches = Match.objects.filter(stage__tournament=tournament, status='completed').count()

    # Build stage summaries
    stage_data = []
    current_stage = None
    for s in stages:
        s_total = s.matches.count()
        s_completed = s.matches.filter(status='completed').count()
        progress = (s_completed / s_total * 100) if s_total > 0 else 0

        status = 'upcoming'
        if s_completed > 0 and s_completed < s_total:
            status = 'in_progress'
            if current_stage is None:
                current_stage = s.name
        elif s_completed > 0 and s_completed == s_total:
            status = 'completed'

        # Get actual counts from real data
        actual_teams, actual_groups = _get_actual_stage_counts(s)

        stage_data.append({
            'stage': s,
            'total_matches': s_total,
            'completed_matches': s_completed,
            'progress': progress,
            'status': status,
            'actual_teams': actual_teams,
            'actual_groups': actual_groups,
        })

    if current_stage is None and completed_matches > 0:
        first_stage = stages.first()
        current_stage = first_stage.name if first_stage else 'Not Started'
    elif current_stage is None:
        current_stage = 'Not Started'

    # Recent completed matches
    recent_matches = Match.objects.filter(
        stage__tournament=tournament,
        status='completed',
    ).select_related('team1', 'team2', 'winner', 'batting_first', 'stage', 'group').order_by('-match_number')[:6]

    # Top teams (from first stage's points table)
    first_stage = stages.first()
    top_teams = PointsTableEntry.objects.none()
    if first_stage:
        top_teams = PointsTableEntry.objects.filter(
            stage=first_stage
        ).select_related('team').order_by('-points', '-nrr')[:8]

    context = {
        'tournament': tournament,
        'total_teams': total_teams,
        'total_matches': total_matches,
        'completed_matches': completed_matches,
        'current_stage': current_stage,
        'stage_data': stage_data,
        'recent_matches': recent_matches,
        'top_teams': top_teams,
        'active_page': 'dashboard',
    }
    return render(request, 'tournament/dashboard.html', context)


def matches_list(request):
    """View to list all matches with filter by stage."""
    tournament = get_active_tournament()
    
    if not tournament:
        return render(request, 'tournament/no_tournament.html', {})
        
    stage_slug = request.GET.get('stage')
    
    # Base queryset for all matches in this tournament
    matches_qs = Match.objects.filter(stage__tournament=tournament).select_related(
        'team1', 'team2', 'winner', 'stage', 'group'
    ).order_by('stage__order', 'match_number')
    
    # Filter by stage if requested
    if stage_slug:
        matches_qs = matches_qs.filter(stage__slug=stage_slug)
    
    # Group matches by status for the template
    completed_matches = [m for m in matches_qs if m.status == 'completed']
    upcoming_matches = [m for m in matches_qs if m.status == 'upcoming']
        
    context = {
        'tournament': tournament,
        'completed_matches': completed_matches,
        'upcoming_matches': upcoming_matches,
        'active_stage_slug': stage_slug,
        'active_page': 'matches_list',
    }
    return render(request, 'tournament/matches_list.html', context)


def stage_detail(request, stage_slug):
    """
    Generic stage detail view — adapts based on stage_type:
    - group: tabs with groups, points tables, match cards
    - round_robin: single flat points table + match cards
    - knockout: bracket / match cards
    """
    tournament = get_active_tournament()
    if not tournament:
        return render(request, 'tournament/no_tournament.html')

    stage = get_object_or_404(TournamentStage, tournament=tournament, slug=stage_slug)

    # Common data
    all_matches = stage.matches.select_related(
        'team1', 'team2', 'winner', 'batting_first', 'group'
    ).order_by('match_number')

    completed_matches = all_matches.filter(status='completed')
    upcoming_matches = all_matches.filter(status='upcoming')

    total_matches_count = all_matches.count()
    completed_count = completed_matches.count()
    progress = (completed_count / total_matches_count * 100) if total_matches_count > 0 else 0

    # Actual counts for header
    actual_teams, actual_groups = _get_actual_stage_counts(stage)

    context = {
        'tournament': tournament,
        'stage': stage,
        'total_matches_count': total_matches_count,
        'completed_count': completed_count,
        'progress': progress,
        'active_page': stage.slug,
        'actual_teams': actual_teams,
        'actual_groups': actual_groups,
    }

    if stage.stage_type == 'group':
        # Grouped view — build data per group
        groups = stage.groups.order_by('name')
        group_data = []

        for group in groups:
            entries = PointsTableEntry.objects.filter(
                stage=stage, group=group,
            ).select_related('team').order_by('-points', '-nrr', '-won', 'team__name')

            for i, entry in enumerate(entries, 1):
                entry.display_rank = i

            g_matches = all_matches.filter(group=group)
            g_completed = g_matches.filter(status='completed')
            g_upcoming = g_matches.filter(status='upcoming')
            g_total = g_matches.count()
            g_comp_count = g_completed.count()

            group_data.append({
                'group': group,
                'entries': entries,
                'completed_matches': g_completed,
                'upcoming_matches': g_upcoming,
                'total_matches': g_total,
                'completed_count': g_comp_count,
                'progress': (g_comp_count / g_total * 100) if g_total > 0 else 0,
            })

        active_group = request.GET.get('group', groups.first().name if groups.exists() else '')
        context.update({
            'group_data': group_data,
            'active_group': active_group,
        })

    elif stage.stage_type == 'round_robin':
        # Flat round-robin — single points table
        entries = PointsTableEntry.objects.filter(
            stage=stage,
        ).select_related('team').order_by('-points', '-nrr', '-won', 'team__name')

        for i, entry in enumerate(entries, 1):
            entry.display_rank = i

        context.update({
            'entries': entries,
            'completed_matches': completed_matches,
            'upcoming_matches': upcoming_matches,
        })

    elif stage.stage_type == 'knockout':
        # Build IPL-style playoff bracket
        # Match numbering convention:
        #   1 = Qualifier 1 (1st vs 2nd)
        #   2 = Eliminator  (3rd vs 4th)
        #   3 = Qualifier 2 (Loser Q1 vs Winner Eliminator)
        #   4 = Final        (Winner Q1 vs Winner Q2)
        all_ko_matches = list(all_matches)

        # Helper to find match by number
        def _find_match(num):
            for m in all_ko_matches:
                if m.match_number == num:
                    return m
            return None

        # Create a dummy match-like object for empty slots
        class _EmptyMatch:
            team1 = None
            team2 = None
            status = 'upcoming'
            winner = None
            team1_total = None
            team1_wickets = None
            team2_total = None
            team2_wickets = None

        q1 = _find_match(1) or _EmptyMatch()
        eliminator = _find_match(2) or _EmptyMatch()
        q2 = _find_match(3) or _EmptyMatch()
        final = _find_match(4) or _EmptyMatch()

        # If Q2/Final have placeholder team2 == team1 (waiting for upstream result),
        # null it out so the template shows "TBD"
        if (hasattr(q2, 'team1') and hasattr(q2, 'team2')
                and q2.team1 and q2.team2 and q2.team1 == q2.team2 and q2.status == 'upcoming'):
            q2.team2 = None
        if (hasattr(final, 'team1') and hasattr(final, 'team2')
                and final.team1 and final.team2 and final.team1 == final.team2 and final.status == 'upcoming'):
            final.team2 = None

        # Determine champion
        result_summary = ''
        if hasattr(final, 'winner') and final.winner:
            result_summary = final.winner.name

        has_any_team = (
            getattr(q1, 'team1', None) or
            getattr(eliminator, 'team1', None) or
            len(all_ko_matches) > 0
        )

        playoff_bracket = {
            'q1': q1,
            'eliminator': eliminator,
            'q2': q2,
            'final': final,
            'result_summary': result_summary,
        } if has_any_team else None

        context.update({
            'completed_matches': completed_matches,
            'upcoming_matches': upcoming_matches,
            'playoff_bracket': playoff_bracket,
        })

    return render(request, 'tournament/stage_detail.html', context)
