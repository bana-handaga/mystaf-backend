from rest_framework import serializers
from .models import GitLabConfig, GitLabActivity, ActivitySummary

class GitLabConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = GitLabConfig
        fields = ['id', 'url', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

class GitLabConfigWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = GitLabConfig
        fields = ['url', 'private_token', 'is_active']

class GitLabActivitySerializer(serializers.ModelSerializer):
    staf_name = serializers.CharField(source='staf.get_full_name', read_only=True)
    class Meta:
        model = GitLabActivity
        fields = ['id', 'staf', 'staf_name', 'activity_type', 'project_name',
                  'project_id', 'description', 'commits_count', 'additions',
                  'deletions', 'activity_date']

class ActivitySummarySerializer(serializers.ModelSerializer):
    staf_name = serializers.CharField(source='staf.get_full_name', read_only=True)
    class Meta:
        model = ActivitySummary
        fields = '__all__'
