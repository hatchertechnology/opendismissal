"""
OpenDismissal Forms

Comprehensive form classes with validation for the dismissal system.
Author: Derek Hayes
"""

from django import forms
from django.core.exceptions import ValidationError
from .models import Student
from .utils import validate_dismissal_code_format, sanitize_input


class ParentArrivalForm(forms.Form):
    """
    Form for logging parent arrivals with dismissal code validation.
    Includes real-time validation and security measures.
    """

    dismissal_code = forms.CharField(
        max_length=8,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-lg form-control-mobile",
                "placeholder": "Enter dismissal code",
                "autocomplete": "off",
                "inputmode": "text",
                "pattern": "[A-Z0-9]{6,8}",
                "title": "Enter 6-8 character dismissal code (letters and numbers only)",
                "style": "text-transform: uppercase; font-family: monospace;",
                "autofocus": True,
                "data-validate-url": "/dissmissal/api/validate-code/",  # For AJAX validation
            }
        ),
        help_text="Enter the unique dismissal code provided to the parent",
    )

    notes = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Optional notes about parent arrival...",
            }
        ),
        help_text="Optional notes about the parent arrival",
    )

    def clean_dismissal_code(self):
        """Validate dismissal code format and existence"""
        code = self.cleaned_data["dismissal_code"].upper().strip()

        # Format validation
        is_valid, error_message = validate_dismissal_code_format(code)
        if not is_valid:
            raise ValidationError(error_message)

        # Check if code exists and is active
        try:
            student = Student.objects.get(dismissal_code=code, is_active=True)

            # Store student for use in view (avoid duplicate queries)
            self.student = student

        except Student.DoesNotExist:
            raise ValidationError("Invalid dismissal code. Please verify the code and try again.")

        return code

    def clean_notes(self):
        """Sanitize and validate notes field"""
        notes = self.cleaned_data.get("notes", "").strip()

        # Basic length validation
        if len(notes) > 500:
            raise ValidationError("Notes cannot exceed 500 characters.")

        # Sanitize input
        notes = sanitize_input(notes, max_length=500)

        return notes


class StudentPickupForm(forms.Form):
    """
    Form for completing student pickup process.
    Allows selection from students with parent_arrived status.
    """

    def __init__(self, *args, **kwargs):
        initial_student = kwargs.pop("initial_student", None)
        super().__init__(*args, **kwargs)

        # Get students ready for pickup
        ready_queryset = Student.objects.filter(
            is_active=True, current_status="PARENT_ARRIVED"
        ).order_by("name")

        self.fields["student"] = forms.ModelChoiceField(
            queryset=ready_queryset,
            empty_label="Select student for pickup...",
            widget=forms.Select(attrs={"class": "form-control form-control-lg", "required": True}),
            help_text="Select the student to complete pickup",
        )

        # Pre-select student if provided
        if initial_student and initial_student.current_status == "PARENT_ARRIVED":
            self.fields["student"].initial = initial_student
            self.fields["student"].widget.attrs["readonly"] = True

    notes = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Optional notes about pickup completion...",
            }
        ),
        help_text="Optional notes about the pickup completion",
    )

    def clean_student(self):
        """Validate selected student is eligible for pickup"""
        student = self.cleaned_data["student"]

        if student.current_status != "PARENT_ARRIVED":
            raise ValidationError(
                f"{student.name} is not ready for pickup. "
                f"Current status: {student.get_current_status_display()}"
            )

        return student

    def clean_notes(self):
        """Sanitize and validate notes field"""
        notes = self.cleaned_data.get("notes", "").strip()

        # Basic length validation
        if len(notes) > 500:
            raise ValidationError("Notes cannot exceed 500 characters.")

        # Sanitize input
        notes = sanitize_input(notes, max_length=500)

        return notes


class AddStudentForm(forms.ModelForm):
    """
    Form for adding new students to the system.
    Includes validation for required fields and generates dismissal code.
    """

    class Meta:
        model = Student
        fields = ["name", "grade", "teacher"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter full student name",
                    "maxlength": 100,
                }
            ),
            "grade": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g., 3rd, 4th, 5th",
                    "maxlength": 20,
                }
            ),
            "teacher": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter teacher name",
                    "maxlength": 100,
                }
            ),
        }
        help_texts = {
            "name": "Enter the student's full name as it should appear in the system",
            "grade": "Enter the student's current grade level",
            "teacher": "Enter the homeroom teacher's name",
        }

    def clean_name(self):
        """Validate and format student name"""
        name = self.cleaned_data["name"].strip()

        if len(name) < 2:
            raise ValidationError("Student name must be at least 2 characters long.")

        if len(name) > 100:
            raise ValidationError("Student name cannot exceed 100 characters.")

        # Check for duplicate names (warning, not error)
        existing = Student.objects.filter(name__iexact=name, is_active=True)
        if existing.exists():
            # Don't raise error, but add a warning that could be handled in view
            pass

        return name.title()  # Proper case formatting

    def clean_grade(self):
        """Validate grade format"""
        grade = self.cleaned_data["grade"].strip()

        if not grade:
            raise ValidationError("Grade level is required.")

        return grade

    def clean_teacher(self):
        """Validate teacher name"""
        teacher = self.cleaned_data["teacher"].strip()

        if not teacher:
            raise ValidationError("Teacher name is required.")

        return teacher.title()  # Proper case formatting

    def save(self, commit=True):
        """Save student with auto-generated dismissal code"""
        student = super().save(commit=False)

        # Dismissal code will be auto-generated in Student.save()
        if commit:
            student.save()

        return student


