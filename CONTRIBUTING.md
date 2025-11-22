<!-- SPDX-License-Identifier: MIT
Copyright (c) 2025 Perday Labs -->

# Contributing to Bulk Upsert Helpers

Thank you for your interest in contributing to bulk-upsert-helpers! This project is actively maintained and welcomes contributions from the community.

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/wmoore012/bulk_upsert_helpers.git
cd bulk_upsert_helpers

# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install --with dev,mysql

# Run tests
poetry run pytest

# Run quality checks
poetry run black .
poetry run isort .
poetry run ruff check .
poetry run mypy .
```

## 🧪 Development Workflow

### 1. Set Up Development Environment

```bash
# Create virtual environment
poetry shell

# Install pre-commit hooks
poetry run pre-commit install

# Verify setup
poetry run pytest --version
```

### 2. Making Changes

1. **Create a feature branch**: `git checkout -b feature/your-feature-name`
2. **Write tests first**: Follow TDD principles
3. **Implement your changes**: Keep changes focused and atomic
4. **Run the full test suite**: `poetry run pytest`
5. **Check code quality**: `poetry run pre-commit run --all-files`

### 3. Testing Guidelines

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src --cov-report=html

# Run performance benchmarks
poetry run python -m bulk_upsert_helpers.benchmarks

# Run specific test categories
poetry run pytest -m "not slow"  # Skip slow tests
poetry run pytest -m mysql       # MySQL-specific tests only
```

### 4. Code Quality Standards

- **Type hints**: All functions must have complete type annotations
- **Documentation**: All public functions need docstrings with examples
- **Testing**: Minimum 90% code coverage required
- **Performance**: No regressions in benchmark tests
- **Security**: All database operations must be injection-safe

## 📋 Contribution Types

### 🐛 Bug Reports

When reporting bugs, please include:

- **Environment details**: Python version, database version, OS
- **Minimal reproduction case**: Smallest code that reproduces the issue
- **Expected vs actual behavior**: Clear description of the problem
- **Performance impact**: If applicable, benchmark results

### ✨ Feature Requests

For new features, please provide:

- **Use case description**: Real-world scenario where this helps
- **API design proposal**: How the feature should work
- **Performance considerations**: Expected impact on throughput/memory
- **Backward compatibility**: How it affects existing code

### 🔧 Code Contributions

#### Performance Improvements
- Include before/after benchmark results
- Ensure no regression in existing functionality
- Document optimization techniques used

#### New Database Support
- Follow existing patterns for MySQL implementation
- Add comprehensive test coverage
- Update documentation with supported databases

#### Security Enhancements
- Include security test cases
- Document threat model and mitigations
- Follow OWASP guidelines for database security

## 🏗️ Architecture Guidelines

### Code Organization
```
src/bulk_upsert_helpers/
├── __init__.py          # Public API exports
├── upsert.py           # Core upsert functionality
├── benchmarks.py       # Performance measurement
└── utils.py            # Helper utilities (if needed)
```

### Design Principles
1. **Single Responsibility**: Each function does one thing well
2. **Fail Fast**: Invalid input raises clear exceptions immediately
3. **Performance First**: Optimize for high-throughput scenarios
4. **Security by Default**: All operations are injection-safe
5. **Backward Compatibility**: Maintain API stability

### Database Abstraction
- Use SQLAlchemy's database-agnostic features where possible
- Implement database-specific optimizations when beneficial
- Maintain consistent behavior across supported databases

## 🧪 Testing Strategy

### Test Categories
- **Unit Tests (70%)**: Fast, isolated function testing
- **Integration Tests (20%)**: Real database operations
- **Performance Tests (10%)**: Benchmark validation

### Test Requirements
- All new code must have corresponding tests
- Performance-critical paths need benchmark tests
- Security features require negative test cases
- Edge cases and error conditions must be covered

### MySQL Testing
```bash
# Start MySQL container for testing
docker run --name mysql-test -e MYSQL_ROOT_PASSWORD=testpass -e MYSQL_DATABASE=testdb -p 3306:3306 -d mysql:8.0

# Run MySQL-specific tests
TEST_DATABASE_URL=mysql+pymysql://root:testpass@localhost:3306/testdb poetry run pytest -m mysql
```

## 📊 Performance Standards

### Benchmarking Requirements
- All performance claims must be backed by benchmarks
- Regression tests prevent performance degradation
- Memory usage must be tracked for large operations
- Throughput measurements required for bulk operations

### Quality Gates
```python
PERFORMANCE_THRESHOLDS = {
    "bulk_upsert_min_throughput": 5000,     # rows/sec
    "get_or_create_min_throughput": 1000,   # ops/sec
    "p95_latency_max_ms": 5000,             # milliseconds
    "memory_max_mb": 500,                   # megabytes
}
```

## 🔒 Security Guidelines

### SQL Injection Prevention
- Always use parameterized queries
- Never concatenate user input into SQL strings
- Validate input types and ranges
- Use SQLAlchemy's built-in protections

### Input Validation
```python
# Good: Type-safe with validation
def bulk_upsert(engine: Engine, table: Table, rows: List[Dict[str, Any]]) -> int:
    if not isinstance(rows, list):
        raise ValueError("rows must be a list")
    # ... rest of implementation

# Bad: No validation
def bulk_upsert(engine, table, rows):
    # Direct use without validation
```

## 📝 Documentation Standards

### Docstring Format
```python
def bulk_upsert(engine: Engine, table: Table, rows: List[Dict[str, Any]]) -> int:
    """
    Insert rows into table, updating existing rows on conflicts.

    Args:
        engine: SQLAlchemy Engine instance
        table: SQLAlchemy Table object to insert into
        rows: List of dictionaries representing rows to insert/update

    Returns:
        Number of affected rows

    Raises:
        ValueError: If rows list is empty or invalid
        ImportError: If MySQL dialect is not available

    Example:
        >>> engine = create_engine("mysql+pymysql://user:pass@host/db")
        >>> affected = bulk_upsert(engine, users_table, user_data)
        >>> print(f"Processed {affected} records")

    Notes:
        - Uses MySQL's ON DUPLICATE KEY UPDATE for optimal performance
        - Primary key columns are automatically excluded from updates
        - All operations are SQL injection safe
    """
```

### README Updates
- Keep examples current and tested
- Update performance benchmarks with new results
- Document any breaking changes clearly
- Include migration guides for major versions

## 🚀 Release Process

### Version Numbering
- Follow [Semantic Versioning](https://semver.org/)
- `MAJOR.MINOR.PATCH` format
- Breaking changes increment MAJOR
- New features increment MINOR
- Bug fixes increment PATCH

### Release Checklist
- [ ] All tests pass
- [ ] Performance benchmarks meet thresholds
- [ ] Documentation is updated
- [ ] CHANGELOG.md is updated
- [ ] Version number is bumped
- [ ] Git tag is created
- [ ] PyPI release is published

## 🤝 Community Guidelines

### Code of Conduct
- Be respectful and inclusive
- Focus on constructive feedback
- Help newcomers learn and contribute
- Maintain professional communication

### Getting Help
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community support
- **Documentation**: Check README and docstrings first
- **Examples**: Look at test cases for usage patterns

## 🏆 Recognition

Contributors who make significant improvements will be:
- Listed in the project's contributors section
- Mentioned in release notes
- Invited to become project maintainers (for ongoing contributors)

Thank you for helping make bulk-upsert-helpers better for everyone! 🎉
