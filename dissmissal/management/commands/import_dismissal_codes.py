"""
Django management command to import dismissal codes from CSV file.

Usage:
    uv run python manage.py import_dismissal_codes --file path/to/codes.csv
    uv run python manage.py import_dismissal_codes --file path/to/codes.csv --dry-run
    uv run python manage.py import_dismissal_codes --file path/to/codes.csv --user admin_username
"""

import csv
import sys
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction
from dissmissal.models import Student
from dissmissal.utils import (
    validate_and_format_dismissal_code,
    log_dismissal_code_change,
    check_dismissal_code_uniqueness
)


class Command(BaseCommand):
    help = 'Import dismissal codes from CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Path to CSV file containing student names and dismissal codes'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making actual changes'
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Username of staff member performing the import (for audit logging)'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        dry_run = options['dry_run']
        username = options['user']
        
        # Get user for audit logging
        user = None
        if username:
            try:
                user = User.objects.get(username=username, is_staff=True)
            except User.DoesNotExist:
                raise CommandError(f'Staff user "{username}" not found')
        
        # Validate file exists
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                pass
        except FileNotFoundError:
            raise CommandError(f'File not found: {file_path}')
        except Exception as e:
            raise CommandError(f'Error accessing file: {e}')
        
        self.stdout.write(f'Reading CSV file: {file_path}')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        success_count = 0
        error_count = 0
        errors = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                # Detect delimiter
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                
                # Validate required columns
                required_fields = ['student_name', 'dismissal_code']
                if not all(field in reader.fieldnames for field in required_fields):
                    raise CommandError(
                        f'CSV must contain columns: {", ".join(required_fields)}\\n'
                        f'Found columns: {", ".join(reader.fieldnames or [])}'
                    )
                
                # Process each row
                with transaction.atomic():
                    for row_num, row in enumerate(reader, start=2):
                        result = self._process_row(row, row_num, user, dry_run)
                        
                        if result['success']:
                            success_count += 1
                            if result['message']:
                                self.stdout.write(
                                    self.style.SUCCESS(f"Row {row_num}: {result['message']}")
                                )
                        else:
                            error_count += 1
                            errors.append(f"Row {row_num}: {result['error']}")
                            self.stdout.write(
                                self.style.ERROR(f"Row {row_num}: {result['error']}")
                            )
                    
                    if dry_run:
                        # Rollback transaction in dry run mode
                        transaction.set_rollback(True)
        
        except Exception as e:
            raise CommandError(f'Error processing CSV file: {e}')
        
        # Summary
        self.stdout.write('\\n' + '='*50)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN COMPLETED'))
        else:
            self.stdout.write(self.style.SUCCESS('IMPORT COMPLETED'))
        
        self.stdout.write(f'Successfully processed: {success_count} students')
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {error_count}'))
            if errors:
                self.stdout.write('\\nError details:')
                for error in errors[:10]:  # Show first 10 errors
                    self.stdout.write(f'  - {error}')
                if len(errors) > 10:
                    self.stdout.write(f'  ... and {len(errors) - 10} more errors')
        
        if error_count > 0:
            sys.exit(1)
    
    def _process_row(self, row, row_num, user, dry_run):
        """Process a single CSV row"""
        student_name = row.get('student_name', '').strip()
        new_code = row.get('dismissal_code', '').strip()
        
        if not student_name:
            return {'success': False, 'error': 'Student name is required'}
        
        # Find student by name
        try:
            student = Student.objects.get(name__iexact=student_name)
        except Student.DoesNotExist:
            return {'success': False, 'error': f'Student "{student_name}" not found'}
        except Student.MultipleObjectsReturned:
            return {'success': False, 'error': f'Multiple students found with name "{student_name}"'}
        
        # Handle empty code (auto-generate)
        if not new_code:
            if dry_run:
                formatted_code = '[AUTO-GENERATED]'
            else:
                formatted_code = Student.generate_dismissal_code()
        else:
            # Validate dismissal code
            formatted_code, is_valid, error_message = validate_and_format_dismissal_code(new_code)
            if not is_valid:
                return {'success': False, 'error': error_message}
            
            # Check uniqueness
            if not dry_run:
                is_unique, error_message = check_dismissal_code_uniqueness(
                    formatted_code, exclude_student_id=student.id
                )
                if not is_unique:
                    return {'success': False, 'error': error_message}
        
        # Check if code is actually changing
        old_code = student.dismissal_code
        if old_code == formatted_code:
            return {
                'success': True, 
                'message': f'{student_name}: No change needed (code already {formatted_code})'
            }
        
        # Update student code
        if not dry_run:
            student.dismissal_code = formatted_code
            student.save(update_fields=['dismissal_code'])
            
            # Log the change if user provided
            if user:
                log_dismissal_code_change(
                    user=user,
                    student=student,
                    old_code=old_code,
                    new_code=formatted_code,
                    ip_address='127.0.0.1',  # Command line import
                    method='management_command'
                )
        
        return {
            'success': True,
            'message': f'{student_name}: {old_code} → {formatted_code}'
        }