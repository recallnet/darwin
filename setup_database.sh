#!/bin/bash
set -e

echo "================================"
echo "Darwin Web Application Database Setup"
echo "================================"
echo ""

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "PostgreSQL is not installed."
    echo ""
    echo "On macOS, install with:"
    echo "  brew install postgresql@16"
    echo "  brew services start postgresql@16"
    echo ""
    echo "On Ubuntu/Debian, install with:"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install postgresql postgresql-contrib"
    echo "  sudo systemctl start postgresql"
    echo ""
    echo "Please install PostgreSQL and run this script again."
    exit 1
fi

echo "✓ PostgreSQL is installed"

# Check if PostgreSQL server is running
if ! pg_isready -h localhost -p 5432 &> /dev/null; then
    echo ""
    echo "PostgreSQL server is not running."
    echo ""
    echo "Start it with:"
    echo "  macOS (Homebrew): brew services start postgresql@16"
    echo "  Ubuntu/Debian: sudo systemctl start postgresql"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo "✓ PostgreSQL server is running"
echo ""

# Database configuration
DB_NAME="darwin_web"
DB_USER="darwin"
DB_PASSWORD="password"

# Get the current PostgreSQL superuser
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - use current user
    PG_SUPERUSER="$USER"
else
    # Linux - use postgres user
    PG_SUPERUSER="postgres"
fi

echo "Creating database and user..."
echo ""

# Create database user if it doesn't exist
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    psql -U "$PG_SUPERUSER" -d postgres -tc "SELECT 1 FROM pg_user WHERE usename = '$DB_USER'" | grep -q 1 || \
        psql -U "$PG_SUPERUSER" -d postgres -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
else
    # Linux
    sudo -u postgres psql -tc "SELECT 1 FROM pg_user WHERE usename = '$DB_USER'" | grep -q 1 || \
        sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
fi

echo "✓ User '$DB_USER' created/verified"

# Create database if it doesn't exist
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    psql -U "$PG_SUPERUSER" -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || \
        psql -U "$PG_SUPERUSER" -d postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
else
    # Linux
    sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || \
        sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
fi

echo "✓ Database '$DB_NAME' created/verified"
echo ""

# Grant privileges
if [[ "$OSTYPE" == "darwin"* ]]; then
    psql -U "$PG_SUPERUSER" -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
else
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
fi

echo "✓ Privileges granted"
echo ""

echo "Running database migrations..."
echo ""

# Run Alembic migrations
cd "$(dirname "$0")"
python3 -m alembic -c darwin/api/db/migrations/alembic.ini upgrade head

echo ""
echo "✓ Migrations completed"
echo ""

echo "Creating test user..."
echo ""

# Create a test user using Python
python3 << 'PYTHON_SCRIPT'
import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from darwin.api.db.postgres import SessionLocal
from darwin.api.db.models import User, Team, TeamMember
from darwin.api.utils.security import hash_password

# Create session
db = SessionLocal()

try:
    # Check if test user already exists
    existing_user = db.query(User).filter(User.email == "test@darwin.local").first()

    if existing_user:
        print("✓ Test user already exists: test@darwin.local")
        user = existing_user
    else:
        # Create test user
        user = User(
            email="test@darwin.local",
            password_hash=hash_password("test123"),
            name="Test User",
            is_active=True,
        )
        db.add(user)
        db.flush()  # Get the user ID
        print("✓ Created test user: test@darwin.local")

    # Check if test team exists
    existing_team = db.query(Team).filter(Team.slug == "test-team").first()

    if existing_team:
        print("✓ Test team already exists: test-team")
        team = existing_team
    else:
        # Create test team
        team = Team(
            name="Test Team",
            slug="test-team",
            created_by=user.id,
        )
        db.add(team)
        db.flush()  # Get the team ID
        print("✓ Created test team: test-team")

    # Check if membership exists
    existing_membership = db.query(TeamMember).filter(
        TeamMember.user_id == user.id,
        TeamMember.team_id == team.id
    ).first()

    if not existing_membership:
        # Add user to team as admin
        membership = TeamMember(
            user_id=user.id,
            team_id=team.id,
            role="admin",
        )
        db.add(membership)
        print("✓ Added user to team as admin")
    else:
        print("✓ User is already a member of the team")

    # Commit changes
    db.commit()
    print("")
    print("=" * 50)
    print("Test credentials created successfully!")
    print("=" * 50)
    print("")
    print("  Email:    test@darwin.local")
    print("  Password: test123")
    print("  Team:     test-team")
    print("")
    print("You can now login at: http://localhost:3001")
    print("")

except Exception as e:
    db.rollback()
    print(f"Error creating test user: {e}", file=sys.stderr)
    sys.exit(1)
finally:
    db.close()

PYTHON_SCRIPT

echo ""
echo "================================"
echo "Database setup complete!"
echo "================================"
echo ""
echo "Your Darwin web application database is ready."
echo ""
echo "Next steps:"
echo "  1. Start the backend: cd darwin && python3 -m uvicorn darwin.api.main:app --reload"
echo "  2. Start the frontend: cd darwin-ui && npm run dev"
echo "  3. Login at http://localhost:3001 with the test credentials"
echo ""
