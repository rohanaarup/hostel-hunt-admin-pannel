# Hostel Hunt – Admin Panel & Backend

A full-stack accommodation management platform consisting of a Django REST API and a React-based administration interface.

## Overview

Hostel Hunt provides a platform for discovering and managing PG and hostel accommodation.

The backend handles application data, authentication, business logic, and API communication. The administration panel provides an interface for managing the platform.

## Technology Stack

### Backend

- Python
- Django
- Django REST Framework
- PostgreSQL
- JWT Authentication
- Django ORM

### Frontend

- React
- Vite
- TypeScript
- Tailwind CSS

### Infrastructure & Tools

- Supabase
- Render
- GitHub Actions
- Postman
- Git

## Core Functional Areas

- User authentication
- Hostel and PG management
- Property discovery and filtering
- Booking management
- User management
- Wishlist functionality
- Payment integration
- Administrative operations

## High-Level Architecture

```text
             Mobile Application
                    |
                    v
              Django REST API
                    |
          ---------------------
          |         |         |
       Auth     Business    Booking
          |       Logic       |
          ---------------------
                    |
                    v
                PostgreSQL
                    |
                    v
             Admin Dashboard
              React + Vite
```

## Local Setup

### Backend

Clone the repository:

```bash
git clone https://github.com/rohanaarup/hostel-hunt-admin-pannel.git
```

Navigate into the project directory:

```bash
cd hostel-hunt-admin-pannel
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure the required environment variables using the project's environment configuration.

Run Django checks:

```bash
python manage.py check
```

Check for uncommitted migration changes:

```bash
python manage.py makemigrations --check --dry-run
```

Run tests:

```bash
python manage.py test
```

Start the backend:

```bash
python manage.py runserver
```

### Frontend

Navigate to the frontend directory:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

Check the available scripts in `package.json` before running optional lint or build commands.

## Engineering Considerations

Areas that require particular attention in a booking platform include:

- Authentication and authorization
- Booking lifecycle consistency
- Availability and bed allocation
- Payment verification
- Database transactions
- API validation
- Error handling
- User data isolation

## Testing & Quality

The project includes backend and frontend development infrastructure.

Automated tests, deployment verification, and integration testing should be run against the current environment before treating a feature as production-ready.

## Known Limitations

Some booking, payment, and availability workflows require further verification and improvement. Consult `KNOWN_GAPS.md` for documented outstanding issues.

## Deployment

Deployment configuration and environment requirements are documented in `DEPLOY.md`.

Do not publish secrets, database credentials, or production environment files.

## Author

**Rohan**

GitHub: https://github.com/rohanaarup
