from django.contrib import admin
from .models import GitLabConfig, GitLabActivity, ActivitySummary, GitLabProject, ProjectCommit, IssueComment

@admin.register(GitLabConfig)
class GitLabConfigAdmin(admin.ModelAdmin):
    list_display = ['url', 'is_active', 'created_at']

@admin.register(GitLabActivity)
class GitLabActivityAdmin(admin.ModelAdmin):
    list_display = ['staf', 'activity_type', 'project_name', 'commits_count', 'activity_date']
    list_filter = ['activity_type', 'staf']
    search_fields = ['staf__username', 'project_name']
    date_hierarchy = 'activity_date'

@admin.register(ActivitySummary)
class ActivitySummaryAdmin(admin.ModelAdmin):
    list_display = ['staf', 'period_type', 'period_start', 'period_end', 'total_commits', 'score']
    list_filter = ['period_type', 'staf']

@admin.register(GitLabProject)
class GitLabProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'namespace', 'visibility', 'last_activity_at', 'synced_at']
    search_fields = ['name', 'name_with_namespace', 'namespace']

@admin.register(ProjectCommit)
class ProjectCommitAdmin(admin.ModelAdmin):
    list_display = ['project', 'gitlab_username', 'author_name', 'committed_at']
    list_filter = ['project']
    search_fields = ['gitlab_username', 'author_name', 'project__name']

@admin.register(IssueComment)
class IssueCommentAdmin(admin.ModelAdmin):
    list_display = ['author_username', 'issue_title', 'project', 'issue_state', 'created_at']
    list_filter = ['issue_state', 'project']
    search_fields = ['author_username', 'author_name', 'issue_title', 'body']
    date_hierarchy = 'created_at'
