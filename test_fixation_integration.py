#!/usr/bin/env python3
"""
Test script for rights fixation integration
"""
import sys
from pathlib import Path

# Add the rights fixation system to Python path
rights_fixation_path = Path(__file__).parent / "מערכת קיבוע זכויות"
if str(rights_fixation_path) not in sys.path:
    sys.path.insert(0, str(rights_fixation_path))

def test_imports():
    """Test that all required modules can be imported"""
    try:
        from app.utils import get_client_package_dir
        from app.pdf_filler import fill_161d_form, generate_grants_appendix, generate_commutations_appendix
        print("✅ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_template_exists():
    """Test that 161d template exists"""
    template_path = rights_fixation_path / "app" / "static" / "templates" / "161d.pdf"
    if template_path.exists():
        print(f"✅ 161d template found at: {template_path}")
        return True
    else:
        print(f"❌ 161d template not found at: {template_path}")
        return False

def test_packages_directory():
    """Test that packages directory exists and is writable"""
    packages_dir = rights_fixation_path / "packages"
    try:
        packages_dir.mkdir(exist_ok=True)
        # Test write permission
        test_file = packages_dir / "test_write_permission.tmp"
        test_file.touch()
        test_file.unlink()
        print(f"✅ Packages directory is writable: {packages_dir}")
        return True
    except (OSError, PermissionError) as e:
        print(f"❌ Packages directory write error: {e}")
        return False

def test_get_client_package_dir():
    """Test get_client_package_dir function"""
    try:
        from app.utils import get_client_package_dir
        # Test with sample data
        test_dir = get_client_package_dir(1, "ישראל", "ישראלי")
        print(f"✅ get_client_package_dir works: {test_dir}")
        return True
    except Exception as e:
        print(f"❌ get_client_package_dir error: {e}")
        return False

if __name__ == "__main__":
    print("Testing rights fixation integration...")
    print(f"Rights fixation path: {rights_fixation_path}")
    
    tests = [
        test_imports,
        test_template_exists,
        test_packages_directory,
        test_get_client_package_dir
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All integration tests passed!")
    else:
        print("⚠️ Some tests failed - check configuration")
