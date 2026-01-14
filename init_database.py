#!/usr/bin/env python3
"""
Initialize Darwin Web Application Database

This script:
1. Creates database tables
2. Creates a test user
3. Creates a test team
4. Adds the user to the team

Usage:
    python3 init_database.py
"""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from darwin.api.db.postgres import engine, SessionLocal
from darwin.api.db.models import User, Team, TeamMember, Base
from darwin.api.utils.security import hash_password

def init_database():
    """Initialize database tables and test data."""
    print("================================")
    print("Darwin Web Application Database Initialization")
    print("================================")
    print("")

    # Create all tables
    print("Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ Tables created successfully")
    except Exception as e:
        print(f"✗ Error creating tables: {e}")
        print("\nMake sure PostgreSQL is running and the database exists.")
        print("Run the following commands to create the database:")
        print("")
        print("  # macOS (Homebrew):")
        print("  brew install postgresql@16")
        print("  brew services start postgresql@16")
        print("  createuser -s darwin")
        print("  createdb -O darwin darwin_web")
        print("")
        print("  # Ubuntu/Debian:")
        print("  sudo apt-get install postgresql")
        print("  sudo systemctl start postgresql")
        print("  sudo -u postgres createuser -s darwin")
        print("  sudo -u postgres createdb -O darwin darwin_web")
        print("")
        sys.exit(1)

    print("")

    # Create session
    db = SessionLocal()

    try:
        # Check if test user already exists
        existing_user = db.query(User).filter(User.email == "test@test.com").first()

        if existing_user:
            print("✓ Test user already exists: test@test.com")
            user = existing_user
        else:
            # Create test user
            user = User(
                email="test@test.com",
                password_hash=hash_password("test123"),
                name="Test User",
                is_active=True,
            )
            db.add(user)
            db.flush()  # Get the user ID
            print("✓ Created test user: test@test.com")

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
        print("Database initialization complete!")
        print("=" * 50)
        print("")
        print("Test credentials:")
        print("  Email:    test@test.com")
        print("  Password: test123")
        print("  Team:     test-team")
        print("")
        print("You can now login at: http://localhost:3001")
        print("")
        print("Next steps:")
        print("  1. Start the backend: python3 -m uvicorn darwin.api.main:app --reload")
        print("  2. Start the frontend: cd darwin-ui && npm run dev")
        print("  3. Login at http://localhost:3001")
        print("")

    except Exception as e:
        db.rollback()
        print(f"\n✗ Error creating test data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
