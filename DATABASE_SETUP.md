# Darwin Web Application - Database Setup Guide

This guide will help you set up PostgreSQL for the Darwin web application to enable authentication and team management.

## Quick Start

### 1. Install PostgreSQL

**macOS (using Homebrew):**
```bash
brew install postgresql@16
brew services start postgresql@16
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 2. Create Database and User

**macOS:**
```bash
createdb darwin_web
```

The `darwin` user is not needed on macOS since you'll connect as your system user.

**Ubuntu/Debian:**
```bash
# Switch to postgres user
sudo -u postgres psql

# In the PostgreSQL prompt:
CREATE USER darwin WITH PASSWORD 'password';
CREATE DATABASE darwin_web OWNER darwin;
GRANT ALL PRIVILEGES ON DATABASE darwin_web TO darwin;
\q
```

### 3. Update Environment Variables (if needed)

The `.env` file already has the default configuration:

```bash
DATABASE_URL=postgresql://darwin:password@localhost:5432/darwin_web
```

If you used different credentials, update this line in `.env`.

**For macOS users:** You may need to change the connection string to use your system username:
```bash
DATABASE_URL=postgresql://yourusername@localhost:5432/darwin_web
```

### 4. Initialize Database

Run the initialization script to create tables and test user:

```bash
python3 init_database.py
```

This will:
- Create all necessary database tables (users, teams, team_members, etc.)
- Create a test user: `test@darwin.local` / `test123`
- Create a test team: `test-team`
- Add the test user to the team as admin

### 5. Start the Application

**Terminal 1 - Backend:**
```bash
python3 -m uvicorn darwin.api.main:app --reload
```

**Terminal 2 - Frontend:**
```bash
cd darwin-ui
npm run dev
```

### 6. Login

Visit http://localhost:3001 and login with:
- **Email:** test@darwin.local
- **Password:** test123

## Troubleshooting

### "connection refused" error

Make sure PostgreSQL is running:
```bash
# macOS
brew services list | grep postgresql
brew services start postgresql@16

# Ubuntu/Debian
sudo systemctl status postgresql
sudo systemctl start postgresql
```

### "peer authentication failed" error (Linux)

Edit `/etc/postgresql/*/main/pg_hba.conf`:

Change this line:
```
local   all             all                                     peer
```

To:
```
local   all             all                                     md5
```

Then restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

### "database does not exist" error

Create the database:
```bash
# macOS
createdb darwin_web

# Ubuntu/Debian
sudo -u postgres createdb darwin_web
```

### "role does not exist" error (Ubuntu/Debian)

Create the user:
```bash
sudo -u postgres psql -c "CREATE USER darwin WITH PASSWORD 'password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE darwin_web TO darwin;"
```

## Alternative: Using SQLite (Development Only)

If you don't want to install PostgreSQL for development, you can use SQLite instead:

1. Update `darwin/api/db/postgres.py` to use SQLite:
```python
DATABASE_URL = os.getenv(
    "DATABASE_URL", "sqlite:///./darwin_web.db"
)
```

2. Run the initialization script:
```bash
python3 init_database.py
```

**Note:** SQLite is not recommended for production use due to:
- Limited concurrent write support
- No user authentication built-in
- Missing advanced features like full-text search

## Database Schema

The application uses the following tables:

- `users` - User accounts
- `teams` - Team/organization information
- `team_members` - User-team relationships with roles
- `team_invitations` - Pending team invitations
- `sessions` - Session tracking (optional)
- `run_metadata` - Run ownership and status

## Next Steps

After setting up the database:

1. **Explore the API**: Visit http://localhost:8000/docs for interactive API documentation
2. **Create runs**: Use the web UI to configure and launch backtests
3. **View reports**: Analyze performance metrics and trade history
4. **Invite team members**: Add collaborators via the team management page

## Need Help?

- Check the main README.md for general application documentation
- Review the API documentation at http://localhost:8000/docs
- File issues on GitHub (if available)
