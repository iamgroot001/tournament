"""
Multi-tournament models for the WCL Tournament Tracker.

Key design:
- Tournament: top-level entity with is_active flag
- TournamentStage: defines available stages per tournament (dynamic)
- Team: per-tournament (FK to Tournament)
- Group: FK to TournamentStage
- Match: FK to TournamentStage, auto-computes points on save
- PointsTableEntry: computed from match results, FK to TournamentStage
"""

import random
from collections import defaultdict
from django.db import models
from django.core.exceptions import ValidationError


def parse_overs_to_float(overs_str):
    """Convert cricket overs string like '19.3' to float overs (19.5)."""
    if not overs_str:
        return 0.0
    s = str(overs_str).strip()
    if not s:
        return 0.0
    if '.' not in s:
        try:
            return float(s)
        except ValueError:
            return 0.0
    parts = s.split('.')
    try:
        return float(parts[0]) + float(parts[1]) / 6
    except (ValueError, IndexError):
        return 0.0


def cricket_overs_to_balls(value):
    """Convert cricket overs notation (e.g., 19.3) to total balls."""
    if value is None or value == '':
        return 0
    s = str(value).strip()
    if not s:
        return 0
    if '.' not in s:
        try:
            return int(float(s)) * 6
        except ValueError:
            return 0
    parts = s.split('.')
    if len(parts) != 2:
        return 0
    try:
        overs = int(parts[0])
        balls = int(parts[1])
    except ValueError:
        return 0
    return (overs * 6) + balls


WIN_POINTS = 2
TIE_POINTS = 1


# ──────────────────────────────────────────────────────────────
# Tournament
# ──────────────────────────────────────────────────────────────

