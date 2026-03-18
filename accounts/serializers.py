from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import StafUser

class StafUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = StafUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'role', 'gitlab_username', 'phone', 'avatar',
                  'is_active', 'date_joined', 'last_login']
        read_only_fields = ['id', 'date_joined', 'last_login']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = StafUser
        fields = ['username', 'email', 'first_name', 'last_name',
                  'password', 'password2', 'role', 'gitlab_username', 'phone']

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password2": "Password tidak cocok."})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = StafUser(**validated_data)
        user.set_password(password)
        user.save()
        return user

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['username'], password=data['password'])
        if not user:
            raise serializers.ValidationError("Username atau password salah.")
        if not user.is_active:
            raise serializers.ValidationError("Akun tidak aktif.")
        data['user'] = user
        return data

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password2 = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['new_password2']:
            raise serializers.ValidationError({"new_password2": "Password baru tidak cocok."})
        return data
