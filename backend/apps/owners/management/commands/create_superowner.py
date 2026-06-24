import getpass
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

Owner = get_user_model()

class Command(BaseCommand):
    help = 'Creates a superowner with email rohandharlapally22@gmail.com'

    def handle(self, *args, **options):
        email = 'rohandharlapally22@gmail.com'
        display_name = 'Rohan Owner'
        
        if Owner.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f'Superowner with email {email} already exists.'))
            return

        self.stdout.write(f'Creating superowner for {email}...')
        password = getpass.getpass('Password: ')
        confirm_password = getpass.getpass('Password (again): ')

        if password != confirm_password:
            self.stdout.write(self.style.ERROR('Passwords do not match.'))
            return

        try:
            Owner.objects.create_superuser(
                email=email,
                password=password,
                display_name=display_name,
                is_verified=True
            )
            self.stdout.write(self.style.SUCCESS('Superowner created successfully.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to create superowner: {e}'))
