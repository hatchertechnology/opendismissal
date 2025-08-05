# opendismissal
An application to help streamline and secure school dismissals.


## Problem statement
School dismissals can be chaotic and stressful. Parents often have to wait in long lines to pick up their children, and schools struggle to ensure that only authorized individuals are allowed to take students home. This can lead to safety concerns and delays in the dismissal process.

For example, today dismissal started at 3pm and was still on going at 5pm.

## Additional Context
The example school is set in an urban area with a significant number of students who's walk to and from school. There are no school busses. This means that dismissal is entirely done by car or on foot. The wallk up process is virtually the same as the car pick up process. Parents walk up with the same neon colored paper with the number on it.

## Current System
Currently, the example school uses a paper based system where parents have a neon colored paper with a number on it. The number corresponds to the student's name and is used to verify that the parent is authorized to pick up the student. School staff stand outside and call out numbers over the radio as parents arrive. This system is inefficient and can lead to confusion and delays. This is especially true when weather is bad or parents don't have the paper.

## Basic MVP Features

1. A web application where
   1. school administrators can record the child's name and dismissal code.
   2. School staff can use a smartphone to input the dismissal code as parents arrive.
   3. Another staff member can see a real-time list of students names who's parents have arrived.
   4. As students are taken outside, the staff member can mark them as picked up.
   5. All school staff have individual logins to ensure accountability.
   6. System is secure, private, and compliant with relevant regulations, such as FERPA and FOIA.
   7. Logs are kept of all actions taken in the system for auditing purposes.
   8. Event history is available to school administrators for each student.
2. A way to easily run the application locally such as with docker and compose.
3. A django command that will generate demo data for full user acceptance testing purposes.


## Preferred Tech Stack
1. Backend: Python with Django and Django Rest Framework
2. Frontend: React and Tailwind CSS
3. Authentication: Django Allauth
4. Logging: Loguru via django-easy-logging
5. File Storage: django-storages[s3]
6. Python environment management: UV
7. Linting: ruff, djlint
8. Configuration: python-decouple and .env files
9. Security testing: Bandit and Safety
10. API Documentation: Swagger / OpenAPI
11. Real-time updates: WebSockets with Django Channels
12. Database: PostgreSQL
13. Containerization: Docker and Docker Compose
14. Version Control: Git and GitHub
15. Cache, sessions, and message broker: Redis


## Future Features

Though out of scope for the MVP, don't make any design decisions that would make these features impossible to implement in the future:

1. Mobile and Desktop Applications
   1. Native mobile applications for iOS and Android using Flutter.
   2. Desktop applications using Flutter.
   3. AppleTV applications.
   

## Security Requirements

- Follow OWASP security practices
- All non-public endpoints protected with `@login_required`
- Environment-based configuration with python-decouple
- Security scanning with bandit and safety
- Production security headers configured in settings

## Code Standards

- Follow Django coding conventions
- Use `uv run` prefix for all Python commands
- 100-character line length (ruff configured)
- Conventional Commits specification for commit messages
- Google-style docstrings for functions/classes
- Unit tests required for all new functionality
- Dismissal django project should be maintained in a way to make it a reusable Django app.


## Code Safety

[SonarQube](https://sonarcloud.io/project/overview?id=hatchertechnology_opendismissal) is used to monitor code quality and security. All new code must maintain or improve the current SonarQube rating.

