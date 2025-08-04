#!/bin/bash

# clean.sh - Script untuk membersihkan file kosong, cache, dan folder kosong

set -e  # Exit on error

echo "🧹 Starting cleanup process..."

# Function to print colored output
print_info() {
    echo -e "\033[34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[32m[SUCCESS]\033[0m $1"
}

print_warning() {
    echo -e "\033[33m[WARNING]\033[0m $1"
}

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR"

echo "Working directory: $SCRIPT_DIR"
echo ""

# 1. Remove Python cache files
print_info "Removing Python cache files..."
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type f -name "*.pyd" -delete 2>/dev/null || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
print_success "Python cache files removed"

# 2. Remove common cache directories
print_info "Removing common cache directories..."
rm -rf .pytest_cache 2>/dev/null || true
rm -rf .mypy_cache 2>/dev/null || true
rm -rf .coverage 2>/dev/null || true
rm -rf htmlcov 2>/dev/null || true
rm -rf .tox 2>/dev/null || true
rm -rf .nox 2>/dev/null || true
rm -rf build 2>/dev/null || true
rm -rf dist 2>/dev/null || true
print_success "Cache directories removed"

# 3. Remove Jupyter Notebook checkpoints
print_info "Removing Jupyter Notebook checkpoints..."
find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} + 2>/dev/null || true
print_success "Jupyter checkpoints removed"

# 4. Remove macOS system files
print_info "Removing macOS system files..."
find . -name ".DS_Store" -delete 2>/dev/null || true
find . -name "._*" -delete 2>/dev/null || true
print_success "macOS system files removed"

# 5. Remove temporary files
print_info "Removing temporary files..."
find . -name "*.tmp" -delete 2>/dev/null || true
find . -name "*.temp" -delete 2>/dev/null || true
find . -name "*~" -delete 2>/dev/null || true
find . -name "*.swp" -delete 2>/dev/null || true
find . -name "*.swo" -delete 2>/dev/null || true
print_success "Temporary files removed"

# 6. Remove empty files
print_info "Removing empty files..."
empty_files_count=$(find . -type f -empty | wc -l | tr -d ' ')
if [ "$empty_files_count" -gt 0 ]; then
    find . -type f -empty -delete
    print_success "Removed $empty_files_count empty files"
else
    print_info "No empty files found"
fi

# 7. Remove empty directories (run multiple times to handle nested empty dirs)
print_info "Removing empty directories..."
removed_dirs=0
for i in {1..5}; do
    empty_dirs=$(find . -type d -empty 2>/dev/null | grep -v "^\.$" | wc -l | tr -d ' ')
    if [ "$empty_dirs" -gt 0 ]; then
        find . -type d -empty -delete 2>/dev/null || true
        removed_dirs=$((removed_dirs + empty_dirs))
    else
        break
    fi
done

if [ "$removed_dirs" -gt 0 ]; then
    print_success "Removed $removed_dirs empty directories"
else
    print_info "No empty directories found"
fi

# 8. Remove log files (optional - uncomment if needed)
# print_info "Removing log files..."
# find . -name "*.log" -delete 2>/dev/null || true
# print_success "Log files removed"

echo ""
print_success "✨ Cleanup completed successfully!"
echo ""

# Show summary
echo "📊 Summary:"
echo "   - Python cache files cleaned"
echo "   - Common cache directories removed"
echo "   - Jupyter checkpoints cleaned"
echo "   - macOS system files removed"
echo "   - Temporary files cleaned"
echo "   - Empty files removed: $empty_files_count"
echo "   - Empty directories removed: $removed_dirs"
echo ""
echo "🎉 Your project is now clean!"
