# ArchViz Platform

A backend API for architectural visualization studios. Clients submit projects
and reference files, an admin assigns an artist, the artist uploads render
versions, and the client reviews them and requests revisions until approval.

**Highlights**
- Custom user model with client, artist and admin roles
- Project status workflow (state machine) with an audit log
- JWT authentication and role-based permissions
- File uploads with background image processing (thumbnails and watermarked previews) using Celery and Redis
- Email notifications on status changes
- Dockerized stack (Django, Celery worker, PostgreSQL, Redis) and GitHub Actions CI
- Automated tests with pytest