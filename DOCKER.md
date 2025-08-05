# Docker Deployment Guide for OpenDismissal

This document provides comprehensive instructions for deploying OpenDismissal using Docker in both development and production environments.

## Quick Start

### Development Environment

1. **Prerequisites**
   - Docker and Docker Compose installed
   - Clone the repository

2. **Start Development Environment**
   ```bash
   # Build and start all services
   docker-compose up --build

   # Or run in background
   docker-compose up -d --build
   ```

3. **Access the Application**
   - Django Admin: http://localhost:8000/admin/
   - Main Application: http://localhost:8000/dissmissal/
   - PostgreSQL: localhost:5432
   - Redis: localhost:6379

4. **Create Superuser**
   ```bash
   docker-compose exec web uv run python manage.py createsuperuser
   ```

### Production Environment

1. **Setup Environment**
   ```bash
   # Copy and configure environment file
   cp .env.example .env
   # Edit .env with your production values
   ```

2. **Deploy Production Stack**
   ```bash
   # Use production compose file
   docker-compose -f docker-compose.prod.yml up -d --build
   ```

## File Overview

### Docker Files

- **`Dockerfile`**: Multi-stage production-ready image with security best practices
- **`.dockerignore`**: Excludes unnecessary files from the Docker build context
- **`docker-compose.yml`**: Development environment with PostgreSQL and Redis
- **`docker-compose.prod.yml`**: Production environment with security and performance optimizations
- **`nginx.conf`**: Nginx reverse proxy configuration for production
- **`.env.example`**: Template for environment variables

### Key Features

#### Dockerfile Security Features
- **Multi-stage build**: Reduces final image size and attack surface
- **Non-root user**: Application runs as `appuser` for security
- **Minimal base image**: Uses Python 3.13 slim for smaller footprint
- **Dependency isolation**: Uses UV virtual environment
- **Health checks**: Built-in application health monitoring
- **Proper permissions**: Correct file and directory permissions

#### Production Optimizations
- **Static file collection**: Automatic static file handling
- **Database migrations**: Automatic migration on startup
- **Resource limits**: Memory and CPU constraints
- **Logging configuration**: Structured logging with rotation
- **SSL/TLS ready**: Nginx configuration supports HTTPS

## Environment Variables

### Required Variables (Production)

```bash
# Django Core
SECRET_KEY=your-very-secure-secret-key-minimum-50-characters
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DATABASE_URL=postgresql://user:password@host:5432/database
POSTGRES_DB=opendismissal
POSTGRES_USER=opendismissal_user  
POSTGRES_PASSWORD=secure_database_password

# Redis
REDIS_URL=redis://:password@host:6379/1
REDIS_PASSWORD=secure_redis_password
```

### Optional Variables

```bash
# Application
TIME_ZONE=America/New_York
DJANGO_LOG_LEVEL=INFO
WEB_PORT=8000

# Email (for admin notifications)
EMAIL_HOST=smtp.provider.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@domain.com
EMAIL_HOST_PASSWORD=your-email-password
EMAIL_USE_TLS=True

# Security Headers
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True

# Rate Limiting
RATELIMIT_ENABLE=True
```

## Common Commands

### Development

```bash
# View logs
docker-compose logs -f web

# Execute commands in container
docker-compose exec web uv run python manage.py shell
docker-compose exec web uv run python manage.py migrate
docker-compose exec web uv run python manage.py collectstatic

# Run tests
docker-compose exec web uv run python manage.py test

# Access database
docker-compose exec postgres psql -U postgres -d opendismissal

# Access Redis
docker-compose exec redis redis-cli
```

### Production

```bash
# Deploy/update
docker-compose -f docker-compose.prod.yml up -d --build

# View production logs
docker-compose -f docker-compose.prod.yml logs -f web

# Scale application (if needed)
docker-compose -f docker-compose.prod.yml up -d --scale web=3

# Backup database
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup.sql

# Monitor resource usage
docker stats
```

## Deployment Strategies

### Rolling Updates

```bash
# Build new image
docker-compose -f docker-compose.prod.yml build web

# Rolling update (zero downtime)
docker-compose -f docker-compose.prod.yml up -d --no-deps web
```

### Health Checks

The application includes built-in health checks:

- **Application**: `GET /admin/login/` (returns 200 if healthy)
- **Database**: Automatic Django database check
- **Dependencies**: PostgreSQL and Redis health checks

### Monitoring

```bash
# Check container health
docker-compose ps

# View resource usage
docker stats

# Check logs for errors
docker-compose logs web | grep ERROR
```

## Security Considerations

### Production Security Checklist

- [ ] Set strong `SECRET_KEY` (minimum 50 characters)
- [ ] Configure `ALLOWED_HOSTS` for your domain
- [ ] Use HTTPS with SSL certificates
- [ ] Set secure database credentials
- [ ] Configure Redis password
- [ ] Enable security headers in Nginx
- [ ] Set up log monitoring and alerting
- [ ] Configure firewall rules
- [ ] Regular security updates
- [ ] Backup strategy implementation

### Network Security

The production setup uses internal Docker networks:
- PostgreSQL and Redis are not exposed to the host
- Only the web application port is exposed
- Nginx handles SSL termination and security headers

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   ```bash
   # Check database is running
   docker-compose ps postgres
   
   # Check database logs
   docker-compose logs postgres
   
   # Test connection
   docker-compose exec web uv run python manage.py check --deploy
   ```

2. **Static Files Not Loading**
   ```bash
   # Collect static files
   docker-compose exec web uv run python manage.py collectstatic --clear
   
   # Check nginx static file serving
   docker-compose logs nginx
   ```

3. **Permission Issues**
   ```bash
   # Fix log directory permissions
   docker-compose exec web chown -R appuser:appuser /app/logs
   ```

4. **Memory Issues**
   ```bash
   # Check container memory usage
   docker stats
   
   # Adjust resource limits in docker-compose.prod.yml
   ```

### Performance Tuning

1. **Database Optimization**
   - Configure PostgreSQL shared_buffers
   - Set appropriate connection limits
   - Enable connection pooling

2. **Redis Configuration**
   - Set appropriate memory limits
   - Configure persistence settings
   - Monitor cache hit rates

3. **Django Settings**
   - Configure database connection pooling
   - Set appropriate cache timeouts
   - Enable gzip compression

## Backup and Recovery

### Database Backups

```bash
# Create backup
docker-compose exec postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
docker-compose exec -T postgres psql -U $POSTGRES_USER $POSTGRES_DB < backup.sql
```

### Volume Backups

```bash
# Backup all volumes
docker run --rm -v opendismissal_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz -C /data .
docker run --rm -v opendismissal_redis_data:/data -v $(pwd):/backup alpine tar czf /backup/redis_backup.tar.gz -C /data .
```

## Scaling Considerations

### Horizontal Scaling

```bash
# Scale web application containers
docker-compose -f docker-compose.prod.yml up -d --scale web=3

# Use load balancer (nginx upstream configuration)
# Configure session affinity if needed
```

### Vertical Scaling

Adjust resource limits in `docker-compose.prod.yml`:

```yaml
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '0.5'
    reservations:
      memory: 512M
      cpus: '0.25'
```

This Docker deployment provides a robust, secure, and scalable foundation for the OpenDismissal application.