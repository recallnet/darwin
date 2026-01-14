#!/usr/bin/env python3
"""
Validate .env file for Darwin deployment.

This script checks that all required environment variables are set
and have valid values before deploying to Docker/Railway/Vercel.
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse


def check_required_var(name: str, value: str | None, validators: list = None) -> bool:
    """Check if a required variable is set and valid."""
    if not value or value.strip() == "":
        print(f"❌ {name}: Not set or empty")
        return False

    # Run validators if provided
    if validators:
        for validator in validators:
            is_valid, error_msg = validator(value)
            if not is_valid:
                print(f"❌ {name}: {error_msg}")
                return False

    # Mask sensitive values in output
    if any(secret in name.lower() for secret in ["key", "secret", "password"]):
        display_value = value[:8] + "..." if len(value) > 8 else "***"
    else:
        display_value = value if len(value) < 60 else value[:57] + "..."

    print(f"✅ {name}: {display_value}")
    return True


def validate_url(value: str) -> tuple[bool, str]:
    """Validate URL format."""
    try:
        result = urlparse(value)
        if not all([result.scheme, result.netloc]):
            return False, "Invalid URL format (missing scheme or netloc)"
        if result.scheme not in ["http", "https", "redis", "postgresql"]:
            return False, f"Invalid URL scheme: {result.scheme}"
        return True, ""
    except Exception as e:
        return False, f"Invalid URL: {str(e)}"


def validate_jwt_secret(value: str) -> tuple[bool, str]:
    """Validate JWT secret length."""
    if len(value) < 32:
        return False, f"Too short ({len(value)} chars, need 32+)"
    return True, ""


def validate_port(value: str) -> tuple[bool, str]:
    """Validate port number."""
    try:
        port = int(value)
        if not (1 <= port <= 65535):
            return False, f"Port out of range: {port}"
        return True, ""
    except ValueError:
        return False, "Not a valid port number"


def main():
    """Main validation function."""
    print("=" * 70)
    print("Darwin Deployment Environment Validation")
    print("=" * 70)
    print()

    # Load .env file
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        print(f"❌ .env file not found at: {env_path}")
        print()
        print("Please copy .env.example to .env and configure it:")
        print("  cp .env.example .env")
        sys.exit(1)

    # Parse .env file
    env_vars = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key] = value

    print(f"Found .env file with {len(env_vars)} variables")
    print()

    # Track validation results
    all_valid = True
    warnings = []

    # ===== Required for Core Darwin =====
    print("--- Core Darwin Configuration ---")
    all_valid &= check_required_var(
        "AI_GATEWAY_BASE_URL",
        env_vars.get("AI_GATEWAY_BASE_URL"),
        [validate_url]
    )
    all_valid &= check_required_var(
        "AI_GATEWAY_API_KEY",
        env_vars.get("AI_GATEWAY_API_KEY")
    )
    all_valid &= check_required_var(
        "MODEL_ID",
        env_vars.get("MODEL_ID")
    )
    print()

    # ===== Required for Web API =====
    print("--- Web API Configuration ---")
    all_valid &= check_required_var(
        "DATABASE_URL",
        env_vars.get("DATABASE_URL"),
        [validate_url]
    )
    all_valid &= check_required_var(
        "REDIS_URL",
        env_vars.get("REDIS_URL"),
        [validate_url]
    )
    all_valid &= check_required_var(
        "JWT_SECRET_KEY",
        env_vars.get("JWT_SECRET_KEY"),
        [validate_jwt_secret]
    )
    all_valid &= check_required_var(
        "JWT_ALGORITHM",
        env_vars.get("JWT_ALGORITHM")
    )
    all_valid &= check_required_var(
        "API_PORT",
        env_vars.get("API_PORT"),
        [validate_port]
    )
    print()

    # ===== Required for Frontend =====
    print("--- Frontend Configuration ---")
    all_valid &= check_required_var(
        "NEXTAUTH_SECRET",
        env_vars.get("NEXTAUTH_SECRET"),
        [validate_jwt_secret]
    )

    nextauth_url = env_vars.get("NEXTAUTH_URL")
    if nextauth_url:
        if "localhost" in nextauth_url:
            print(f"⚠️  NEXTAUTH_URL: {nextauth_url} (localhost - update for production)")
            warnings.append("NEXTAUTH_URL uses localhost - update after Vercel deployment")
        else:
            check_required_var("NEXTAUTH_URL", nextauth_url, [validate_url])
    else:
        print("❌ NEXTAUTH_URL: Not set")
        all_valid = False
    print()

    # ===== Optional but Recommended =====
    print("--- Optional Configuration ---")

    replay_lab_url = env_vars.get("REPLAY_LAB_URL")
    if replay_lab_url:
        check_required_var("REPLAY_LAB_URL", replay_lab_url, [validate_url])
    else:
        print("⚠️  REPLAY_LAB_URL: Not set (will fall back to synthetic data)")
        warnings.append("REPLAY_LAB_URL not set - may limit historical data access")

    smtp_host = env_vars.get("SMTP_HOST")
    if not smtp_host or smtp_host.startswith("#"):
        print("⚠️  SMTP_HOST: Not configured (team invitations disabled)")
        warnings.append("SMTP not configured - team invitation emails won't work")
    else:
        check_required_var("SMTP_HOST", smtp_host)
        check_required_var("SMTP_PORT", env_vars.get("SMTP_PORT"), [validate_port])
        check_required_var("SMTP_USER", env_vars.get("SMTP_USER"))
        check_required_var("SMTP_PASSWORD", env_vars.get("SMTP_PASSWORD"))
    print()

    # ===== CORS Configuration =====
    print("--- CORS Configuration ---")
    allowed_origins = env_vars.get("ALLOWED_ORIGINS")
    if allowed_origins:
        origins = [o.strip() for o in allowed_origins.split(",")]
        print(f"✅ ALLOWED_ORIGINS: {len(origins)} origin(s) configured")
        for origin in origins:
            print(f"   - {origin}")

        if any("localhost" in o for o in origins):
            warnings.append("ALLOWED_ORIGINS includes localhost - add production domains after deployment")
    else:
        print("❌ ALLOWED_ORIGINS: Not set")
        all_valid = False
    print()

    # ===== Deployment-Specific Checks =====
    print("--- Deployment Readiness ---")

    # Check for Docker/Railway deployment
    if env_vars.get("DATABASE_URL", "").startswith("postgresql://"):
        db_url = env_vars["DATABASE_URL"]
        if "localhost" in db_url:
            print("⚠️  DATABASE_URL uses localhost")
            warnings.append("DATABASE_URL uses localhost - update for Railway deployment")
        else:
            print(f"✅ DATABASE_URL configured for remote database")

    if env_vars.get("REDIS_URL", "").startswith("redis://"):
        redis_url = env_vars["REDIS_URL"]
        if "localhost" in redis_url:
            print("⚠️  REDIS_URL uses localhost")
            warnings.append("REDIS_URL uses localhost - update for Railway deployment")
        else:
            print(f"✅ REDIS_URL configured for remote Redis")
    print()

    # ===== Summary =====
    print("=" * 70)
    if all_valid:
        print("✅ All required variables are set and valid!")
        if warnings:
            print()
            print("Warnings:")
            for i, warning in enumerate(warnings, 1):
                print(f"  {i}. {warning}")
        print()
        print("Next steps:")
        print("  1. For Docker: docker-compose up -d")
        print("  2. For Railway: See RAILWAY_SETUP.md")
        print("  3. For Vercel: See VERCEL_SETUP.md")
        sys.exit(0)
    else:
        print("❌ Validation failed! Please fix the errors above.")
        if warnings:
            print()
            print("Warnings:")
            for i, warning in enumerate(warnings, 1):
                print(f"  {i}. {warning}")
        print()
        print("See .env.example for reference configuration")
        sys.exit(1)


if __name__ == "__main__":
    main()
