# AutoArticle E2E Verification Checklist

## Scope
- Wizard flow: Step 1 -> Step 2 -> Step 3 -> Detail -> Edit
- Export outputs: PDF, Word, PPT, CardNews PNG
- Image count cases: 1, 2, 3, 4
- Export layout versions: v1, v2 (rollback capable)

## Preconditions
- Apply migrations:
  - `python manage.py migrate`
- Login with a test account.
- Confirm `autoarticle` is reachable without onboarding redirect in test mode.

## A. Wizard and Save Flow
1. Open `autoarticle` create page.
2. Enter:
   - 학년: `3학년`
   - 반: `풀꽃반`
   - 행사명/장소/일시/키워드
3. Upload 1 image and run generation.
4. Save article on step 3.
5. Verify detail page shows 대상 as `3학년 풀꽃반`.

## B. Edit Flow (Image Replace)
1. Open Edit from detail.
2. Check one existing image to remove.
3. Upload one new image.
4. Save.
5. Verify detail image gallery changed as expected.

## C. Export Design Version Toggle
1. In detail or archive, set export design to `v2` and apply.
2. Download all outputs once.
3. Switch back to `v1` and download again.
4. Confirm rollback is immediate (no deploy, no migration).

## D. 1~4 Image Export Matrix
Run each row with one article and verify images are included.

| Case | Input Images | PDF | Word | PPT | Card PNG |
|---|---:|---|---|---|---|
| Case-1 | 1 | 1 image visible | 1 image visible | 1 image visible | 1 image visible |
| Case-2 | 2 | 2 images visible | 2 images visible | 2 images visible | 2 images visible |
| Case-3 | 3 | 3 images visible | 3 images visible | 3 images visible | 3 images visible |
| Case-4 | 4 | 4 images visible | 4 images visible | 4 images visible | 4 images visible |

## E. Regression Points
- Loading step does not mention fixed timing (e.g., no "평균 10초").
- Archive list displays 대상 with 학년+반.
- Detail metadata displays 대상 with 학년+반.
- No crash when image URLs are Cloudinary URLs.

## F. Known Environment Caveats
- Existing tests may fail if onboarding middleware redirects to `/update-email/` in non-test mode.
- In test mode, onboarding exemptions should allow `/autoarticle/` paths.
