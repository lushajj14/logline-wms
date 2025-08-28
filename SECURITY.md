# Security Configuration

## API Secret Key Setup

The API uses JWT tokens for authentication. You **MUST** set a secure secret key before running in production.

### Generate a Secret Key

Run the provided script:
```bash
python generate_secret.py
```

### Set the Secret Key

#### Option 1: Environment Variable
```bash
# Windows
set API_SECRET=your_generated_secret_here

# Linux/Mac
export API_SECRET=your_generated_secret_here
```

#### Option 2: .env File
Create a `.env` file in the project root:
```
API_SECRET=your_generated_secret_here
```

### Important Security Notes

1. **NEVER commit the secret key to version control**
2. **NEVER use the default/example secret in production**
3. **Generate a new secret for each environment** (dev, staging, prod)
4. **Store production secrets securely** (e.g., Azure Key Vault, AWS Secrets Manager)
5. **Rotate secrets periodically** (recommended: every 90 days)

### Production Check

The API will refuse to start in production without a proper secret:
```bash
# This will cause the API to exit if API_SECRET is not set
export ENVIRONMENT=production
```

## Database Credentials

Database credentials should also be set via environment variables:

```bash
# Required environment variables
export LOGO_SQL_SERVER=your_server
export LOGO_SQL_DB=your_database
export LOGO_SQL_USER=your_user
export LOGO_SQL_PASSWORD=your_password

# Optional
export DB_CONN_TIMEOUT=10  # Connection timeout in seconds
```

## Security Best Practices

1. **Use HTTPS only** in production
2. **Enable CORS restrictions** for API endpoints
3. **Implement rate limiting** on authentication endpoints
4. **Use strong passwords** with minimum complexity requirements
5. **Enable audit logging** for sensitive operations
6. **Regular security updates** for all dependencies
7. **Network isolation** - Database should not be directly accessible from internet
8. **Principle of least privilege** - Use read-only database users where possible