class Tournament(models.Model):
    name = models.CharField(max_length=200, help_text="e.g., World T20 Champions League")
    edition = models.CharField(max_length=50, help_text="e.g., 2026-2027")
    is_active = models.BooleanField(
        default=False,
        help_text="Only one tournament should be active at a time. The active tournament is shown on the public site."
    )
    max_overs = models.IntegerField(
        default=20,
        help_text="Maximum overs per innings for this tournament (e.g., 5, 10, 20)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.edition})"

    def save(self, *args, **kwargs):
        # Ensure only one tournament is active
        if self.is_active:
            Tournament.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


# ──────────────────────────────────────────────────────────────
# Tournament Stage
# ──────────────────────────────────────────────────────────────

STAGE_TYPE_CHOICES = [
    ('group', 'Group Stage (teams in groups, round-robin)'),
    ('knockout', 'Knockout / Playoffs (bracket elimination)'),
    ('round_robin', 'Flat Round Robin (no groups, all vs all)'),
]


class TournamentStage(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='stages')
    name = models.CharField(max_length=60, help_text="e.g., Group Stage, Super 16, Super 8, Playoffs")
    slug = models.SlugField(max_length=60, help_text="URL slug, e.g., group-stage, super-16, super-8, playoffs")
    stage_type = models.CharField(max_length=20, choices=STAGE_TYPE_CHOICES, default='group')
    order = models.IntegerField(default=0, help_text="Display order (lower = earlier in tournament)")
    emoji = models.CharField(max_length=10, blank=True, default='🏏', help_text="Emoji icon for the nav")

    teams_count = models.IntegerField(default=0, help_text="Expected number of teams in this stage")
    groups_count = models.IntegerField(default=0, help_text="Number of groups (0 for flat/knockout stages)")
    qualify_count = models.IntegerField(default=4, help_text="Teams that qualify per group (for points table highlighting)")
    matches_per_pairing = models.IntegerField(
        default=1,
        help_text="How many times each team plays against every other team (1=single RR, 2=double RR)"
    )

    class Meta:
        ordering = ['tournament', 'order']
        unique_together = ['tournament', 'slug']

    def __str__(self):
        return f"{self.tournament.edition} — {self.name}"


# ──────────────────────────────────────────────────────────────
# Team
# ──────────────────────────────────────────────────────────────

class Team(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ['name']
        unique_together = ['tournament', 'name']

    def __str__(self):
        return self.name


# ──────────────────────────────────────────────────────────────
# Group + Membership
# ──────────────────────────────────────────────────────────────

class Group(models.Model):
    stage = models.ForeignKey(TournamentStage, on_delete=models.CASCADE, related_name='groups')
    name = models.CharField(max_length=30, help_text="e.g., Group A, Group B")
    teams = models.ManyToManyField(Team, through='GroupMembership', related_name='stage_groups')

    class Meta:
        ordering = ['stage', 'name']
        unique_together = ['stage', 'name']

    def __str__(self):
        return f"{self.stage.name} — {self.name}"


class GroupMembership(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)

    class Meta:
        unique_together = ['team', 'group']
        ordering = ['order']

    def __str__(self):
        return f"{self.team} in {self.group}"


# ──────────────────────────────────────────────────────────────
# Match
# ──────────────────────────────────────────────────────────────

MATCH_STATUS_CHOICES = [
    ('completed', 'Completed'),
    ('upcoming', 'Upcoming'),
]


class Match(models.Model):
    stage = models.ForeignKey(TournamentStage, on_delete=models.CASCADE, related_name='matches')
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, related_name='matches')
    match_number = models.IntegerField(default=0)

    team1 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='matches_as_team1')
    team2 = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='matches_as_team2')

    team1_total = models.IntegerField(null=True, blank=True, help_text="Team 1 total runs")
    team1_overs = models.CharField(max_length=10, blank=True, default='', help_text="e.g., 20, 19.3")
    team1_wickets = models.IntegerField(null=True, blank=True, help_text="Team 1 wickets lost")

    team2_total = models.IntegerField(null=True, blank=True, help_text="Team 2 total runs")
    team2_overs = models.CharField(max_length=10, blank=True, default='', help_text="e.g., 20, 19.3")
    team2_wickets = models.IntegerField(null=True, blank=True, help_text="Team 2 wickets lost")

    status = models.CharField(max_length=20, choices=MATCH_STATUS_CHOICES, default='upcoming')
    winner = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='matches_won')
    batting_first = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='matches_batted_first',
        help_text="Which team batted first. Set automatically if left blank on completed matches."
    )

    video_url = models.URLField(max_length=500, blank=True, null=True, help_text="Link to YouTube match video")

    class Meta:
        ordering = ['stage', 'match_number']
        verbose_name_plural = 'Matches'

    def __str__(self):
        return f"Match #{self.match_number}: {self.team1} vs {self.team2}"

    @property
    def is_completed(self):
        return self.status == 'completed'

    @property
    def is_tie(self):
        if not self.is_completed:
            return False
        return (self.team1_total is not None and self.team2_total is not None
                and self.team1_total == self.team2_total)

    @property
    def result_summary(self):
        if not self.is_completed or self.team1_total is None or self.team2_total is None:
            return "Upcoming"
        if self.is_tie:
            return "Match Tied"
        if not self.winner:
            return "Result TBD"

        w, w_total, w_wkts, w_ov, l, l_total, l_wkts, l_ov = self._winner_loser_data()

        if self.batting_first:
            batted_first = (self.batting_first == w)
        else:
            max_overs = self.stage.tournament.max_overs if self.stage_id else 20
            batted_first = self._infer_winner_batted_first(w_wkts, w_ov, l_wkts, l_ov, max_overs)

        if batted_first:
            return f"{w.name} won by {w_total - l_total} runs"
        else:
            return f"{w.name} won by {10 - (w_wkts or 0)} wickets"

    def _winner_loser_data(self):
        if self.team1_total >= self.team2_total:
            return (self.team1, self.team1_total, self.team1_wickets, self.team1_overs,
                    self.team2, self.team2_total, self.team2_wickets, self.team2_overs)
        return (self.team2, self.team2_total, self.team2_wickets, self.team2_overs,
                self.team1, self.team1_total, self.team1_wickets, self.team1_overs)

    @staticmethod
    def _infer_winner_batted_first(w_wkts, w_ov, l_wkts, l_ov, max_overs=20):
        w_overs = parse_overs_to_float(w_ov)
        if (w_wkts or 0) >= 10:
            return True
        if w_overs < max_overs and (w_wkts or 0) < 10:
            return False
        if (l_wkts or 0) >= 10:
            return True
        return True

    def clean(self):
        super().clean()
        if not self.stage_id:
            return
            
        max_overs = self.stage.tournament.max_overs
        
        if self.team1_overs:
            t1_ov = parse_overs_to_float(self.team1_overs)
            if t1_ov > max_overs:
                raise ValidationError({
                    'team1_overs': f"{self.team1.name}'s overs ({self.team1_overs}) cannot exceed the tournament limit of {max_overs}."
                })
                
        if self.team2_overs:
            t2_ov = parse_overs_to_float(self.team2_overs)
            if t2_ov > max_overs:
                raise ValidationError({
                    'team2_overs': f"{self.team2.name}'s overs ({self.team2_overs}) cannot exceed the tournament limit of {max_overs}."
                })

    def save(self, *args, **kwargs):
        # Auto-detect completed status
        if (self.team1_total is not None and self.team1_overs and self.team1_wickets is not None
                and self.team2_total is not None and self.team2_overs and self.team2_wickets is not None):
            self.status = 'completed'

            # Auto-set winner
            if self.team1_total > self.team2_total:
                self.winner = self.team1
            elif self.team2_total > self.team1_total:
                self.winner = self.team2
            else:
                self.winner = None  # tie

            # Auto-infer batting order if not set
            if not self.batting_first_id:
                bat_first = self._auto_batting_first()
                if bat_first:
                    self.batting_first = bat_first
        else:
            self.status = 'upcoming'
            self.winner = None

        super().save(*args, **kwargs)

        # Recompute points table for this stage
        if self.stage_id:
            recompute_points_table(self.stage)

        # Auto-schedule playoff matches for knockout stages
        if self.stage_id and self.stage.stage_type == 'knockout' and self.status == 'completed' and self.winner:
            self._auto_schedule_playoff()

    def _auto_batting_first(self):
        """Infer batting first team from score data."""
        t1_t = self.team1_total or 0
        t2_t = self.team2_total or 0
        t1_w = self.team1_wickets or 0
        t2_w = self.team2_wickets or 0
        t1_ov = parse_overs_to_float(self.team1_overs)
        t2_ov = parse_overs_to_float(self.team2_overs)
        max_overs = self.stage.tournament.max_overs if self.stage_id else 20

        if t1_t == t2_t:
            return self.team1

        if t1_t > t2_t:
            # Team1 won
            if t1_w >= 10:
                return self.team1  # All-out winner → batted first
            if t1_ov < max_overs and t1_w < 10:
                return self.team2  # Winner chased → other team batted first
            return self.team1
        else:
            # Team2 won
            if t2_w >= 10:
                return self.team2
            if t2_ov < max_overs and t2_w < 10:
                return self.team1
            return self.team2

    def _auto_schedule_playoff(self):
        """
        Auto-create/update downstream playoff matches based on results.

        IPL-style bracket convention (by match_number):
          1 = Qualifier 1  (1st vs 2nd)        → Winner to Final, Loser to Q2
          2 = Eliminator   (3rd vs 4th)         → Winner to Q2
          3 = Qualifier 2  (Loser Q1 vs Winner Elim) → Winner to Final
          4 = Final        (Winner Q1 vs Winner Q2)
        """
        stage = self.stage
        winner = self.winner
        loser = self.team2 if winner == self.team1 else self.team1

        if self.match_number == 1:
            # Q1 completed → Winner to Final (team1), Loser to Q2 (team1)
            # Create/update Q2 (match 3)
            q2, created = Match.objects.get_or_create(
                stage=stage, match_number=3,
                defaults={'team1': loser, 'team2': loser, 'status': 'upcoming'},
            )
            if not created:
                q2.team1 = loser
                q2.save(update_fields=['team1'])
            else:
                q2.team1 = loser
                q2.save(update_fields=['team1'])

            # Create/update Final (match 4)
            final, created = Match.objects.get_or_create(
                stage=stage, match_number=4,
                defaults={'team1': winner, 'team2': winner, 'status': 'upcoming'},
            )
            if not created:
                final.team1 = winner
                final.save(update_fields=['team1'])
            else:
                final.team1 = winner
                final.save(update_fields=['team1'])

        elif self.match_number == 2:
            # Eliminator completed → Winner to Q2 (team2)
            q2, created = Match.objects.get_or_create(
                stage=stage, match_number=3,
                defaults={'team1': winner, 'team2': winner, 'status': 'upcoming'},
            )
            if not created:
                q2.team2 = winner
                q2.save(update_fields=['team2'])
            else:
                q2.team2 = winner
                q2.save(update_fields=['team2'])

        elif self.match_number == 3:
            # Q2 completed → Winner to Final (team2)
            final, created = Match.objects.get_or_create(
                stage=stage, match_number=4,
                defaults={'team1': winner, 'team2': winner, 'status': 'upcoming'},
            )
            if not created:
                final.team2 = winner
                final.save(update_fields=['team2'])
            else:
                final.team2 = winner
                final.save(update_fields=['team2'])


