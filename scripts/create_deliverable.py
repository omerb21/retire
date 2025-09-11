#!/usr/bin/env python3
"""
Create deployment deliverable ZIP package
"""
import os
import zipfile
import hashlib
import json
from datetime import datetime
from pathlib import Path

def calculate_sha256(file_path):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def create_deliverable_zip():
    """Create complete deployment deliverable"""
    
    # Configuration
    project_root = Path(__file__).parent.parent
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version = "1.0.0"
    
    # Output paths
    artifacts_dir = project_root / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    
    zip_filename = f"retirement-system-v{version}-{timestamp}.zip"
    zip_path = artifacts_dir / zip_filename
    
    # Files to include in deliverable
    include_patterns = [
        "app/**/*.py",
        "models/**/*.py",
        "routes/**/*.py",
        "services/**/*.py",
        "utils/**/*.py",
        "schemas/**/*.py",
        "db/**/*.py",
        "tests/**/*.py",
        "alembic/**/*",
        "migrations/**/*.sql",
        "scripts/**/*",
        "docs/**/*.md",
        "*.py",
        "*.txt",
        "*.ini",
        "*.yml",
        "*.yaml",
        "*.md",
        "Dockerfile*",
        "docker-compose*.yml",
        "nginx.conf",
        ".github/workflows/*.yml"
    ]
    
    # Files to exclude
    exclude_patterns = [
        "**/__pycache__/**",
        "**/.pytest_cache/**",
        "**/htmlcov/**",
        "**/*.pyc",
        "**/*.pyo",
        "**/*.db",
        "**/*.sqlite",
        "**/logs/**",
        "**/temp/**",
        "**/.coverage",
        "**/coverage.xml",
        "**/.env",
        "**/.env.local",
        "**/node_modules/**",
        "**/.git/**",
        "**/artifacts/**"
    ]
    
    print(f"🏗️ Creating deliverable package: {zip_filename}")
    
    # Create ZIP file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        
        # Add project files
        for pattern in include_patterns:
            for file_path in project_root.glob(pattern):
                if file_path.is_file():
                    # Check if file should be excluded
                    should_exclude = False
                    for exclude_pattern in exclude_patterns:
                        if file_path.match(exclude_pattern):
                            should_exclude = True
                            break
                    
                    if not should_exclude:
                        # Calculate relative path
                        rel_path = file_path.relative_to(project_root)
                        zipf.write(file_path, rel_path)
                        print(f"  ✓ Added: {rel_path}")
        
        # Create deployment manifest
        manifest = {
            "package_name": "retirement-planning-system",
            "version": version,
            "build_timestamp": timestamp,
            "build_date": datetime.now().isoformat(),
            "components": {
                "api_server": "FastAPI application with REST endpoints",
                "database": "PostgreSQL with Alembic migrations",
                "pdf_generation": "ReportLab with matplotlib charts",
                "calculation_engine": "Pension and cashflow calculations",
                "xml_import": "Product data import and mapping",
                "logging": "Comprehensive calculation audit trail"
            },
            "deployment": {
                "docker": "Multi-stage Dockerfile with production optimizations",
                "docker_compose": "Full stack with PostgreSQL, Redis, Nginx",
                "migrations": "Alembic database migrations",
                "health_checks": "Application and database health monitoring"
            },
            "testing": {
                "unit_tests": "Comprehensive unit test coverage",
                "integration_tests": "API and database integration tests",
                "e2e_tests": "Complete workflow end-to-end tests",
                "ci_cd": "GitHub Actions pipeline with security scanning"
            },
            "requirements": {
                "python": "3.11+",
                "database": "PostgreSQL 12+",
                "memory": "2GB+ recommended",
                "storage": "5GB+ for data and logs"
            }
        }
        
        # Add manifest to ZIP
        manifest_json = json.dumps(manifest, indent=2, ensure_ascii=False)
        zipf.writestr("DEPLOYMENT_MANIFEST.json", manifest_json)
        print("  ✓ Added: DEPLOYMENT_MANIFEST.json")
        
        # Create installation instructions
        install_instructions = """# Retirement Planning System - Installation Guide

## Quick Start with Docker

1. Extract the deployment package
2. Navigate to the project directory
3. Run the deployment script:
   ```bash
   chmod +x scripts/deploy.sh
   ./scripts/deploy.sh staging
   ```

## Manual Installation

### Prerequisites
- Python 3.11+
- PostgreSQL 12+
- Docker (optional)

### Steps
1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up database:
   ```bash
   # Create database
   createdb retirement_db
   
   # Run migrations
   alembic upgrade head
   ```

3. Start the application:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

## Configuration

### Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `ENVIRONMENT`: production/staging/development
- `DEBUG`: Enable debug mode (development only)

### Database Setup
The system uses PostgreSQL with Alembic migrations. Run `alembic upgrade head` to create all required tables.

## API Documentation
Once running, visit:
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Testing
Run the test suite:
```bash
pytest tests/ -v
```

## Support
For issues and support, refer to the documentation in the docs/ directory.
"""
        
        zipf.writestr("INSTALLATION.md", install_instructions)
        print("  ✓ Added: INSTALLATION.md")
    
    # Calculate ZIP hash
    zip_hash = calculate_sha256(zip_path)
    
    # Create hash file
    hash_filename = f"{zip_filename}.sha256"
    hash_path = artifacts_dir / hash_filename
    
    with open(hash_path, 'w') as f:
        f.write(f"{zip_hash}  {zip_filename}\n")
    
    # Create deployment summary
    summary = {
        "deliverable": {
            "filename": zip_filename,
            "size_bytes": zip_path.stat().st_size,
            "sha256": zip_hash,
            "created": datetime.now().isoformat()
        },
        "version": version,
        "timestamp": timestamp,
        "status": "ready_for_deployment"
    }
    
    summary_path = artifacts_dir / f"deployment_summary_{timestamp}.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n✅ Deliverable package created successfully!")
    print(f"📦 Package: {zip_path}")
    print(f"📏 Size: {zip_path.stat().st_size:,} bytes")
    print(f"🔐 SHA256: {zip_hash}")
    print(f"📋 Summary: {summary_path}")
    
    return zip_path, zip_hash

if __name__ == "__main__":
    create_deliverable_zip()
