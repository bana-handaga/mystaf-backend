from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from accounts.models import StafUser
from .models import GitLabConfig, GitLabActivity
from .serializers import (
    GitLabConfigSerializer, GitLabConfigWriteSerializer,
    GitLabActivitySerializer
)
from .services import GitLabService

class GitLabConfigView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        config = GitLabConfig.objects.filter(is_active=True).first()
        if not config:
            return Response({'detail': 'Belum ada konfigurasi GitLab.'}, status=404)
        return Response(GitLabConfigSerializer(config).data)

    def post(self, request):
        serializer = GitLabConfigWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = serializer.save()
        return Response(GitLabConfigSerializer(config).data, status=201)

class SyncStafActivityView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, staf_id=None):
        days = int(request.data.get('days', 30))
        if staf_id:
            staf = get_object_or_404(StafUser, id=staf_id)
            staf_list = [staf]
        else:
            staf_list = StafUser.objects.filter(role='programmer', is_active=True)

        service = GitLabService()
        results = []
        for staf in staf_list:
            try:
                count = service.sync_staf_activity(staf, days)
                results.append({'staf': staf.username, 'synced': count, 'status': 'ok'})
            except Exception as e:
                results.append({'staf': staf.username, 'error': str(e), 'status': 'error'})

        return Response({'results': results})

class StafActivitySummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, staf_id):
        staf = get_object_or_404(StafUser, id=staf_id)
        days = int(request.query_params.get('days', 30))
        service = GitLabService()
        try:
            summary = service.get_activity_summary(staf, days)
            return Response(summary)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

class TeamActivitySummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        service = GitLabService()
        try:
            summary = service.get_team_summary(days)
            return Response(summary)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

class ActivityListView(generics.ListAPIView):
    serializer_class = GitLabActivitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = GitLabActivity.objects.select_related('staf')
        staf_id = self.request.query_params.get('staf_id')
        activity_type = self.request.query_params.get('type')
        days = self.request.query_params.get('days', 30)
        if staf_id:
            qs = qs.filter(staf_id=staf_id)
        if activity_type:
            qs = qs.filter(activity_type=activity_type)
        from django.utils import timezone
        from datetime import timedelta
        since = timezone.now() - timedelta(days=int(days))
        return qs.filter(activity_date__gte=since)


from .models import GitLabProject, ProjectCommit

class ProjectListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db.models import Count, Q
        days = int(request.query_params.get('days', 30))
        search = request.query_params.get('search', '')
        from django.utils import timezone
        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)

        qs = GitLabProject.objects.annotate(
            commit_count=Count('commits', filter=Q(commits__committed_at__gte=since)),
            contributor_count=Count('commits__gitlab_username', filter=Q(commits__committed_at__gte=since), distinct=True),
        ).filter(last_activity_at__gte=since)

        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(name_with_namespace__icontains=search) |
                Q(namespace__icontains=search)
            )

        qs = qs.order_by('-commit_count', '-last_activity_at')

        results = [{
            'id': p.id,
            'project_id': p.project_id,
            'name': p.name,
            'name_with_namespace': p.name_with_namespace,
            'namespace': p.namespace,
            'web_url': p.web_url,
            'visibility': p.visibility,
            'last_activity_at': str(p.last_activity_at.date()) if p.last_activity_at else None,
            'commit_count': p.commit_count,
            'contributor_count': p.contributor_count,
        } for p in qs]

        return Response({'count': len(results), 'results': results})


class ProjectDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, project_id):
        from django.db.models import Count
        days = int(request.query_params.get('days', 30))
        project = get_object_or_404(GitLabProject, id=project_id)
        service = GitLabService()
        contributors = service.get_project_contributors(project, days)
        return Response({
            'project': {
                'id': project.id,
                'project_id': project.project_id,
                'name': project.name,
                'name_with_namespace': project.name_with_namespace,
                'namespace': project.namespace,
                'web_url': project.web_url,
                'last_activity_at': str(project.last_activity_at.date()) if project.last_activity_at else None,
            },
            'days': days,
            'total_commits': sum(c['total_commits'] for c in contributors),
            'contributors': contributors,
        })


class SyncProjectsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.utils import timezone
        from datetime import timedelta
        days = int(request.data.get('days', 30))
        service = GitLabService()
        try:
            count = service.sync_projects()
            # Auto-sync commits for projects with recent activity but no commits in DB
            since = timezone.now() - timedelta(days=days)
            from .models import GitLabProject
            from django.db.models import Count
            new_projects = GitLabProject.objects.annotate(
                commit_count=Count('commits')
            ).filter(commit_count=0, last_activity_at__gte=since)
            commit_results = []
            for proj in new_projects:
                try:
                    new_commits = service.sync_project_commits(proj, days)
                    if new_commits > 0:
                        commit_results.append(f'{proj.name}: {new_commits} commits')
                except Exception:
                    pass
            msg = f'{count} proyek disinkronkan.'
            if commit_results:
                msg += f' Auto-sync commits: {", ".join(commit_results)}.'
            return Response({'message': msg})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class SyncProjectCommitsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, project_id=None):
        days = int(request.data.get('days', 30))
        service = GitLabService()
        results = []

        if project_id:
            projects = [get_object_or_404(GitLabProject, id=project_id)]
        else:
            projects = GitLabProject.objects.all()

        for proj in projects:
            try:
                count = service.sync_project_commits(proj, days)
                results.append({'project': proj.name, 'new_commits': count, 'status': 'ok'})
            except Exception as e:
                results.append({'project': proj.name, 'new_commits': 0, 'error': str(e), 'status': 'error'})

        return Response({'results': results})


from .models import IssueComment

COMMIT_CATEGORIES = {
    'fix':      ['fix', 'bug', 'error', 'resolve', 'patch', 'hotfix', 'repair', 'revert'],
    'feature':  ['add', 'feat', 'feature', 'implement', 'new', 'create', 'build', 'init'],
    'refactor': ['refactor', 'clean', 'improve', 'optimize', 'restructure', 'enhance', 'update', 'upgrade'],
    'docs':     ['doc', 'readme', 'comment', 'docs', 'documentation', 'changelog'],
    'config':   ['config', 'setup', 'env', 'setting', 'deploy', 'ci', 'cd', 'workflow', 'docker'],
    'test':     ['test', 'spec', 'unit', 'integration', 'testing', 'coverage'],
    'remove':   ['remove', 'delete', 'drop', 'cleanup', 'clean up', 'deprecated'],
    'merge':    ['merge', 'pull request', 'rebase', 'sync'],
}

def classify_commit(message):
    msg = (message or '').lower()
    for cat, keywords in COMMIT_CATEGORIES.items():
        for kw in keywords:
            if kw in msg:
                return cat
    return 'other'


class CommitAnalysisView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.utils import timezone
        from datetime import timedelta

        days = int(request.query_params.get('days', 30))
        staf_id = request.query_params.get('staf_id', '')
        project_id = request.query_params.get('project_id', '')
        since = timezone.now() - timedelta(days=days)

        qs = ProjectCommit.objects.filter(
            committed_at__gte=since
        ).select_related('project', 'staf').order_by('gitlab_username', 'project')

        if staf_id:
            qs = qs.filter(staf_id=staf_id)
        if project_id:
            qs = qs.filter(project_id=project_id)

        all_cats = list(COMMIT_CATEGORIES.keys()) + ['other']
        category_totals = {c: 0 for c in all_cats}
        staf_project_map = {}

        for commit in qs:
            cat = classify_commit(commit.message)
            category_totals[cat] += 1
            key = f"{commit.gitlab_username}__{commit.project_id}"
            if key not in staf_project_map:
                staf_project_map[key] = {
                    'staf_name': commit.author_name,
                    'staf_username': commit.gitlab_username,
                    'staf_id': commit.staf.id if commit.staf else None,
                    'project_name': commit.project.name,
                    'project_id': commit.project.id,
                    'total': 0,
                    'categories': {c: 0 for c in all_cats},
                    'dominant': '',
                }
            staf_project_map[key]['total'] += 1
            staf_project_map[key]['categories'][cat] += 1

        # Determine dominant category per staf-project
        for v in staf_project_map.values():
            v['dominant'] = max(v['categories'], key=lambda c: v['categories'][c])

        results = sorted(staf_project_map.values(), key=lambda x: x['total'], reverse=True)

        # Per-staf summary (across all projects)
        staf_summary = {}
        for v in results:
            u = v['staf_username']
            if u not in staf_summary:
                staf_summary[u] = {
                    'staf_name': v['staf_name'],
                    'staf_username': u,
                    'staf_id': v['staf_id'],
                    'total': 0,
                    'categories': {c: 0 for c in all_cats},
                    'projects': 0,
                }
            staf_summary[u]['total'] += v['total']
            staf_summary[u]['projects'] += 1
            for c in all_cats:
                staf_summary[u]['categories'][c] += v['categories'][c]

        staf_list = sorted(staf_summary.values(), key=lambda x: x['total'], reverse=True)

        return Response({
            'total_commits': sum(category_totals.values()),
            'category_totals': category_totals,
            'by_staf': staf_list,
            'by_staf_project': results,
        })


class CommitMessageListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db.models import Q
        from django.utils import timezone
        from datetime import timedelta

        days = int(request.query_params.get('days', 30))
        search = request.query_params.get('search', '')
        project_id = request.query_params.get('project_id', '')
        staf_id = request.query_params.get('staf_id', '')
        since = timezone.now() - timedelta(days=days)

        qs = ProjectCommit.objects.filter(
            committed_at__gte=since
        ).select_related('project', 'staf').order_by('-committed_at')

        if search:
            qs = qs.filter(
                Q(message__icontains=search) |
                Q(author_name__icontains=search) |
                Q(gitlab_username__icontains=search)
            )
        if project_id:
            qs = qs.filter(project_id=project_id)
        if staf_id:
            qs = qs.filter(staf_id=staf_id)

        results = [{
            'id': c.id,
            'commit_hash': c.commit_hash[:8],
            'message': c.message,
            'author_name': c.author_name,
            'author_username': c.gitlab_username,
            'staf_id': c.staf.id if c.staf else None,
            'project_id': c.project.id,
            'project_name': c.project.name,
            'project_web_url': c.project.web_url,
            'additions': c.additions,
            'deletions': c.deletions,
            'committed_at': c.committed_at.strftime('%Y-%m-%d %H:%M'),
        } for c in qs[:500]]

        return Response({'count': len(results), 'results': results})


class IssueCommentListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.db.models import Q
        from django.utils import timezone
        from datetime import timedelta

        days = int(request.query_params.get('days', 30))
        search = request.query_params.get('search', '')
        project_id = request.query_params.get('project_id', '')
        author = request.query_params.get('author', '')
        issue_state = request.query_params.get('issue_state', '')
        comment_type = request.query_params.get('comment_type', '')
        since = timezone.now() - timedelta(days=days)

        qs = IssueComment.objects.filter(
            created_at__gte=since, is_system=False
        ).select_related('project', 'staf').order_by('-created_at')

        if search:
            qs = qs.filter(
                Q(issue_title__icontains=search) |
                Q(body__icontains=search) |
                Q(author_username__icontains=search) |
                Q(author_name__icontains=search)
            )
        if project_id:
            qs = qs.filter(project_id=project_id)
        if author:
            qs = qs.filter(author_username__icontains=author)
        if issue_state:
            qs = qs.filter(issue_state=issue_state)
        if comment_type:
            qs = qs.filter(comment_type=comment_type)

        results = [{
            'id': c.id,
            'project_name': c.project.name,
            'project_id': c.project.id,
            'comment_type': c.comment_type,
            'commit_sha': c.commit_sha[:8] if c.commit_sha else '',
            'commit_message': c.commit_message[:80] if c.commit_message else '',
            'commit_url': c.commit_url,
            'issue_iid': c.issue_iid,
            'issue_title': c.issue_title,
            'issue_url': c.issue_url,
            'issue_state': c.issue_state,
            'author_username': c.author_username,
            'author_name': c.author_name,
            'staf_id': c.staf.id if c.staf else None,
            'body': c.body[:200],
            'created_at': c.created_at.strftime('%Y-%m-%d %H:%M'),
        } for c in qs[:500]]

        return Response({'count': len(results), 'results': results})


class GitLabDiagnosticView(APIView):
    """Test koneksi GitLab dan tampilkan info debug."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        config = GitLabConfig.objects.filter(is_active=True).first()
        if not config:
            return Response({'status': 'error', 'message': 'Konfigurasi GitLab belum diatur.'}, status=400)

        try:
            service = GitLabService()
            current_user = service.gl.auth()
            gl_user = service.gl.users.get(service.gl.auth())
            server_version = service.gl.version()
            project_count = GitLabProject.objects.count()
            from .models import ProjectCommit
            commit_count = ProjectCommit.objects.count()
            return Response({
                'status': 'ok',
                'gitlab_url': config.url,
                'gitlab_version': server_version,
                'project_count_db': project_count,
                'commit_count_db': commit_count,
            })
        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=400)


class ManagementReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .report_service import build_team_report
        days = int(request.query_params.get('days', 30))
        try:
            report = build_team_report(days)
            return Response(report)
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class IssueCommentStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        service = GitLabService()
        try:
            stats = service.get_comment_stats(days)
            return Response(stats)
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class SyncIssueCommentsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        days = int(request.data.get('days', 30))
        project_id = request.data.get('project_id')
        service = GitLabService()

        if project_id:
            projects = GitLabProject.objects.filter(id=project_id)
        else:
            projects = GitLabProject.objects.all()

        results = []
        for proj in projects:
            try:
                count = service.sync_issue_comments(proj, days)
                commit_count = service.sync_commit_comments(proj, days)
                total_count = count + commit_count
                if total_count > 0:
                    results.append({
                        'project': proj.name,
                        'new_issue_comments': count,
                        'new_commit_comments': commit_count,
                        'new_comments': total_count,
                        'status': 'ok',
                    })
            except Exception as e:
                results.append({'project': proj.name, 'error': str(e), 'status': 'error'})

        total = sum(r.get('new_comments', 0) for r in results)
        return Response({'total_new': total, 'results': results})
