from django.urls import path
from .views import (
    GitLabConfigView, SyncStafActivityView,
    StafActivitySummaryView, TeamActivitySummaryView,
    ActivityListView,
    ProjectListView, ProjectDetailView, SyncProjectsView, SyncProjectCommitsView
)
from .views import IssueCommentListView, IssueCommentStatsView, SyncIssueCommentsView, CommitMessageListView

urlpatterns = [
    path('config/', GitLabConfigView.as_view(), name='gitlab-config'),
    path('sync/', SyncStafActivityView.as_view(), name='sync-all'),
    path('sync/<int:staf_id>/', SyncStafActivityView.as_view(), name='sync-staf'),
    path('summary/team/', TeamActivitySummaryView.as_view(), name='team-summary'),
    path('summary/<int:staf_id>/', StafActivitySummaryView.as_view(), name='staf-summary'),
    path('activities/', ActivityListView.as_view(), name='activity-list'),
    path('projects/', ProjectListView.as_view(), name='project-list'),
    path('projects/sync/', SyncProjectsView.as_view(), name='sync-projects'),
    path('projects/sync-all-commits/', SyncProjectCommitsView.as_view(), name='sync-all-commits'),
    path('projects/<int:project_id>/', ProjectDetailView.as_view(), name='project-detail'),
    path('projects/<int:project_id>/sync/', SyncProjectCommitsView.as_view(), name='sync-project-commits'),
    path('commits/', CommitMessageListView.as_view(), name='commit-list'),
    path('comments/', IssueCommentListView.as_view(), name='comment-list'),
    path('comments/stats/', IssueCommentStatsView.as_view(), name='comment-stats'),
    path('comments/sync/', SyncIssueCommentsView.as_view(), name='sync-comments'),
]
