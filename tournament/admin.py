"""
Rich Django admin for tournament management.

Provides full CRUD for all models with inline editing,
filters, search, and custom actions.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Tournament, TournamentStage, Team, Group, GroupMembership,
    Match, PointsTableEntry, promote_qualified_teams, generate_fixtures,
)


# ──────────────────────────────────────────────────────────────
# Inlines
# ──────────────────────────────────────────────────────────────

class TournamentStageInline(admin.TabularInline):
    model = TournamentStage
    extra = 1
    fields = ['name', 'slug', 'stage_type', 'order', 'emoji',
              'teams_count', 'groups_count', 'qualify_count', 'matches_per_pairing']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order']


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 4
    raw_id_fields = ['team']
    ordering = ['order']


# ──────────────────────────────────────────────────────────────
# Tournament
# ──────────────────────────────────────────────────────────────

@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ['name', 'edition', 'is_active_badge', 'stages_list', 'team_count', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'edition']
    inlines = [TournamentStageInline]
    actions = ['make_active']

    @admin.display(description='Active', boolean=True)
    def is_active_badge(self, obj):
        return obj.is_active

    @admin.display(description='Stages')
    def stages_list(self, obj):
        stages = obj.stages.order_by('order').values_list('name', flat=True)
        return ' → '.join(stages) if stages else '—'

    @admin.display(description='Teams')
    def team_count(self, obj):
        return obj.teams.count()

    @admin.action(description='Set as active tournament')
    def make_active(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Please select exactly one tournament.", level='error')
            return
        Tournament.objects.update(is_active=False)
        queryset.update(is_active=True)
        self.message_user(request, f"'{queryset.first()}' is now the active tournament.")


# ──────────────────────────────────────────────────────────────
# Tournament Stage
# ──────────────────────────────────────────────────────────────

@admin.register(TournamentStage)
class TournamentStageAdmin(admin.ModelAdmin):
    list_display = ['name', 'tournament', 'stage_type', 'order',
                    'teams_count', 'groups_count', 'qualify_count', 'matches_per_pairing',
                    'actual_team_count', 'match_progress']
    list_filter = ['tournament', 'stage_type']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    actions = ['promote_to_next_stage', 'generate_stage_fixtures']

    @admin.display(description='Registered Teams')
    def actual_team_count(self, obj):
        if obj.stage_type == 'group':
            count = Team.objects.filter(
                groupmembership__group__stage=obj
            ).distinct().count()
        else:
            team_ids = set()
            for m in obj.matches.all():
                team_ids.add(m.team1_id)
                team_ids.add(m.team2_id)
            pts = PointsTableEntry.objects.filter(stage=obj).values_list('team_id', flat=True)
            team_ids.update(pts)
            count = len(team_ids)
        if count == 0:
            return format_html('<span style="color: #94a3b8;">—</span>')
        return count

    @admin.display(description='Matches')
    def match_progress(self, obj):
        total = obj.matches.count()
        completed = obj.matches.filter(status='completed').count()
        if total == 0:
            return format_html('<span style="color: #94a3b8;">—</span>')
        if completed == total:
            return format_html('<span style="color: #4ade80;">✓ {}/{}</span>', completed, total)
        return f"{completed}/{total}"

    @admin.action(description='🚀 Promote qualified teams to next stage')
    def promote_to_next_stage(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly ONE stage to promote from.",
                level='error',
            )
            return

        stage = queryset.first()
        success, message, teams = promote_qualified_teams(stage)

        if success:
            self.message_user(request, f"✅ {message}")
        else:
            self.message_user(request, f"❌ {message}", level='error')

    @admin.action(description='📋 Generate fixtures (tie-sheet) for this stage')
    def generate_stage_fixtures(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                "Please select exactly ONE stage to generate fixtures for.",
                level='error',
            )
            return

        stage = queryset.first()
        success, message = generate_fixtures(stage)

        if success:
            self.message_user(request, f"✅ {message}")
        else:
            self.message_user(request, f"❌ {message}", level='error')


# ──────────────────────────────────────────────────────────────
# Team
# ──────────────────────────────────────────────────────────────

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'tournament']
    list_filter = ['tournament']
    search_fields = ['name']
    list_per_page = 100


# ──────────────────────────────────────────────────────────────
# Group
# ──────────────────────────────────────────────────────────────

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'stage', 'team_count', 'team_list']
    list_filter = ['stage__tournament', 'stage']
    search_fields = ['name']
    inlines = [GroupMembershipInline]

    @admin.display(description='Teams')
    def team_count(self, obj):
        return obj.teams.count()

    @admin.display(description='Assigned Teams')
    def team_list(self, obj):
        teams = obj.teams.order_by('groupmembership__order').values_list('name', flat=True)
        if teams:
            return ', '.join(teams)
        return format_html('<span style="color: #94a3b8;">—</span>')


# ──────────────────────────────────────────────────────────────
# Match
# ──────────────────────────────────────────────────────────────

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = [
        'match_number', 'stage', 'group', 'team1', 'team2',
        'score_display', 'status_badge', 'winner', 'batting_first',
    ]
    list_filter = ['stage__tournament', 'stage', 'group', 'status']
    search_fields = ['team1__name', 'team2__name']
    raw_id_fields = ['team1', 'team2', 'winner', 'batting_first']
    list_per_page = 50

    fieldsets = (
        ('Match Info', {
            'fields': ('stage', 'group', 'match_number')
        }),
        ('Teams', {
            'fields': ('team1', 'team2')
        }),
        ('Team 1 Score', {
            'fields': ('team1_total', 'team1_overs', 'team1_wickets'),
            'description': 'Enter score to mark match as completed. Winner, status, and batting order are auto-detected.'
        }),
        ('Team 2 Score', {
            'fields': ('team2_total', 'team2_overs', 'team2_wickets'),
        }),
        ('Media & Links', {
            'fields': ('video_url',)
        }),
        ('Auto-Computed (override if needed)', {
            'fields': ('status', 'winner', 'batting_first'),
            'classes': ('collapse',),
            'description': 'These fields are auto-set when you enter scores. Only override if the auto-detection is wrong.'
        }),
    )

    @admin.display(description='Score')
    def score_display(self, obj):
        if obj.status != 'completed':
            return '—'
        t1 = f"{obj.team1_total}/{obj.team1_wickets}" if obj.team1_total is not None else '—'
        t2 = f"{obj.team2_total}/{obj.team2_wickets}" if obj.team2_total is not None else '—'
        return f"{t1} vs {t2}"

    @admin.display(description='Status')
    def status_badge(self, obj):
        if obj.status == 'completed':
            return format_html('<span style="color: #4ade80;">✓ Completed</span>')
        return format_html('<span style="color: #94a3b8;">○ Upcoming</span>')


# ──────────────────────────────────────────────────────────────
# Points Table (read-only in admin)
# ──────────────────────────────────────────────────────────────

@admin.register(PointsTableEntry)
class PointsTableEntryAdmin(admin.ModelAdmin):
    list_display = ['rank', 'team', 'stage', 'group', 'played', 'won', 'lost', 'tied', 'points', 'nrr']
    list_filter = ['stage__tournament', 'stage', 'group']
    search_fields = ['team__name']

    def has_add_permission(self, request):
        return False  # Auto-computed only

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
