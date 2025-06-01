# Debt Tracker API

A simplified FastAPI application for tracking personal debts and managing contacts.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file in the root directory:
```bash
# Database
DATABASE_URL=sqlite:///./debt_tracker.db

# Email Configuration
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_FROM=your-email@gmail.com

# Security
SECRET_KEY=your-super-secret-key-here
DEBUG=False

# App Settings
APP_NAME=Debt Tracker API
APP_VERSION=2.0.0
```

### 3. Run the Application
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

## 📚 API Documentation

### Interactive Docs
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Health Check
- **GET** `/` - API status
- **GET** `/health` - Health check

## 🔐 Authentication Flow

### 1. Register User
```bash
POST /auth/register
{
  "email": "user@example.com",
  "password": "password123",
  "fullname": "John Doe"
}
```

### 2. Verify Email
```bash
POST /auth/verify-email
{
  "email": "user@example.com",
  "code": "123456"
}
```

### 3. Login
```bash
POST /auth/login
{
  "email": "user@example.com",
  "password": "password123"
}
```

### 4. Use Token
Include the token in the Authorization header for protected endpoints:
```bash
Authorization: Bearer your-jwt-token-here
```

## 📱 Core Features

### Contact Management
- Create, read, update, delete contacts
- Each contact shows debt summary
- Phone number uniqueness per user

### Debt Tracking
- Track who owes money to whom
- Mark debts as paid/unpaid
- Filter debts by status, type, or contact
- Get debt overview with totals

### Email Features
- Email verification during registration
- Password reset via email
- Automatic code generation and expiration

## 🛠️ API Endpoints

### Authentication (`/auth`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new user |
| POST | `/auth/verify-email` | Verify email with code |
| POST | `/auth/login` | Login user |
| GET | `/auth/me` | Get current user info |
| POST | `/auth/forgot-password` | Request password reset |
| POST | `/auth/reset-password` | Reset password |
| POST | `/auth/resend-code` | Resend verification code |

### Contacts (`/contacts`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/contacts` | Create contact |
| GET | `/contacts` | List all contacts |
| GET | `/contacts/{id}` | Get specific contact |
| PUT | `/contacts/{id}` | Update contact |
| DELETE | `/contacts/{id}` | Delete contact |

### Debts (`/debts`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/debts` | Create debt |
| GET | `/debts` | List debts (with filters) |
| GET | `/debts/overview` | Get debt summary |
| GET | `/debts/{id}` | Get specific debt |
| PUT | `/debts/{id}` | Update debt |
| DELETE | `/debts/{id}` | Delete debt |
| PATCH | `/debts/{id}/pay` | Mark debt as paid |

## 📊 Response Format

### Success Response
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": { ... },
  "timestamp": "2025-06-01T12:00:00Z"
}
```

### Error Response
```json
{
  "success": false,
  "message": "Error description",
  "errors": ["Detailed error messages"],
  "timestamp": "2025-06-01T12:00:00Z"
}
```

## 🗃️ Database Schema

### Users
- `id` - Primary key
- `email` - Unique email address
- `password` - Hashed password
- `fullname` - User's full name
- `is_verified` - Email verification status
- `created_at` - Registration timestamp

### Contacts
- `id` - Primary key
- `name` - Contact's name
- `phone` - Phone number (unique per user)
- `user_id` - Foreign key to users
- `created_at` - Creation timestamp

### Debts
- `id` - Primary key
- `amount` - Debt amount (float)
- `description` - Debt description
- `is_paid` - Payment status (boolean)
- `is_my_debt` - Direction (true = I owe them, false = they owe me)
- `contact_id` - Foreign key to contacts
- `created_at` - Creation timestamp

### Verification Codes
- `id` - Primary key
- `email` - Email address
- `code` - 6-digit verification code
- `code_type` - Type: "email" or "password_reset"
- `expires_at` - Expiration timestamp
- `used` - Usage status
- `created_at` - Creation timestamp

## 🔧 Configuration

### Email Setup (Gmail)
1. Enable 2-factor authentication on your Gmail account
2. Generate an app-specific password
3. Use the app password in `MAIL_PASSWORD`

### Security
- Change `SECRET_KEY` to a secure random string
- Set `DEBUG=False` in production
- Use HTTPS in production

## 📝 Example Usage

### Complete User Flow
```bash
# 1. Register
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "securepass123",
    "fullname": "John Doe"
  }'

# 2. Verify email (check your inbox for code)
curl -X POST "http://localhost:8000/auth/verify-email" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "code": "123456"
  }'

# 3. Login
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "securepass123"
  }'

# 4. Create contact (use token from login)
curl -X POST "http://localhost:8000/contacts" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Smith",
    "phone": "+1234567890"
  }'

# 5. Add debt
curl -X POST "http://localhost:8000/debts" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "contact_id": 1,
    "amount": 50.00,
    "description": "Lunch money",
    "is_my_debt": false
  }'

# 6. Get overview
curl -X GET "http://localhost:8000/debts/overview" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## 🚀 Deployment

### Using Docker (Optional)
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Using Gunicorn (Production)
```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## 🛡️ Security Features

- **Password Hashing**: Bcrypt with salt
- **JWT Tokens**: 7-day expiration
- **Email Verification**: Required for account activation
- **Input Validation**: Pydantic models
- **SQL Injection Protection**: SQLAlchemy ORM
- **CORS Protection**: Built-in FastAPI middleware
- **Rate Limiting**: Built-in request validation

## 📦 Dependencies

### Core Dependencies
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `sqlalchemy` - ORM
- `passlib[bcrypt]` - Password hashing
- `python-jose[cryptography]` - JWT tokens
- `fastapi-mail` - Email sending
- `python-dotenv` - Environment variables
- `pydantic[email]` - Data validation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is open source and available under the MIT License.

## 🐛 Troubleshooting

### Common Issues

**Email not sending:**
- Check Gmail app password
- Verify SMTP settings
- Ensure 2FA is enabled on Gmail

**Database errors:**
- Delete `debt_tracker.db` to reset
- Check file permissions
- Verify SQLite installation

**JWT token issues:**
- Check SECRET_KEY configuration
- Verify token format in Authorization header
- Ensure token hasn't expired

**Import errors:**
- Install all requirements: `pip install -r requirements.txt`
- Check Python version (3.7+ required)
- Verify virtual environment activation

### Support

For issues and questions:
1. Check the troubleshooting section
2. Review API documentation at `/docs`
3. Check logs for detailed error messages
4. Ensure all environment variables are set correctly