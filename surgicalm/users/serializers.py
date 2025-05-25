# serializers.py
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from surgicalm.users.models import CustomUser, PartnerHospitals

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser  
        fields = ['id', 'username', 'email']

class DevSerializer(serializers.Serializer):
    dev_key = serializers.CharField()

class NurseLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

class PatientRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = CustomUser  
        fields = ('email', 'username', 'password', 'password2')

    def validate(self, attrs):
        """Centralized validation logic."""
        email = attrs.get('email')
        username = attrs.get('username')
        password = attrs.get('password')
        password2 = attrs.get('password2')

        # Validate email
        if CustomUser.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "An account with this email already exists."})

        # Validate username
        if len(username) < 3:
            raise serializers.ValidationError({"username": "Username must be at least 3 characters long."})
        if len(username) > 30:
            raise serializers.ValidationError({"username": "Username cannot exceed 30 characters."})
        if not username.isalnum():
            raise serializers.ValidationError({"username": "Username must contain only letters and numbers."})
        if CustomUser.objects.filter(username=username).exists():
            raise serializers.ValidationError({"username": "This username is already taken. Please choose a different one."})

        # Validate password
        if len(password) < 8:
            raise serializers.ValidationError({"password": "Password must be at least 8 characters long."})
        if password == username:
            raise serializers.ValidationError({"password": "Password must be different than username"})
        if not any(char.isdigit() for char in password):
            raise serializers.ValidationError({"password": "Password must contain at least one digit."})
        if not any(char.isupper() for char in password):
            raise serializers.ValidationError({"password": "Password must contain at least one uppercase letter."})
        if not any(char in "!@#$%^&*()-_=+[]{};:'\",.<>?/|`~" for char in password):
            raise serializers.ValidationError({"password": "Password must contain at least one special character"})

        # Validate password confirmation
        if password != password2:
            raise serializers.ValidationError({"password": "Password fields don't match."})

        return attrs

    def create(self, validated_data):
        """Create a new patient user."""
        validated_data.pop('password2')  

        user = CustomUser.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
            user_type='patient',
            hospital=self.context['hospital']
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

class NurseRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    hospital_id = serializers.IntegerField(write_only=True, required=True)  

    class Meta:
        model = CustomUser  
        fields = ('email', 'username', 'password', 'password2', 'hospital_id')

    def validate(self, attrs):
        """Ensure passwords match and hospital exists"""
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})

        if not PartnerHospitals.objects.filter(id=attrs['hospital_id']).exists():
            raise serializers.ValidationError({"hospital_id": "Selected hospital does not exist."})

        return attrs

    def create(self, validated_data):
        """Create a nurse with the assigned hospital"""
        validated_data.pop('password2')  
        hospital = PartnerHospitals.objects.get(id=validated_data.pop('hospital_id'))  

        user = CustomUser.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
            user_type='nurse',
            hospital=hospital 
        )

        user.set_password(validated_data['password']) 
        user.save()
        return user
    
class PatientLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