# ──────────────────────────────────────────────────────────────
# Points Table
# ──────────────────────────────────────────────────────────────

class PointsTableEntry(models.Model):
    stage = models.ForeignKey(TournamentStage, on_delete=models.CASCADE, related_name='points_entries')
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, related_name='points_entries')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='points_entries')

    played = models.IntegerField(default=0)
    won = models.IntegerField(default=0)
    lost = models.IntegerField(default=0)
    tied = models.IntegerField(default=0)
    points = models.IntegerField(default=0)
    nrr = models.FloatField(default=0.0)
    rank = models.IntegerField(default=0)

    class Meta:
        ordering = ['stage', 'group', 'rank']
        unique_together = ['stage', 'team']

    def __str__(self):
        return f"{self.team} — Rank {self.rank}"


# ──────────────────────────────────────────────────────────────
# Points computation (called on Match save)
# ──────────────────────────────────────────────────────────────

def recompute_points_table(stage):
    """Recompute the entire points table for a given TournamentStage."""
    # Delete existing entries for this stage
    PointsTableEntry.objects.filter(stage=stage).delete()

    matches = Match.objects.filter(stage=stage, status='completed')
    groups = Group.objects.filter(stage=stage)

    # Build stats per (group_id, team_id)
    stats = defaultdict(lambda: {
        'played': 0, 'won': 0, 'lost': 0, 'tied': 0, 'points': 0,
        'runs_for': 0, 'runs_against': 0,
        'overs_faced_balls': 0, 'overs_bowled_balls': 0,
    })

    for m in matches:
        group_id = m.group_id or 0
        k1 = (group_id, m.team1_id)
        k2 = (group_id, m.team2_id)

        s1, s2 = stats[k1], stats[k2]
        s1['played'] += 1
        s2['played'] += 1

        t1_runs = m.team1_total or 0
        t2_runs = m.team2_total or 0
        t1_wkts = m.team1_wickets or 0
        t2_wkts = m.team2_wickets or 0
        t1_balls = cricket_overs_to_balls(m.team1_overs) or 0
        t2_balls = cricket_overs_to_balls(m.team2_overs) or 0

        full_quota_balls = (stage.tournament.max_overs if stage.tournament else 20) * 6

        # NRR: all-out teams use full quota
        t1_nrr_balls = full_quota_balls if t1_wkts >= 10 else t1_balls
        t2_nrr_balls = full_quota_balls if t2_wkts >= 10 else t2_balls

        s1['runs_for'] += t1_runs
        s1['runs_against'] += t2_runs
        s1['overs_faced_balls'] += t1_nrr_balls
        s1['overs_bowled_balls'] += t2_nrr_balls

        s2['runs_for'] += t2_runs
        s2['runs_against'] += t1_runs
        s2['overs_faced_balls'] += t2_nrr_balls
        s2['overs_bowled_balls'] += t1_nrr_balls

        if t1_runs > t2_runs:
            s1['won'] += 1
            s1['points'] += WIN_POINTS
            s2['lost'] += 1
        elif t2_runs > t1_runs:
            s2['won'] += 1
            s2['points'] += WIN_POINTS
            s1['lost'] += 1
        else:
            s1['tied'] += 1
            s2['tied'] += 1
            s1['points'] += TIE_POINTS
            s2['points'] += TIE_POINTS

    def calc_nrr(s):
        if s['overs_faced_balls'] <= 0 or s['overs_bowled_balls'] <= 0:
            return 0.0
        return (s['runs_for'] / (s['overs_faced_balls'] / 6)
                - s['runs_against'] / (s['overs_bowled_balls'] / 6))

    # Build entries for grouped stages
    if groups.exists():
        for group in groups:
            memberships = GroupMembership.objects.filter(group=group).select_related('team')
            entries = []
            for mem in memberships:
                key = (group.id, mem.team_id)
                s = stats.get(key, {
                    'played': 0, 'won': 0, 'lost': 0, 'tied': 0, 'points': 0,
                    'runs_for': 0, 'runs_against': 0,
                    'overs_faced_balls': 0, 'overs_bowled_balls': 0,
                })
                entries.append({
                    'team': mem.team, 'group': group,
                    'played': s['played'], 'won': s['won'], 'lost': s['lost'],
                    'tied': s['tied'], 'points': s['points'],
                    'nrr': round(calc_nrr(s), 3),
                })

            entries.sort(key=lambda x: (-x['points'], -x['nrr'], -x['won'], x['team'].name))
            for rank, e in enumerate(entries, 1):
                PointsTableEntry.objects.create(
                    stage=stage, group=e['group'], team=e['team'],
                    played=e['played'], won=e['won'], lost=e['lost'],
                    tied=e['tied'], points=e['points'], nrr=e['nrr'], rank=rank,
                )
    else:
        # Flat round-robin / knockout — all teams in one table
        tournament = stage.tournament
        # Get all teams that have matches in this stage
        team_ids = set()
        for m in matches:
            team_ids.add(m.team1_id)
            team_ids.add(m.team2_id)

        # Also add teams from matches (including upcoming)
        all_stage_matches = Match.objects.filter(stage=stage)
        for m in all_stage_matches:
            team_ids.add(m.team1_id)
            team_ids.add(m.team2_id)

        teams = Team.objects.filter(id__in=team_ids)
        entries = []
        for team in teams:
            key = (0, team.id)
            s = stats.get(key, {
                'played': 0, 'won': 0, 'lost': 0, 'tied': 0, 'points': 0,
                'runs_for': 0, 'runs_against': 0,
                'overs_faced_balls': 0, 'overs_bowled_balls': 0,
            })
            entries.append({
                'team': team, 'group': None,
                'played': s['played'], 'won': s['won'], 'lost': s['lost'],
                'tied': s['tied'], 'points': s['points'],
                'nrr': round(calc_nrr(s), 3),
            })

        entries.sort(key=lambda x: (-x['points'], -x['nrr'], -x['won'], x['team'].name))
        for rank, e in enumerate(entries, 1):
            PointsTableEntry.objects.create(
                stage=stage, group=None, team=e['team'],
                played=e['played'], won=e['won'], lost=e['lost'],
                tied=e['tied'], points=e['points'], nrr=e['nrr'], rank=rank,
            )


