"""
Management command for exporting dismissal codes to CSV file.

Usage:
    python manage.py export_dismissal_codes output.csv
    python manage.py export_dismissal_codes output.csv --active-only
"""

import csv
from django.core.management.base import BaseCommand
from dissmissal.models import Student


class Command(BaseCommand):
    help = 'Export dismissal codes to CSV file (Name,Dismissal Code,Grade,Teacher,Status,Is Active)'

    def add_arguments(self, parser):
        parser.add_argument('output_file', type=str, help='Output CSV file path')
        parser.add_argument(
            '--active-only',
            action='store_true',
            help='Export only active students'
        )

    def handle(self, *args, **options):
        output_file = options['output_file']
        active_only = options['active_only']

        # Get students
        students = Student.objects.all().order_by('name')
        if active_only:
            students = students.filter(is_active=True)

        # Write CSV file
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                
                # Write header
                writer.writerow(['Name', 'Dismissal Code', 'Grade', 'Teacher', 'Status', 'Is Active'])
                
                # Write student data
                rows_written = 0
                for student in students:
                    writer.writerow([
                        student.name,
                        student.dismissal_code,
                        student.grade,
                        student.teacher,
                        student.get_current_status_display(),
                        'Yes' if student.is_active else 'No'
                    ])
                    rows_written += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully exported {rows_written} students to {output_file}'
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error writing CSV file: {e}')
            )