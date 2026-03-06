# System Architecture Snapshot

**Generated:** 2026-03-06  
**Version:** Current main branch  
**Purpose:** Complete architectural overview of the retirement planning system

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [High-Level Architecture](#high-level-architecture)
3. [Frontend Architecture](#frontend-architecture)
4. [Backend Architecture](#backend-architecture)
5. [Data Layer](#data-layer)
6. [Core Services](#core-services)
7. [API Layer](#api-layer)
8. [Security & Validation](#security--validation)
9. [Testing Strategy](#testing-strategy)
10. [Deployment & Operations](#deployment--operations)
11. [Recent Architectural Improvements](#recent-architectural-improvements)
12. [Technical Debt & Known Issues](#technical-debt--known-issues)
13. [Development Guidelines](#development-guidelines)

---

## Executive Summary

The retirement planning system is a full-stack web application that helps users plan for retirement by analyzing pension funds, capital assets, and additional income sources. The system provides financial calculations, tax planning, and rights fixation capabilities with a focus on Israeli pension regulations.

**Key Characteristics:**
- **Frontend:** React/TypeScript single-page application
- **Backend:** FastAPI with SQLAlchemy ORM
- **Database:** PostgreSQL with SQLite fallback for development
- **Architecture:** Layered service-oriented architecture with clear separation of concerns
- **Testing:** Comprehensive test suite including E2E, integration, and unit tests
- **AI Integration:** Conversational AI agent for user guidance

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React)                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐ │
│  │ Client Mgmt │ │ Pension     │ │ Reports     │ │ Settings│ │
│  │             │ │ Portfolio   │ │             │ │         │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                    HTTP/REST API
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐ │
│  │ API Routers │ │ Core        │ │ Calculation │ │ AI Agent│ │
│  │             │ │ Services    │ │ Engine      │ │         │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                        SQLAlchemy ORM
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Database Layer                             │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐ │
│  │ PostgreSQL  │ │ Models      │ │ Migrations  │ │ Seeds   │ │
│  │ (Primary)   │ │             │ │             │ │         │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Frontend Architecture

### Technology Stack
- **Framework:** React 18 with TypeScript
- **Build Tool:** Vite
- **State Management:** Local component state + React hooks
- **Routing:** React Router
- **UI Components:** Custom components with Tailwind CSS
- **API Client:** Custom fetch wrapper with error handling

### Key Frontend Modules

#### 1. Client Management (`/pages/ClientDetails/`)
- Client information management
- Pension date calculation
- System state snapshots

#### 2. Pension Portfolio (`/pages/PensionPortfolio/`)
- XML file parsing and import
- Portfolio visualization
- Conversion calculations

#### 3. Current Employer (`/pages/SimpleCurrentEmployer/`)
- Employment termination planning
- Severance calculations
- Rights fixation

#### 4. Reports (`/pages/SimpleReports/`)
- Cash flow projections
- Tax calculations
- Financial summaries

#### 5. System Settings (`/pages/SystemSettings/`)
- System health monitoring
- Configuration management

### Frontend Architecture Patterns

```typescript
// Example: API Route SSOT Pattern
export const apiRoutes = {
  clients: {
    capitalAssets: (clientId: number) => `/api/v1/clients/${clientId}/capital-assets`,
    pensionFunds: (clientId: number) => `/api/v1/clients/${clientId}/pension-funds`,
    additionalIncomes: (clientId: number) => `/api/v1/clients/${clientId}/additional-incomes`,
  }
} as const;
```

---

## Backend Architecture

### Technology Stack
- **Framework:** FastAPI with Python 3.11
- **ORM:** SQLAlchemy 2.0 with async support
- **Database:** PostgreSQL (production) / SQLite (development)
- **Validation:** Pydantic v2
- **Migration:** Alembic
- **Testing:** pytest with extensive fixtures

### Core Backend Layers

#### 1. API Layer (`app/routers/`)
- RESTful API endpoints
- Request/response validation
- Error handling and status codes

#### 2. Service Layer (`app/services/`)
- Business logic implementation
- Calculation engines
- External service integrations

#### 3. Core Layer (`app/core/`)
- Database configuration
- System utilities
- Validation frameworks

#### 4. Models Layer (`app/models/`)
- SQLAlchemy model definitions
- Database schema
- Relationships and constraints

### Key Backend Services

#### Calculation Engine (`app/services/calculation/`)
```python
# Example: Engine Factory Pattern
class EngineFactory:
    @staticmethod
    def create_calculation_engine(
        calculation_type: CalculationType,
        **kwargs
    ) -> CalculationEngine:
        if calculation_type == CalculationType.CASHFLOW:
            return CashflowCalculationEngine(**kwargs)
        elif calculation_type == CalculationType.TAX:
            return TaxCalculationEngine(**kwargs)
        # ... other engines
```

#### AI Agent Service (`app/services/agent_execution/`)
- Conversational AI integration
- Intent classification
- Tool execution framework
- Policy enforcement

#### Annuity Coefficient Service (`app/services/annuity_coefficient/`)
- Pension fund coefficient calculations
- Insurance generation coefficients
- Company-specific coefficients

---

## Data Layer

### Database Schema Overview

#### Core Entities
1. **Client** - Central user entity
2. **PensionFund** - Pension fund accounts
3. **CapitalAsset** - Capital assets and investments
4. **AdditionalIncome** - Additional income sources
5. **EmployerGrant** - Employer grants and rights
6. **TaxBracket** - Tax calculation tables
7. **AnnuityCoefficient** - Coefficient tables

#### Key Relationships
```python
# Example: Client Relationships
class Client(Base):
    __tablename__ = "clients"
    
    pension_funds = relationship("PensionFund", back_populates="client")
    capital_assets = relationship("CapitalAsset", back_populates="client")
    additional_incomes = relationship("AdditionalIncome", back_populates="client")
    employer_grants = relationship("EmployerGrant", back_populates="client")
```

### Data Validation Patterns
```python
# Example: Pydantic Schema with Extra Fields Handling
class PensionFundCreate(BaseModel):
    fund_name: str
    balance: float
    monthly_pension: Optional[float] = None
    
    model_config = ConfigDict(extra='ignore')  # Ignore extra fields
```

---

## Core Services

### 1. Calculation Engine

#### Cashflow Calculations
- Multi-year cash flow projections
- Tax calculations with brackets
- Inflation adjustments
- Pension fund projections

#### Tax Calculations
- Progressive tax bracket calculations
- Special tax treatments (fixed_rate, tax_spread)
- Capital gains calculations
- Pension tax exemptions

### 2. AI Agent System

#### Architecture
```
User Input → Intent Classifier → Capability Router → Tool Executor → Response
```

#### Key Components
- **Intent Classification**: Determines user intent
- **Capability Routing**: Routes to appropriate tools
- **Tool Execution**: Executes financial calculations
- **Policy Enforcement**: Ensures compliance with rules

#### Agent Training System
- Golden test cases for validation
- Real path execution testing
- Determinism verification
- Capability mapping

### 3. Annuity Coefficient System

#### Data Sources
- Company annuity coefficients (CSV)
- Insurance generation coefficients
- Pension fund coefficients
- Tax bracket tables

#### Calculation Logic
```python
def get_annuity_coefficient(
    product_type: str,
    age: int,
    gender: str,
    option: str
) -> AnnuityCoefficientResult:
    # Lookup appropriate coefficient table
    # Apply age/gender adjustments
    # Return calculated coefficient
```

---

## API Layer

### API Design Principles
- **RESTful design** with resource-oriented URLs
- **Consistent error handling** with proper HTTP status codes
- **Trailing slash support** for backward compatibility
- **OpenAPI documentation** for all endpoints
- **Request validation** using Pydantic schemas

### Key API Endpoints

#### Client Management
```
GET    /api/v1/clients/{client_id}
POST   /api/v1/clients
PUT    /api/v1/clients/{client_id}
```

#### Pension Portfolio
```
GET    /api/v1/clients/{client_id}/pension-funds
POST   /api/v1/clients/{client_id}/pension-funds
DELETE /api/v1/clients/{client_id}/pension-funds/{fund_id}
POST   /api/v1/pension-funds/{fund_id}/compute
```

#### Capital Assets
```
GET    /api/v1/clients/{client_id}/capital-assets
POST   /api/v1/clients/{client_id}/capital-assets
DELETE /api/v1/clients/{client_id}/capital-assets/{asset_id}
```

#### AI Chat
```
POST   /api/v1/llm/pension-chat
POST   /api/v1/llm/pension-chat-stream
```

### API Stability Features
- **Trailing slash aliases** for backward compatibility
- **Extra field handling** to prevent 422 errors
- **Versioned APIs** for future compatibility
- **Comprehensive error responses**

---

## Security & Validation

### Input Validation
- **Pydantic schemas** for all API inputs
- **SQLAlchemy validation** at database level
- **Custom validators** for business rules
- **Type safety** with TypeScript and Python type hints

### Security Measures
- **SQL injection prevention** through ORM
- **XSS protection** in frontend
- **CSRF protection** in API
- **Input sanitization** for user content
- **Rate limiting** considerations

### Data Privacy
- **Minimal data collection**
- **Secure password handling**
- **Data encryption** at rest (consideration)
- **Audit logging** for sensitive operations

---

## Testing Strategy

### Test Categories

#### 1. Unit Tests
- Model validation tests
- Service layer tests
- Utility function tests
- AI agent component tests

#### 2. Integration Tests
- API endpoint tests
- Database integration tests
- Service integration tests

#### 3. E2E Tests
- Full user journey tests
- Smoke tests for critical paths
- Cross-browser compatibility tests

#### 4. Agent Training Tests
- Golden test case validation
- Real path execution tests
- Determinism verification
- Capability mapping tests

### Test Infrastructure
```python
# Example: Test Configuration
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
```

### Test Data Management
- **Fixture-based test data**
- **Factory patterns** for test objects
- **Database isolation** between tests
- **Cleanup procedures** for test data

---

## Deployment & Operations

### Development Environment
- **Local development** with SQLite
- **Hot reload** for frontend and backend
- **Debug tools** and logging
- **Pre-commit hooks** for code quality

### Production Considerations
- **PostgreSQL database**
- **Reverse proxy** (nginx)
- **SSL/TLS termination**
- **Monitoring and logging**
- **Backup strategies**

### Containerization
```dockerfile
# Example: Multi-stage Docker build
FROM python:3.11-slim as backend
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### CI/CD Pipeline
- **Automated testing** on PR
- **Code quality checks** (Black, isort, flake8)
- **Security scanning**
- **Automated deployment** on merge

---

## Recent Architectural Improvements

### 1. API Route SSOT (Single Source of Truth)
- **Problem**: Hardcoded API paths throughout frontend
- **Solution**: Centralized route builders with type safety
- **Impact**: Reduced API path errors, easier maintenance

### 2. Pydantic v2 Migration
- **Problem**: Deprecated Pydantic v1 validators
- **Solution**: Migration to Pydantic v2 field validators
- **Impact**: Future-proof validation, better performance

### 3. Trailing Slash Compatibility
- **Problem**: 405 errors for requests without trailing slashes
- **Solution**: Dual route decorators for all endpoints
- **Impact**: Better client compatibility

### 4. Extra Fields Handling
- **Problem**: 422 errors when frontend sends extra fields
- **Solution**: Configured schemas to ignore extra fields
- **Impact**: More resilient API, better UX

### 5. System Health Monitoring
- **Problem**: Silent data corruption in coefficient tables
- **Solution**: Automated validation and repair system
- **Impact**: Data integrity assurance, proactive issue detection

### 6. AI Agent Training Framework
- **Problem**: Inconsistent AI agent behavior
- **Solution**: Comprehensive testing and training framework
- **Impact**: Reliable AI agent performance, deterministic behavior

---

## Technical Debt & Known Issues

### High Priority
1. **Pydantic v1 Deprecations**: Remaining v1 validators need migration
2. **Test Coverage**: Some edge cases lack comprehensive tests
3. **Error Handling**: Some services need better error propagation
4. **Performance**: Large dataset queries need optimization

### Medium Priority
1. **Code Organization**: Some services could be better modularized
2. **Documentation**: API documentation needs more examples
3. **Type Safety**: Some legacy code lacks proper type hints
4. **Logging**: Structured logging implementation needed

### Low Priority
1. **UI/UX**: Some interfaces need modernization
2. **Internationalization**: Hebrew/English support improvements
3. **Accessibility**: ARIA labels and keyboard navigation
4. **Mobile Responsiveness**: Some pages need mobile optimization

---

## Development Guidelines

### Code Quality Standards
- **Python**: Follow PEP 8, use Black formatter, isort for imports
- **TypeScript**: Strict mode, ESLint + Prettier
- **Testing**: Minimum 80% coverage for critical paths
- **Documentation**: Docstrings for all public functions

### Git Workflow
- **Feature branches** for all development
- **Pull requests** for code review
- **Semantic commits** with conventional format
- **Protected branches** for main/master

### API Development
- **OpenAPI first** approach for new endpoints
- **Version control** for breaking changes
- **Backward compatibility** maintenance
- **Comprehensive testing** for all endpoints

### Database Changes
- **Alembic migrations** for all schema changes
- **Rollback scripts** for safety
- **Data validation** after migrations
- **Performance testing** for large datasets

### Security Practices
- **Input validation** at all layers
- **SQL injection prevention** through ORM
- **Authentication** for sensitive operations
- **Audit logging** for important actions

---

## Architecture Decision Records (ADRs)

### ADR-001: FastAPI Framework Selection
**Date**: 2023-01-01  
**Status**: Accepted  
**Decision**: Use FastAPI as the backend framework  
**Rationale**: Automatic OpenAPI generation, type hints, async support, performance

### ADR-002: PostgreSQL as Primary Database
**Date**: 2023-01-15  
**Status**: Accepted  
**Decision**: Use PostgreSQL for production, SQLite for development  
**Rationale**: PostgreSQL features, SQLite simplicity for development

### ADR-003: React TypeScript Frontend
**Date**: 2023-02-01  
**Status**: Accepted  
**Decision**: Use React with TypeScript for frontend  
**Rationale**: Type safety, ecosystem support, developer experience

### ADR-004: AI Agent Integration
**Date**: 2023-06-01  
**Status**: Accepted  
**Decision**: Integrate conversational AI agent for user guidance  
**Rationale**: Improved user experience, automated financial guidance

---

## Future Architectural Considerations

### Scalability
- **Database sharding** for large datasets
- **Caching layer** for frequently accessed data
- **Load balancing** for high availability
- **Microservices** decomposition consideration

### Performance
- **Query optimization** for complex calculations
- **Background jobs** for long-running processes
- **Caching strategies** for coefficient tables
- **Async processing** where appropriate

### Security
- **Multi-tenant architecture** consideration
- **Role-based access control** implementation
- **Audit trail** enhancement
- **Data encryption** implementation

### Monitoring & Observability
- **Structured logging** implementation
- **Metrics collection** for performance
- **Health checks** for all services
- **Error tracking** and alerting

---

## Conclusion

This architecture snapshot represents the current state of the retirement planning system. The system follows modern software development practices with clear separation of concerns, comprehensive testing, and a focus on maintainability and scalability.

Key strengths include:
- **Type safety** throughout the stack
- **Comprehensive testing** strategy
- **API-first design** approach
- **AI integration** for user experience
- **Robust calculation engines** for financial accuracy

The architecture is designed to evolve with changing requirements while maintaining stability and performance for users planning their retirement.

---

*This document is automatically generated and should be updated as the architecture evolves.*
