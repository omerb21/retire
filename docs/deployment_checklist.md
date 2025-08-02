# Fixation Adapter Deployment Checklist

## Pre-Deployment

### 1. Environment Preparation

- [ ] Create/verify `templates/fixation/` directory exists
- [ ] Place PDF templates in `templates/fixation/`:
  - [ ] `161d.pdf`
  - [ ] `grants_appendix.pdf`
  - [ ] `commutations_appendix.pdf`
- [ ] Create/verify `packages/` directory exists
- [ ] Set appropriate permissions:
  - Windows: Grant Write permission to Service User
  - Linux: `chmod -R 775 packages`
- [ ] Set environment variables:
  - Staging: `FIXATION_ALLOW_JSON_FALLBACK=true`
  - Production: Initially `true`, later `false` after PDF validation

### 2. Database Preparation

- [ ] For new DB: Run `alembic upgrade head`
- [ ] For existing DB: Verify schema compatibility and run `alembic stamp head`
- [ ] If schema mismatch: Backup DB, reconcile schema, then stamp

### 3. Code Review

- [ ] Verify all tests pass: `python -m unittest discover`
- [ ] Check logging configuration (INFO for Prod, DEBUG for Staging)
- [ ] Ensure no debug prints remain in code
- [ ] Verify all endpoints return proper response models
- [ ] Confirm path validation in file download endpoint

## Deployment

### 4. Deployment Steps

- [ ] Tag release version: `git tag v1.0.0`
- [ ] Deploy to Staging environment
- [ ] Run smoke tests: `.\smoke_test.ps1 [staging-url]`
- [ ] Verify logs show structured metrics
- [ ] Confirm all document types generate successfully
- [ ] Test file download endpoint
- [ ] Deploy to Production environment
- [ ] Run smoke tests: `.\smoke_test.ps1 [production-url]`

## Post-Deployment

### 5. Monitoring Setup

- [ ] Configure alerting rules:
  - [ ] Error rate > 1% for 5 rolling minutes
  - [ ] Any fallback=true events in Production after PDF implementation
  - [ ] No successful writes to packages/ for >30 minutes after API calls
- [ ] Set up SLO monitoring:
  - [ ] Error rate ≤ 1%
  - [ ] Fallback rate = 0% (after PDF implementation)
  - [ ] p95 response time ≤ 500ms

### 6. PDF Implementation

- [ ] In Staging: Place PDF templates in correct location
- [ ] Verify PDF generation works correctly
- [ ] In Production: Place PDF templates in correct location
- [ ] Set `FIXATION_ALLOW_JSON_FALLBACK=false` in Production
- [ ] Monitor for any fallback events (should be 0)

### 7. Maintenance

- [ ] Schedule daily cleanup script: `python cleanup_old_files.py`
- [ ] Set up daily backup of `packages/` directory if required
- [ ] Create dashboard for document metrics:
  - [ ] Document count by client
  - [ ] Response times
  - [ ] Fallback count

## Rollback Plan

If issues occur:

1. Set `FIXATION_ALLOW_JSON_FALLBACK=true` if PDF issues
2. If necessary, revert to previous tag: `git checkout <previous_tag>`
3. Restart service
4. If schema unchanged, run `alembic stamp head`
5. Run smoke tests to verify functionality

## Acceptance Criteria

- [ ] All smoke tests pass
- [ ] Document generation endpoints return 200 with success=true
- [ ] Files are correctly generated in packages/ directory
- [ ] File download endpoint works correctly
- [ ] Structured logging captures all required metrics
- [ ] Error rate remains below 1%
- [ ] No fallbacks occur after PDF implementation
