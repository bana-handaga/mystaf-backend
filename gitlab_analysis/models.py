from django.db import models
from accounts.models import StafUser

class GitLabConfig(models.Model):
    """Konfigurasi koneksi GitLab"""
    url = models.URLField(default='https://gitlab.ums.ac.id')
    private_token = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Konfigurasi GitLab'

    def __str__(self):
        return self.url

class GitLabActivity(models.Model):
    """Aktivitas programmer di GitLab"""
    ACTIVITY_TYPES = [
        ('push', 'Push'),
        ('merge_request', 'Merge Request'),
        ('issue', 'Issue'),
        ('comment', 'Comment'),
        ('pipeline', 'Pipeline'),
    ]
    staf = models.ForeignKey(StafUser, on_delete=models.CASCADE, related_name='gitlab_activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    project_name = models.CharField(max_length=200)
    project_id = models.IntegerField()
    description = models.TextField(blank=True)
    commits_count = models.IntegerField(default=0)
    additions = models.IntegerField(default=0)
    deletions = models.IntegerField(default=0)
    activity_date = models.DateTimeField()
    raw_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Aktivitas GitLab'
        verbose_name_plural = 'Aktivitas GitLab'
        ordering = ['-activity_date']
        indexes = [
            models.Index(fields=['staf', 'activity_date']),
            models.Index(fields=['activity_type']),
        ]

    def __str__(self):
        return f"{self.staf.username} - {self.activity_type} - {self.activity_date.date()}"

class ActivitySummary(models.Model):
    """Ringkasan aktivitas mingguan/bulanan"""
    staf = models.ForeignKey(StafUser, on_delete=models.CASCADE, related_name='activity_summaries')
    period_type = models.CharField(max_length=10, choices=[('weekly', 'Mingguan'), ('monthly', 'Bulanan')])
    period_start = models.DateField()
    period_end = models.DateField()
    total_commits = models.IntegerField(default=0)
    total_push_events = models.IntegerField(default=0)
    total_merge_requests = models.IntegerField(default=0)
    total_issues = models.IntegerField(default=0)
    total_comments = models.IntegerField(default=0)
    total_additions = models.IntegerField(default=0)
    total_deletions = models.IntegerField(default=0)
    active_projects = models.JSONField(default=list)
    score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['staf', 'period_type', 'period_start']
        ordering = ['-period_start']


class GitLabProject(models.Model):
    """Cache data project dari GitLab"""
    project_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=300)
    name_with_namespace = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    web_url = models.URLField()
    namespace = models.CharField(max_length=200, blank=True)
    visibility = models.CharField(max_length=20, default='private')
    default_branch = models.CharField(max_length=100, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    star_count = models.IntegerField(default=0)
    forks_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Proyek GitLab'
        verbose_name_plural = 'Proyek GitLab'
        ordering = ['name']

    def __str__(self):
        return self.name_with_namespace


class ProjectCommit(models.Model):
    """Data commit per orang per project"""
    project = models.ForeignKey(GitLabProject, on_delete=models.CASCADE, related_name='commits')
    staf = models.ForeignKey(StafUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='project_commits')
    gitlab_username = models.CharField(max_length=100)
    author_name = models.CharField(max_length=200)
    author_email = models.CharField(max_length=200, blank=True)
    commit_hash = models.CharField(max_length=40)
    message = models.TextField(blank=True)
    committed_at = models.DateTimeField()
    additions = models.IntegerField(default=0)
    deletions = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['project', 'commit_hash']
        ordering = ['-committed_at']
        indexes = [
            models.Index(fields=['project', 'committed_at']),
            models.Index(fields=['gitlab_username']),
        ]

    def __str__(self):
        return f"{self.gitlab_username} @ {self.project.name} ({self.committed_at.date()})"


class IssueComment(models.Model):
    """Komentar pada Issue atau Commit GitLab"""
    COMMENT_TYPES = [
        ('issue', 'Issue'),
        ('commit', 'Commit'),
    ]
    project = models.ForeignKey(GitLabProject, on_delete=models.CASCADE, related_name='issue_comments')
    staf = models.ForeignKey(StafUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='issue_comments')
    comment_type = models.CharField(max_length=10, choices=COMMENT_TYPES, default='issue')
    # Issue fields (nullable for commit comments)
    issue_id = models.IntegerField(null=True, blank=True)
    issue_iid = models.IntegerField(null=True, blank=True)
    issue_title = models.CharField(max_length=500, blank=True)
    issue_url = models.URLField(blank=True)
    issue_state = models.CharField(max_length=20, blank=True)
    # Commit fields (nullable for issue comments)
    commit_sha = models.CharField(max_length=40, blank=True)
    commit_message = models.CharField(max_length=500, blank=True)
    commit_url = models.URLField(blank=True)
    line_code = models.CharField(max_length=100, blank=True)
    # Common fields
    note_id = models.CharField(max_length=100)  # Changed to CharField to support both int and sha-based IDs
    author_username = models.CharField(max_length=100)
    author_name = models.CharField(max_length=200)
    body = models.TextField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(null=True, blank=True)
    is_system = models.BooleanField(default=False)

    class Meta:
        unique_together = ['project', 'note_id', 'comment_type']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'comment_type']),
            models.Index(fields=['author_username', 'created_at']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Komentar'
        verbose_name_plural = 'Komentar'

    def __str__(self):
        if self.comment_type == 'issue':
            return f"{self.author_username} on Issue #{self.issue_iid} - {self.project.name}"
        return f"{self.author_username} on Commit {self.commit_sha[:8]} - {self.project.name}"
