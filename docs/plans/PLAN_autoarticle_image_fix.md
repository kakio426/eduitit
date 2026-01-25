# Plan: AutoArticle Image Upload Fix

## 1. Overview and Objectives

**Objective**: Fix the broken image upload functionality in the AutoArticle app on the production environment (Railway).
**Current State**: Images uploaded in production return 404 errors because they are stored locally (`/media/...`) instead of Cloudinary. `USE_CLOUDINARY` is evaluating to `False` due to missing environment variables.
**Target State**: Images should be uploaded to Cloudinary in production, and `USE_CLOUDINARY` should evaluate to `True`.

## 2. Architecture Decisions

- **Infrastructure**: Use Cloudinary for media storage in production (consistent with existing code capabilities).
- **Configuration**: Use Environment Variables (Railway Variables) to inject credentials.
- **Verification**: Manual upload test in production environment.

## 3. Phase Breakdown

### Phase 1: Configuration & Verification
**Goal**: Enable Cloudinary in production environment.
**Test Strategy**: Manual Verification (Production)

- [ ] **Task 1 (Config)**: Add `CLOUDINARY_CLOUD_NAME` to Railway variables.
- [ ] **Task 2 (Config)**: Add `CLOUDINARY_API_KEY` to Railway variables.
- [ ] **Task 3 (Config)**: Add `CLOUDINARY_API_SECRET` to Railway variables.
- [ ] **Task 4 (Config)**: Add `CLOUDINARY_URL` to Railway variables.
- [ ] **Task 5 (Verification)**: Redeploy and verify `settings.USE_CLOUDINARY` is True (via logs or Django shell if needed).
- [ ] **Task 6 (Verification)**: Upload a new image in AutoArticle and verify it renders correctly (Cloudinary URL).

## 4. Quality Gate Checklists

**Configuration**:
- [ ] All 4 Cloudinary variables are set in Railway.
- [ ] Deploy logs show "USE_CLOUDINARY = True".

**Functionality**:
- [ ] Image upload process completes without error.
- [ ] Image displays in preview step.
- [ ] Image URL in DOM matches `res.cloudinary.com`.

## 5. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Credentials Invalid | Low | High | Verify keys from `.env` before adding. |
| Railway Env Not Updating | Low | Medium | Force redeploy after adding variables. |
| Codebase Logic Error | Low | Medium | Code already exists and works (presumably), this is a config switch. |

## 6. Rollback Strategy
- Remove environment variables from Railway to revert to local storage (though local storage is broken in prod, so "rollback" effectively maintains the status quo of broken images).

## 7. Notes
- Tailwind CSS warning in console is unrelated but should be addressed in a future task by properly building CSS for production.
