import gitlab
import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from django.utils import timezone
from .models import GitLabConfig, GitLabActivity, ActivitySummary, GitLabProject
from accounts.models import StafUser

logger = logging.getLogger(__name__)

class GitLabService:
    def __init__(self):
        config = GitLabConfig.objects.filter(is_active=True).first()
        if not config:
            raise ValueError("Konfigurasi GitLab belum diatur.")
        self.gl = gitlab.Gitlab(config.url, private_token=config.private_token)
        self.gl.auth()

    def get_user_events(self, gitlab_username: str, days: int = 30):
        """Ambil events aktivitas user dari GitLab"""
        try:
            user = self.gl.users.list(username=gitlab_username)[0]
        except (IndexError, Exception) as e:
            raise ValueError(f"User GitLab '{gitlab_username}' tidak ditemukan: {e}")

        since = (datetime.now(dt_timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
        events = user.events.list(after=since, all=True)
        return user, events

    def sync_staf_activity(self, staf: StafUser, days: int = 30):
        """Sinkronisasi aktivitas staf dari GitLab"""
        if not staf.gitlab_username:
            raise ValueError(f"Staf {staf.username} belum memiliki username GitLab.")

        user, events = self.get_user_events(staf.gitlab_username, days)
        created_count = 0

        for event in events:
            activity_type = self._map_action_to_type(event.action_name)
            if not activity_type:
                continue

            project_id = getattr(event, 'project_id', None)
            if not project_id:
                continue

            try:
                activity_date = datetime.fromisoformat(
                    event.created_at.replace('Z', '+00:00')
                )
            except Exception:
                continue

            project_name = str(project_id)
            try:
                project = self.gl.projects.get(project_id)
                project_name = project.name_with_namespace
            except Exception:
                pass

            try:
                _, created = GitLabActivity.objects.get_or_create(
                    staf=staf,
                    activity_type=activity_type,
                    project_id=project_id,
                    activity_date=activity_date,
                    defaults={
                        'project_name': project_name,
                        'description': getattr(event, 'note', {}).get('body', '') if hasattr(event, 'note') else '',
                        'commits_count': event.push_data.get('commit_count', 0) if hasattr(event, 'push_data') and event.push_data else 0,
                        'raw_data': {},
                    }
                )
                if created:
                    created_count += 1
            except Exception as e:
                logger.warning(f"get_or_create activity failed for {staf.username}: {e}")
                continue

        return created_count

    def _map_action_to_type(self, action_name: str):
        mapping = {
            'pushed to': 'push',
            'pushed new': 'push',
            'opened': 'merge_request',
            'merged': 'merge_request',
            'commented on': 'comment',
            'created': 'issue',
            'closed': 'issue',
        }
        for key, value in mapping.items():
            if key in action_name.lower():
                return value
        return None

    def get_activity_summary(self, staf: StafUser, days: int = 30):
        """Ringkasan aktivitas staf"""
        since = timezone.now() - timedelta(days=days)
        activities = GitLabActivity.objects.filter(staf=staf, activity_date__gte=since)

        summary = {
            'staf': {
                'id': staf.id,
                'name': staf.get_full_name() or staf.username,
                'username': staf.username,
                'gitlab_username': staf.gitlab_username,
                'role': staf.role,
            },
            'period_days': days,
            'total_commits': sum(a.commits_count for a in activities),
            'total_push_events': activities.filter(activity_type='push').count(),
            'total_merge_requests': activities.filter(activity_type='merge_request').count(),
            'total_issues': activities.filter(activity_type='issue').count(),
            'total_comments': activities.filter(activity_type='comment').count(),
            'active_projects': list(activities.values_list('project_name', flat=True).distinct()),
            'daily_activity': self._get_daily_activity(activities),
        }
        return summary

    def _get_daily_activity(self, activities):
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        daily = activities.annotate(
            date=TruncDate('activity_date')
        ).values('date').annotate(count=Count('id')).order_by('date')
        return [{'date': str(d['date']), 'count': d['count']} for d in daily]

    def sync_projects(self):
        """Sinkronisasi semua project dari GitLab"""
        projects = self.gl.projects.list(all=True, order_by='last_activity_at', sort='desc')
        synced = 0
        for p in projects:
            last_activity = None
            if hasattr(p, 'last_activity_at') and p.last_activity_at:
                try:
                    last_activity = datetime.fromisoformat(p.last_activity_at.replace('Z', '+00:00'))
                except Exception:
                    pass
            GitLabProject.objects.update_or_create(
                project_id=p.id,
                defaults={
                    'name': p.name,
                    'name_with_namespace': p.name_with_namespace,
                    'description': getattr(p, 'description', '') or '',
                    'web_url': p.web_url,
                    'namespace': p.namespace.get('name', '') if isinstance(p.namespace, dict) else str(p.namespace),
                    'visibility': getattr(p, 'visibility', 'private'),
                    'default_branch': getattr(p, 'default_branch', '') or '',
                    'last_activity_at': last_activity,
                    'star_count': getattr(p, 'star_count', 0),
                    'forks_count': getattr(p, 'forks_count', 0),
                }
            )
            synced += 1
        return synced

    def sync_project_commits(self, project_obj, days=30):
        """Sinkronisasi commit per project"""
        from .models import ProjectCommit
        try:
            gl_project = self.gl.projects.get(project_obj.project_id)
        except Exception as e:
            raise ValueError(f"Project tidak ditemukan di GitLab: {e}")

        since = (datetime.now(dt_timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
        try:
            commits = gl_project.commits.list(since=since, all=True, with_stats=False)
        except Exception as e:
            raise ValueError(f"Gagal mengambil commits dari GitLab: {e}")

        # Build lookup maps: by gitlab_username and by email
        from accounts.models import StafUser
        all_staf = StafUser.objects.all()
        staf_by_username = {s.gitlab_username: s for s in all_staf if s.gitlab_username}
        staf_by_email = {s.email.lower(): s for s in all_staf if s.email}

        created = 0
        for c in commits:
            author_email = (getattr(c, 'author_email', '') or '').lower()

            # Match staf: first by email, then by gitlab_username derived from email prefix
            staf = staf_by_email.get(author_email)
            if not staf:
                email_prefix = author_email.split('@')[0]
                staf = staf_by_username.get(email_prefix)

            committed_at = datetime.fromisoformat(c.committed_date.replace('Z', '+00:00'))

            # Use real gitlab_username from staf if matched, otherwise email prefix
            gitlab_username = staf.gitlab_username if staf else (author_email.split('@')[0] or getattr(c, 'author_name', ''))

            _, is_new = ProjectCommit.objects.get_or_create(
                project=project_obj,
                commit_hash=c.id,
                defaults={
                    'staf': staf,
                    'gitlab_username': gitlab_username,
                    'author_name': getattr(c, 'author_name', ''),
                    'author_email': author_email,
                    'message': (c.message or '')[:500],
                    'committed_at': committed_at,
                }
            )
            if is_new:
                created += 1
        return created

    def get_project_contributors(self, project_obj, days=30):
        """Ringkasan kontributor per project"""
        from .models import ProjectCommit
        from django.db.models import Count
        from django.utils import timezone

        since = timezone.now() - timedelta(days=days)
        commits = ProjectCommit.objects.filter(
            project=project_obj,
            committed_at__gte=since
        )

        # Group by gitlab_username
        from django.db.models import Count, Min, Max
        contributors = commits.values('gitlab_username', 'author_name', 'staf__first_name', 'staf__last_name', 'staf__id').annotate(
            total_commits=Count('id'),
            first_commit=Min('committed_at'),
            last_commit=Max('committed_at'),
        ).order_by('-total_commits')

        result = []
        for c in contributors:
            name = f"{c['staf__first_name'] or ''} {c['staf__last_name'] or ''}".strip() or c['author_name']
            result.append({
                'staf_id': c['staf__id'],
                'gitlab_username': c['gitlab_username'],
                'name': name,
                'total_commits': c['total_commits'],
                'first_commit': str(c['first_commit'].date()) if c['first_commit'] else None,
                'last_commit': str(c['last_commit'].date()) if c['last_commit'] else None,
            })
        return result

    def get_team_summary(self, days: int = 30):
        """Ringkasan aktivitas seluruh tim"""
        programmers = StafUser.objects.filter(role='programmer', is_active=True)
        team_data = []
        for staf in programmers:
            if staf.gitlab_username:
                team_data.append(self.get_activity_summary(staf, days))
        return team_data

    def sync_issue_comments(self, project_obj, days=30):
        """Sinkronisasi komentar issue dari GitLab"""
        from .models import IssueComment
        try:
            gl_project = self.gl.projects.get(project_obj.project_id)
        except Exception as e:
            raise ValueError(f"Project tidak ditemukan: {e}")

        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')

        # Build staf map
        from accounts.models import StafUser
        staf_map = {s.gitlab_username: s for s in StafUser.objects.filter(gitlab_username__isnull=False)}

        try:
            issues = gl_project.issues.list(all=True, updated_after=since)
        except Exception:
            return 0

        created = 0
        for issue in issues:
            try:
                notes = gl_project.issues.get(issue.iid).notes.list(all=True)
            except Exception:
                continue

            for note in notes:
                if note.system:
                    continue
                try:
                    created_at = datetime.fromisoformat(note.created_at.replace('Z', '+00:00'))
                except Exception:
                    continue

                author_username = note.author.get('username', '') if isinstance(note.author, dict) else getattr(note.author, 'username', '')
                author_name = note.author.get('name', '') if isinstance(note.author, dict) else getattr(note.author, 'name', '')
                staf = staf_map.get(author_username)

                updated_at = None
                if hasattr(note, 'updated_at') and note.updated_at:
                    try:
                        updated_at = datetime.fromisoformat(note.updated_at.replace('Z', '+00:00'))
                    except Exception:
                        pass

                _, is_new = IssueComment.objects.get_or_create(
                    project=project_obj,
                    note_id=str(note.id),
                    comment_type='issue',
                    defaults={
                        'staf': staf,
                        'comment_type': 'issue',
                        'issue_id': issue.id,
                        'issue_iid': issue.iid,
                        'issue_title': (issue.title or '')[:500],
                        'issue_url': getattr(issue, 'web_url', ''),
                        'issue_state': getattr(issue, 'state', 'opened'),
                        'author_username': author_username,
                        'author_name': author_name,
                        'body': (note.body or '')[:2000],
                        'created_at': created_at,
                        'updated_at': updated_at,
                        'is_system': False,
                    }
                )
                if is_new:
                    created += 1
        return created

    def sync_commit_comments(self, project_obj, days=30):
        """Sinkronisasi komentar pada commit dari GitLab"""
        from .models import IssueComment
        try:
            gl_project = self.gl.projects.get(project_obj.project_id)
        except Exception as e:
            raise ValueError(f"Project tidak ditemukan: {e}")

        since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')

        from accounts.models import StafUser
        staf_map = {s.gitlab_username: s for s in StafUser.objects.filter(gitlab_username__isnull=False)}

        try:
            commits = gl_project.commits.list(since=since, all=True)
        except Exception:
            return 0

        created = 0
        for commit in commits:
            try:
                comments = gl_project.commits.get(commit.id).comments.list(all=True)
            except Exception:
                continue

            for comment in comments:
                author_username = ''
                author_name = ''
                if hasattr(comment, 'author') and comment.author:
                    if isinstance(comment.author, dict):
                        author_username = comment.author.get('username', '')
                        author_name = comment.author.get('name', '')
                    else:
                        author_username = getattr(comment.author, 'username', '')
                        author_name = getattr(comment.author, 'name', '')

                staf = staf_map.get(author_username)

                try:
                    created_at = datetime.fromisoformat(comment.created_at.replace('Z', '+00:00'))
                except Exception:
                    continue

                note_id = f"commit_{commit.id[:8]}_{getattr(comment, 'id', created_at.timestamp())}"

                _, is_new = IssueComment.objects.get_or_create(
                    project=project_obj,
                    note_id=note_id,
                    comment_type='commit',
                    defaults={
                        'staf': staf,
                        'comment_type': 'commit',
                        'commit_sha': commit.id,
                        'commit_message': (getattr(commit, 'message', '') or '')[:500],
                        'commit_url': f"{project_obj.web_url}/-/commit/{commit.id}",
                        'line_code': getattr(comment, 'line_type', '') or '',
                        'author_username': author_username,
                        'author_name': author_name,
                        'body': (getattr(comment, 'note', '') or '')[:2000],
                        'created_at': created_at,
                        'is_system': False,
                    }
                )
                if is_new:
                    created += 1
        return created

    def get_comment_stats(self, days=30):
        """Statistik komentar seluruh tim"""
        from .models import IssueComment
        from django.db.models import Count
        from django.utils import timezone

        since = timezone.now() - timedelta(days=days)
        comments = IssueComment.objects.filter(created_at__gte=since, is_system=False)

        by_staf = comments.values(
            'author_username', 'author_name', 'staf__id', 'staf__first_name', 'staf__last_name'
        ).annotate(total=Count('id')).order_by('-total')

        return {
            'total_comments': comments.count(),
            'by_staf': list(by_staf),
        }
