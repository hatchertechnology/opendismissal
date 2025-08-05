"""
Management command for importing dismissal codes from CSV file.

Usage:
    python manage.py import_dismissal_codes path/to/codes.csv --dry-run
    python manage.py import_dismissal_codes path/to/codes.csv --update-existing
"""

import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.models import User
from dissmissal.models import Student
from dissmissal.utils import validate_dismissal_code_format


class Command(BaseCommand):
    help = 'Import dismissal codes from CSV file (Name,Dismissal Code,Grade,Teacher)'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to CSV file')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate CSV without importing (shows what would be imported)'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing students if name matches'
        )
        parser.add_argument(
            '--staff-user',
            type=str,
            help='Username of staff member for audit logging (defaults to first superuser)'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        dry_run = options['dry_run']
        update_existing = options['update_existing']
        staff_username = options.get('staff_user')

        # Validate file exists
        if not os.path.exists(csv_file):
            raise CommandError(f'CSV file not found: {csv_file}')

        # Get staff user for audit logging
        staff_user = self.get_staff_user(staff_username)

        # Process CSV file
        try:
            with open(csv_file, 'r', newline='', encoding='utf-8') as file:
                self.process_csv(file, dry_run, update_existing, staff_user)
        except Exception as e:
            raise CommandError(f'Error processing CSV file: {e}')

    def get_staff_user(self, username=None):
        """Get staff user for audit logging"""
        if username:
            try:
                user = User.objects.get(username=username, is_staff=True)
                return user
            except User.DoesNotExist:
                raise CommandError(f'Staff user not found: {username}')
        else:
            # Use first superuser
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                raise CommandError('No superuser found for audit logging. Create one or specify --staff-user')
            return user

    def process_csv(self, file, dry_run, update_existing, staff_user):
        """Process CSV file and import/validate data"""
        reader = csv.DictReader(file)
        
        # Validate headers
        expected_headers = {'Name', 'Dismissal Code', 'Grade', 'Teacher'}
        if not expected_headers.issubset(set(reader.fieldnames)):
            raise CommandError(
                f'CSV must contain columns: {", ".join(expected_headers)}\n'
                f'Found columns: {", ".join(reader.fieldnames)}'
            )

        rows_processed = 0
        rows_created = 0
        rows_updated = 0
        rows_skipped = 0
        errors = []

        with transaction.atomic():
            for row_num, row in enumerate(reader, start=2):  # Start at 2 for header
                try:
                    result = self.process_row(row, row_num, update_existing, staff_user, dry_run)
                    rows_processed += 1
                    
                    if result == 'created':
                        rows_created += 1
                    elif result == 'updated':
                        rows_updated += 1
                    elif result == 'skipped':
                        rows_skipped += 1
                        
                except Exception as e:
                    errors.append(f'Row {row_num}: {e}')
                    continue

            # Report results
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f'DRY RUN - No changes made')
                )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Processed {rows_processed} rows:\n'
                    f'  - Created: {rows_created}\n'
                    f'  - Updated: {rows_updated}\n'
                    f'  - Skipped: {rows_skipped}\n'
                    f'  - Errors: {len(errors)}'
                )
            )

            if errors:
                self.stdout.write(self.style.ERROR('\nErrors:'))
                for error in errors[:10]:  # Show first 10 errors
                    self.stdout.write(self.style.ERROR(f'  {error}'))
                if len(errors) > 10:
                    self.stdout.write(self.style.ERROR(f'  ... and {len(errors) - 10} more errors'))

            # Rollback transaction if dry run
            if dry_run:
                transaction.set_rollback(True)

    def process_row(self, row, row_num, update_existing, staff_user, dry_run):
        """Process a single CSV row"""
        name = row['Name'].strip()
        dismissal_code = row['Dismissal Code'].strip().upper()
        grade = row['Grade'].strip()
        teacher = row['Teacher'].strip()

        # Validate required fields
        if not name:
            raise ValueError('Name is required')
        if not dismissal_code:
            raise ValueError('Dismissal Code is required')
        if not grade:
            raise ValueError('Grade is required')
        if not teacher:
            raise ValueError('Teacher is required')

        # Validate dismissal code format
        from dissmissal.utils import validate_dismissal_code_format
        is_valid, error_msg = validate_dismissal_code_format(dismissal_code)
        if not is_valid:
            raise ValueError(f'Invalid dismissal code "{dismissal_code}": {error_msg}')

        # Check for existing student by name
        existing_student = Student.objects.filter(name=name).first()

        if existing_student:
            if not update_existing:
                self.stdout.write(
                    self.style.WARNING(f'Row {row_num}: Student "{name}" already exists, skipping')
                )
                return 'skipped'
            else:
                # Update existing student
                old_code = existing_student.dismissal_code
                existing_student.dismissal_code = dismissal_code
                existing_student.grade = grade
                existing_student.teacher = teacher
                existing_student._change_user = staff_user
                existing_student._change_ip = '127.0.0.1'  # Command line import
                
                if not dry_run:
                    existing_student.save()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Row {row_num}: Updated "{name}" code from {old_code} to {dismissal_code}'
                    )
                )
                return 'updated'
        else:
            # Check for duplicate dismissal code
            if Student.objects.filter(dismissal_code=dismissal_code).exists():
                raise ValueError(f'Dismissal code "{dismissal_code}" already exists')

            # Create new student
            student = Student(
                name=name,
                dismissal_code=dismissal_code,
                grade=grade,
                teacher=teacher
            )
            student._change_user = staff_user
            student._change_ip = '127.0.0.1'  # Command line import

            if not dry_run:
                student.save()

            self.stdout.write(
                self.style.SUCCESS(f'Row {row_num}: Created "{name}" with code {dismissal_code}')
            )
            return 'created'