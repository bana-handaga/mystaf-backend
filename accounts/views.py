from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.contrib.auth import login, logout
from django.db.models import Count, Sum, Q
from datetime import timedelta
from django.utils import timezone
from .models import StafUser
from .serializers import (
    StafUserSerializer, RegisterSerializer,
    LoginSerializer, ChangePasswordSerializer
)

class RegisterView(generics.CreateAPIView):
    queryset = StafUser.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.IsAdminUser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'user': StafUserSerializer(user).data,
            'token': token.key,
            'message': 'Akun berhasil dibuat.'
        }, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'user': StafUserSerializer(user).data,
            'token': token.key,
            'message': 'Login berhasil.'
        })

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            request.user.auth_token.delete()
        except Exception:
            pass
        return Response({'message': 'Logout berhasil.'})

class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = StafUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'old_password': 'Password lama salah.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'message': 'Password berhasil diubah.'})

class StafListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        search = request.query_params.get('search', '')
        order_by = request.query_params.get('order_by', 'name')
        order_dir = request.query_params.get('order_dir', 'asc')
        since = timezone.now() - timedelta(days=days)

        qs = StafUser.objects.filter(role='programmer').annotate(
            total_activity=Count(
                'gitlab_activities',
                filter=Q(gitlab_activities__activity_date__gte=since)
            ),
            total_commits=Sum(
                'gitlab_activities__commits_count',
                filter=Q(gitlab_activities__activity_date__gte=since)
            ),
        )

        if search:
            qs = qs.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(username__icontains=search) |
                Q(gitlab_username__icontains=search)
            )

        sort_map = {
            'name': 'first_name',
            'username': 'username',
            'email': 'email',
            'gitlab_username': 'gitlab_username',
            'activity': 'total_activity',
            'commits': 'total_commits',
        }
        sort_field = sort_map.get(order_by, 'first_name')
        if order_dir == 'desc':
            sort_field = f'-{sort_field}'
        qs = qs.order_by(sort_field)

        results = []
        for s in qs:
            results.append({
                'id': s.id,
                'username': s.username,
                'first_name': s.first_name,
                'last_name': s.last_name,
                'email': s.email,
                'gitlab_username': s.gitlab_username,
                'role': s.role,
                'is_active': s.is_active,
                'total_activity': s.total_activity or 0,
                'total_commits': s.total_commits or 0,
            })

        return Response({'count': len(results), 'results': results})