class DashboardFilterForm(forms.Form):
    """
    Form for dashboard filtering and search functionality.
    Used for AJAX updates and URL parameter handling.
    """

    STATUS_CHOICES = [
        ("all", "All Students"),
        ("WAITING", "Waiting for Parent"),
        ("PARENT_ARRIVED", "Parent Has Arrived"),
        ("PICKED_UP", "Picked Up"),
    ]

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        initial="all",
        widget=forms.Select(attrs={"class": "form-control", "onchange": "this.form.submit();"}),
    )

    grade = forms.ChoiceField(
        required=False,
        widget=forms.Select(attrs={"class": "form-control", "onchange": "this.form.submit();"}),
    )

    search = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Search by name, code, or teacher..."}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate grade choices dynamically
        grades = (
            Student.objects.filter(is_active=True)
            .values_list("grade", flat=True)
            .distinct()
            .order_by("grade")
        )

        grade_choices = [("all", "All Grades")] + [(g, g) for g in grades]
        self.fields["grade"].choices = grade_choices

    def clean_search(self):
        """Sanitize search input"""
        search = self.cleaned_data.get("search", "").strip()
        return sanitize_input(search, max_length=100)


class QuickActionForm(forms.Form):
    """
    Form for quick actions via AJAX (e.g., quick pickup).
    Used for streamlined mobile interface interactions.
    """

    student_id = forms.IntegerField(widget=forms.HiddenInput())

    action = forms.ChoiceField(
        choices=[
            ("quick_pickup", "Quick Pickup"),
            ("cancel_arrival", "Cancel Arrival"),
        ],
        widget=forms.HiddenInput(),
    )

    notes = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional notes..."}),
    )

    def clean_student_id(self):
        """Validate student exists and is active"""
        student_id = self.cleaned_data["student_id"]

        try:
            student = Student.objects.get(id=student_id, is_active=True)
            # Store student for use in view
            self.student = student
            return student_id
        except Student.DoesNotExist:
            raise ValidationError("Student not found or inactive.")

    def clean_notes(self):
        """Sanitize notes input"""
        notes = self.cleaned_data.get("notes", "").strip()
        return sanitize_input(notes, max_length=200)

    def clean(self):
        """Validate action is appropriate for student status"""
        cleaned_data = super().clean()
        action = cleaned_data.get("action")

        if hasattr(self, "student"):
            student = self.student

            if action == "quick_pickup" and student.current_status != "PARENT_ARRIVED":
                raise ValidationError(
                    f"Cannot complete pickup for {student.name}. "
                    f"Current status: {student.get_current_status_display()}"
                )
            elif action == "cancel_arrival" and student.current_status not in [
                "PARENT_ARRIVED",
                "WAITING",
            ]:
                raise ValidationError(
                    f"Cannot cancel arrival for {student.name}. "
                    f"Current status: {student.get_current_status_display()}"
                )

        return cleaned_data


class BulkActionForm(forms.Form):
    """
    Form for bulk actions on multiple students.
    Used for batch operations like resetting status, etc.
    """

    ACTION_CHOICES = [
        ("reset_status", "Reset to Waiting"),
        ("mark_inactive", "Mark as Inactive"),
        ("generate_new_codes", "Generate New Dismissal Codes"),
    ]

    action = forms.ChoiceField(
        choices=ACTION_CHOICES, widget=forms.Select(attrs={"class": "form-control"})
    )

    student_ids = forms.CharField(
        widget=forms.HiddenInput(), help_text="Comma-separated list of student IDs"
    )

    confirm = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="I confirm I want to perform this bulk action",
    )

    def clean_student_ids(self):
        """Validate student IDs are valid integers"""
        ids_str = self.cleaned_data["student_ids"]

        try:
            ids = [int(id_str.strip()) for id_str in ids_str.split(",") if id_str.strip()]
        except ValueError:
            raise ValidationError("Invalid student IDs provided.")

        if not ids:
            raise ValidationError("No students selected for bulk action.")

        # Verify all students exist
        existing_count = Student.objects.filter(id__in=ids, is_active=True).count()
        if existing_count != len(ids):
            raise ValidationError("Some selected students were not found or are inactive.")

        return ids