# ──────────────────────────────────────────────────────────────
# Auto-Qualification: promote teams to next stage
# ──────────────────────────────────────────────────────────────

def promote_qualified_teams(source_stage):
    """
    Promote qualified teams from source_stage to the next stage in the tournament.

    Logic:
    - For grouped stages: top `qualify_count` teams per group advance.
    - For flat round-robin: top `qualify_count` teams overall advance.
    - Next stage groups: if the next stage has groups, distribute teams
      using serpentine seeding (1st → Group A, 2nd → Group B, 3rd → Group B,
      4th → Group A, etc.) with randomised order within the same seed rank.
    - For flat next stage: just create points entries / group memberships.

    Returns: (success: bool, message: str, qualified_teams: list[Team])
    """
    tournament = source_stage.tournament

    # Find the next stage (by order)
    next_stage = TournamentStage.objects.filter(
        tournament=tournament,
        order__gt=source_stage.order,
    ).order_by('order').first()

    if not next_stage:
        return False, "No next stage found in this tournament.", []

    qualify_count = source_stage.qualify_count or 0
    if qualify_count <= 0:
        return False, f"Stage '{source_stage.name}' has no qualify_count set.", []

    # ── Gather qualified teams sorted by rank ──
    qualified_teams = []

    if source_stage.stage_type == 'group':
        # Top N per group
        groups = source_stage.groups.order_by('name')
        for group in groups:
            entries = PointsTableEntry.objects.filter(
                stage=source_stage, group=group,
            ).order_by('rank')[:qualify_count]
            for entry in entries:
                qualified_teams.append({
                    'team': entry.team,
                    'rank': entry.rank,
                    'points': entry.points,
                    'nrr': entry.nrr,
                    'source_group': group.name,
                })

    elif source_stage.stage_type == 'round_robin':
        # Top N overall
        entries = PointsTableEntry.objects.filter(
            stage=source_stage,
        ).order_by('rank')[:qualify_count]
        for entry in entries:
            qualified_teams.append({
                'team': entry.team,
                'rank': entry.rank,
                'points': entry.points,
                'nrr': entry.nrr,
                'source_group': None,
            })
    else:
        return False, f"Cannot promote from knockout stage '{source_stage.name}'.", []

    if not qualified_teams:
        return False, f"No qualified teams found. Are there completed matches in '{source_stage.name}'?", []

    # ── Clear existing data in the next stage ──
    GroupMembership.objects.filter(group__stage=next_stage).delete()
    PointsTableEntry.objects.filter(stage=next_stage).delete()

    # ── Assign teams to the next stage ──
    if next_stage.stage_type == 'group':
        # Distribute into next stage's groups using serpentine seeding
        next_groups = list(next_stage.groups.order_by('name'))

        if not next_groups:
            # Auto-create groups if they don't exist
            num_groups = next_stage.groups_count or 2
            for i in range(num_groups):
                group_name = f"Group {chr(65 + i)}"
                g, _ = Group.objects.get_or_create(
                    stage=next_stage, name=group_name,
                )
                next_groups.append(g)

        num_groups = len(next_groups)

        # Sort qualified teams by rank, randomise within same rank
        # Group by seed position (rank within source group)
        seed_buckets = defaultdict(list)
        for qt in qualified_teams:
            seed_buckets[qt['rank']].append(qt)

        # Shuffle each bucket for random group assignment
        for rank_key in seed_buckets:
            random.shuffle(seed_buckets[rank_key])

        # Serpentine distribution: seed 1 → A, B, C, D; seed 2 → D, C, B, A; etc.
        order_counter = 0
        for rank_idx, rank_key in enumerate(sorted(seed_buckets.keys())):
            bucket = seed_buckets[rank_key]
            if rank_idx % 2 == 0:
                group_order = list(range(num_groups))
            else:
                group_order = list(range(num_groups - 1, -1, -1))

            for i, qt in enumerate(bucket):
                group_idx = group_order[i % num_groups]
                target_group = next_groups[group_idx]
                GroupMembership.objects.create(
                    team=qt['team'],
                    group=target_group,
                    order=order_counter,
                )
                order_counter += 1

        # Create initial points table entries for the next stage
        for group in next_groups:
            memberships = GroupMembership.objects.filter(group=group).select_related('team')
            for rank, mem in enumerate(memberships, 1):
                PointsTableEntry.objects.create(
                    stage=next_stage, group=group, team=mem.team,
                    played=0, won=0, lost=0, tied=0, points=0, nrr=0.0,
                    rank=rank,
                )

    elif next_stage.stage_type in ('round_robin', 'knockout'):
        # Flat assignment — all qualified teams go to next stage
        # Sort by overall ranking (points desc, nrr desc), then randomise same-ranked
        qualified_teams.sort(key=lambda x: (-x['points'], -x['nrr']))

        for rank, qt in enumerate(qualified_teams, 1):
            PointsTableEntry.objects.create(
                stage=next_stage, group=None, team=qt['team'],
                played=0, won=0, lost=0, tied=0, points=0, nrr=0.0,
                rank=rank,
            )

    team_names = [qt['team'].name for qt in qualified_teams]
    return True, f"Promoted {len(qualified_teams)} teams to '{next_stage.name}': {', '.join(team_names)}", [qt['team'] for qt in qualified_teams]


