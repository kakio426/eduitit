from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.utils import generate_sso_token, get_schoolit_url
from django.conf import settings
import jwt
import datetime

User = get_user_model()

class Command(BaseCommand):
    help = 'Test SSO token generation and verify payload'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='User email to test with')

    def handle(self, *args, **options):
        email = options['email']
        log_lines = []
        
        def log(msg):
            print(msg)
            log_lines.append(str(msg))

        log("\n" + "="*50)
        log("!!! SSO DIAGNOSTIC START !!!")
        log("="*50 + "\n")
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            log(f"ERROR: User with email {email} not found")
            self.write_log(log_lines)
            return

        log(f"User Found: {user.email} (ID: {user.id})")
        
        # 1. Profile Check
        if hasattr(user, 'userprofile'):
            log(f"Role: {user.userprofile.role}")
            log(f"Nickname: {user.userprofile.nickname}")
        else:
            log("WARNING: User has no profile!")

        # 2. Token Generation
        try:
            token = generate_sso_token(user)
            log("\n[Token Generated]")
            log(f"{token[:15]}...{token[-15:]}")
        except Exception as e:
            log(f"ERROR: Token generation failed: {e}")
            self.write_log(log_lines)
            return

        # 3. Verification
        try:
            payload = jwt.decode(token, settings.SSO_JWT_SECRET, algorithms=['HS256'])
            log("\n[Payload Verification]")
            for k, v in payload.items():
                log(f"  {k}: {v}")
                
            valid_roles = ['SCHOOL', 'INSTRUCTOR', 'COMPANY']
            if payload['role'] not in valid_roles:
                log(f"\nCRITICAL WARNING: Role '{payload['role']}' is invalid! Schoolit will reject this.")
                log(f"Expected one of: {valid_roles}")
            else:
                log(f"\nRole '{payload['role']}' is VALID.")

        except Exception as e:
            log(f"\nERROR: Token decoding failed: {e}")
            
        # 4. URL
        try:
            role = user.userprofile.role if hasattr(user, 'userprofile') else 'unknown'
            base_url = get_schoolit_url(role)
            final_url = f"{base_url}?sso_token={token}"
            log(f"\n[Target URL]\n{final_url}")
        except Exception as e:
            log(f"ERROR: URL failed: {e}")

        # 5. Config
        log("\n[Config Check]")
        log(f"SSO_JWT_SECRET Set: {'Yes' if settings.SSO_JWT_SECRET else 'No'}")
        if settings.SSO_JWT_SECRET == settings.SECRET_KEY:
             log("WARNING: Using default SECRET_KEY as SSO secret. Security risk + mismatch risk.")
        log(f"SCHOOLIT_URL: {settings.SCHOOLIT_URL}")
        
        log("\n" + "="*50)
        log("!!! SSO DIAGNOSTIC END !!!")
        log("="*50 + "\n")
        
        self.write_log(log_lines)

    def write_log(self, lines):
        with open('sso_debug.log', 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
