# AutoArticle Export Design Versioning (Rollback Guide)

## What was added
- Export layout version switch:
  - `v1` (legacy)
  - `v2` (clean)
  - `v3` (magazine)
- Applies to:
  - CardNews PNG
  - PPT
  - PDF
  - Word

## Immediate rollback options
1. UI rollback (no deploy)
- In article detail or archive, choose `v1 클래식` and click `적용`.
- Next downloads use legacy design immediately.

2. Environment rollback (global)
- Set `AUTOARTICLE_EXPORT_LAYOUT=v1`
- Restart app/deploy

## New design intent
- `v2`: Cleaner spacing and lower visual noise
- `v3`: Magazine-like hierarchy with stronger title/header contrast
- Better metadata readability (date/location/대상)
- Consistent 1~4 image handling across all exports

## Safe rollout
1. Keep default as `v1`
2. Switch per session/user to `v2` and verify
3. If stable, set env default to `v2` or `v3`