# ──────────────────────────────────────────────────────────────
# Auto Fixture Generation (Tie-Sheet)
# ──────────────────────────────────────────────────────────────

def generate_fixtures(stage):
    """
    Auto-generate all match fixtures for a stage based on its type and teams.

    Matches are interleaved across groups so the tie-sheet alternates:
    Match 1 → Group C, Match 2 → Group A, Match 3 → Group D, etc.

    - group: Round-robin pairings per group, interleaved across groups.
    - round_robin: All teams vs all, shuffled.
    - knockout: Seeded bracket (1v4, 2v3 for 4 teams).

    Returns: (success: bool, message: str)
    """
    from itertools import combinations

    # Don't overwrite existing matches
    existing = stage.matches.count()
    if existing > 0:
        return False, f"Stage '{stage.name}' already has {existing} matches. Delete them first to regenerate."

    matches_per_pairing = stage.matches_per_pairing or 1

    if stage.stage_type == 'group':
        # ── Grouped round-robin with interleaved scheduling ──
        groups = stage.groups.order_by('name')
        if not groups.exists():
            return False, f"No groups found for '{stage.name}'. Create groups and assign teams first."

        # Step 1: Build all pairings per group
        group_pairings = {}  # group → list of (team1, team2) across all rounds
        for group in groups:
            teams = list(group.teams.order_by('groupmembership__order'))
            if len(teams) < 2:
                continue
            pairings = list(combinations(teams, 2))
            # Repeat for matches_per_pairing (e.g., 2x round-robin)
            all_pairings = []
            for _ in range(matches_per_pairing):
                all_pairings.extend(pairings)
            group_pairings[group] = all_pairings

        if not group_pairings:
            return False, f"No teams found in any group of '{stage.name}'."

        # Step 2: Build interleaved match list
        # Use round-robin across groups: take 1 match from each group,
        # shuffle group order each round, repeat until all matches done.
        all_matches = []  # list of (group, team1, team2)
        group_list = list(group_pairings.keys())
        group_indices = {g: 0 for g in group_list}

        while True:
            # Collect one match from each group that still has matches
            round_matches = []
            for g in group_list:
                idx = group_indices[g]
                if idx < len(group_pairings[g]):
                    t1, t2 = group_pairings[g][idx]
                    round_matches.append((g, t1, t2))
                    group_indices[g] += 1

            if not round_matches:
                break

            # Shuffle this round so groups appear in random order
            random.shuffle(round_matches)
            all_matches.extend(round_matches)

        # Step 3: Create Match objects with sequential match numbers
        for match_num, (group, t1, t2) in enumerate(all_matches, 1):
            Match.objects.create(
                stage=stage,
                group=group,
                match_number=match_num,
                team1=t1,
                team2=t2,
                status='upcoming',
            )

        return True, f"Generated {len(all_matches)} interleaved fixtures across {len(group_pairings)} groups in '{stage.name}'."

    elif stage.stage_type == 'round_robin':
        # ── Flat round-robin, shuffled ──
        team_ids = set()
        pts = PointsTableEntry.objects.filter(stage=stage).values_list('team_id', flat=True)
        team_ids.update(pts)

        if not team_ids:
            return False, f"No teams found for '{stage.name}'. Promote teams from the previous stage first."

        teams = list(Team.objects.filter(id__in=team_ids).order_by('name'))
        if len(teams) < 2:
            return False, f"Need at least 2 teams for round-robin. Found {len(teams)}."

        pairings = list(combinations(teams, 2))
        all_matches = []
        for _ in range(matches_per_pairing):
            round_pairings = list(pairings)
            random.shuffle(round_pairings)
            all_matches.extend(round_pairings)

        for match_num, (t1, t2) in enumerate(all_matches, 1):
            Match.objects.create(
                stage=stage,
                group=None,
                match_number=match_num,
                team1=t1,
                team2=t2,
                status='upcoming',
            )

        return True, f"Generated {len(all_matches)} shuffled fixtures for '{stage.name}' ({len(teams)} teams, {matches_per_pairing}x round-robin)."

    elif stage.stage_type == 'knockout':
        # ── Seeded knockout bracket ──
        entries = PointsTableEntry.objects.filter(stage=stage).order_by('rank')
        teams = [e.team for e in entries]

        if len(teams) < 2:
            return False, f"Need at least 2 teams for knockout. Found {len(teams)}."

        match_number = 1
        if len(teams) == 4:
            # IPL-style playoff bracket — only create Q1 + Eliminator.
            # Q2 and Final are auto-scheduled when Q1/Eliminator results are entered.
            # Match 1 = Qualifier 1: 1st vs 2nd
            Match.objects.create(
                stage=stage, group=None, match_number=1,
                team1=teams[0], team2=teams[1], status='upcoming',
            )
            # Match 2 = Eliminator: 3rd vs 4th
            Match.objects.create(
                stage=stage, group=None, match_number=2,
                team1=teams[2], team2=teams[3], status='upcoming',
            )
            return True, (
                f"Generated IPL-style playoff bracket for '{stage.name}': "
                f"Q1 ({teams[0].name} vs {teams[1].name}), "
                f"Eliminator ({teams[2].name} vs {teams[3].name}). "
                f"Q2 and Final will auto-schedule when results are entered."
            )

        elif len(teams) == 2:
            Match.objects.create(
                stage=stage, group=None, match_number=match_number,
                team1=teams[0], team2=teams[1], status='upcoming',
            )
            return True, f"Generated 1 final fixture for '{stage.name}'."

        else:
            # General knockout: seeded pairs (1v last, 2v second-last, etc.)
            total_created = 0
            mid = len(teams) // 2
            for i in range(mid):
                Match.objects.create(
                    stage=stage, group=None, match_number=match_number,
                    team1=teams[i], team2=teams[len(teams) - 1 - i], status='upcoming',
                )
                match_number += 1
                total_created += 1
            return True, f"Generated {total_created} knockout fixtures for '{stage.name}'."

    return False, f"Unknown stage type: {stage.stage_type}"
