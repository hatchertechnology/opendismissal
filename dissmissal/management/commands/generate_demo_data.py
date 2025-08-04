from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from dissmissal.models import Student, PickupEvent
import random


class Command(BaseCommand):
    help = "Generate demo data for OpenDismissal presentations and testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--students",
            type=int,
            default=25,
            help="Number of demo students to create (default: 25)",
        )
        parser.add_argument(
            "--events",
            action="store_true",
            help="Generate sample pickup events for realistic dashboard",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Clear existing demo data before generating new data",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write("Clearing existing demo data...")
            Student.objects.filter(name__startswith="Demo ").delete()
            PickupEvent.objects.filter(student__name__startswith="Demo ").delete()

        # Create demo staff user
        demo_staff, created = User.objects.get_or_create(
            username="demo_staff",
            defaults={
                "first_name": "Demo",
                "last_name": "Staff",
                "email": "demo@school.edu",
                "is_staff": True,
                "is_active": True,
            },
        )
        if created:
            demo_staff.set_password("demo123")
            demo_staff.save()
            self.stdout.write(self.style.SUCCESS(f"Created demo staff user: {demo_staff.username}"))

        # Demo student data with realistic names and grades
        demo_students_data = [
            ("Demo Emma Johnson", "3rd", "Mrs. Smith"),
            ("Demo Liam Chen", "4th", "Mr. Davis"),
            ("Demo Olivia Williams", "2nd", "Ms. Garcia"),
            ("Demo Noah Brown", "5th", "Mrs. Wilson"),
            ("Demo Ava Rodriguez", "1st", "Ms. Martinez"),
            ("Demo Ethan Miller", "3rd", "Mrs. Smith"),
            ("Demo Sophia Anderson", "4th", "Mr. Davis"),
            ("Demo Mason Taylor", "2nd", "Ms. Garcia"),
            ("Demo Isabella Moore", "5th", "Mrs. Wilson"),
            ("Demo Jacob White", "1st", "Ms. Martinez"),
            ("Demo Charlotte Jones", "3rd", "Mrs. Smith"),
            ("Demo William Garcia", "4th", "Mr. Davis"),
            ("Demo Amelia Martinez", "2nd", "Ms. Garcia"),
            ("Demo James Wilson", "5th", "Mrs. Wilson"),
            ("Demo Harper Lopez", "1st", "Ms. Martinez"),
            ("Demo Benjamin Lee", "3rd", "Mrs. Smith"),
            ("Demo Evelyn Gonzalez", "4th", "Mr. Davis"),
            ("Demo Lucas Hernandez", "2nd", "Ms. Garcia"),
            ("Demo Abigail Perez", "5th", "Mrs. Wilson"),
            ("Demo Henry Turner", "1st", "Ms. Martinez"),
            ("Demo Emily Campbell", "3rd", "Mrs. Smith"),
            ("Demo Alexander Parker", "4th", "Mr. Davis"),
            ("Demo Elizabeth Evans", "2nd", "Ms. Garcia"),
            ("Demo Sebastian Stewart", "5th", "Mrs. Wilson"),
            ("Demo Scarlett Rivera", "1st", "Ms. Martinez"),
        ]

        students_created = 0
        target_count = min(options["students"], len(demo_students_data))

        for i in range(target_count):
            name, grade, teacher = demo_students_data[i]

            # Create student with random status distribution
            status_choices = ["WAITING", "PARENT_ARRIVED", "PICKED_UP"]
            status_weights = [0.6, 0.3, 0.1]  # Most waiting, some arrived, few picked up
            status = random.choices(status_choices, weights=status_weights)[0]

            student, created = Student.objects.get_or_create(
                name=name,
                defaults={
                    "grade": grade,
                    "teacher": teacher,
                    "current_status": status,
                    "is_active": True,
                },
            )

            if created:
                students_created += 1
                self.stdout.write(f"Created: {student.name} ({student.dismissal_code})")

                # Generate sample events if requested
                if options["events"] and status != "WAITING":
                    self.create_sample_events(student, demo_staff, status)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDemo data generation complete!\n"
                f"Created {students_created} students\n"
                f"Demo staff login: demo_staff / demo123\n"
                f"Access admin at: /admin/\n"
                f"Access app at: /dissmissal/"
            )
        )

    def create_sample_events(self, student, staff_user, final_status):
        """Create realistic sample events for demonstration"""
        now = timezone.now()

        # Create parent arrival event (5-15 minutes ago)
        if final_status in ["PARENT_ARRIVED", "PICKED_UP"]:
            arrival_time = now - timedelta(minutes=random.randint(5, 15))
            PickupEvent.objects.create(
                student=student,
                staff_member=staff_user,
                event_type="PARENT_ARRIVED",
                dismissal_code_used=student.dismissal_code,
                timestamp=arrival_time,
                notes=f"Parent arrived for {student.name}",
                ip_address="127.0.0.1",
            )

        # Create pickup completion event (1-5 minutes ago)
        if final_status == "PICKED_UP":
            pickup_time = now - timedelta(minutes=random.randint(1, 5))
            PickupEvent.objects.create(
                student=student,
                staff_member=staff_user,
                event_type="STUDENT_PICKED_UP",
                dismissal_code_used=student.dismissal_code,
                timestamp=pickup_time,
                notes=f"Pickup completed for {student.name}",
                ip_address="127.0.0.1",
            )
