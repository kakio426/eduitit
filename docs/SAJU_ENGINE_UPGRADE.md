# Saju Service Upgrade: Deterministic Engine Integration

## ✅ Completed Features
The Saju (Fortune) service has been upgraded to use a deterministic Logic Engine as the Single Source of Truth (SSOT). This ensures that chart calculations are mathematically precise and consistent, eliminating hallucinated or varying results from the LLM.

### 1. Database & Reference Data
- **Models**: Created `Stem` (Ten Heavenly Stems), `Branch` (Twelve Earthly Branches), `SixtyJiazi` (60 Pillars), and `NatalChart` models.
- **Seeding**: Populated the database with standard Saju reference data.

### 2. Manse-ryok (Astronomical Engine)
- **High Precision**: Implemented `fortune.libs.manse` using `ephem` and `korean-lunar-calendar`.
- **Solar Terms**: Calculates exact entry times for 24 Solar Terms (Jeolgi) to determine accurate Month Pillars.
- **True Solar Time**: Applies longitude correction (standard 135 vs local 127.0 for Korea) to calculate precise Hour Pillars.

### 3. Logic Engine
- **Calculator**: `fortune.libs.calculator` logic implemented to derive:
    - **Year Pillar**: Based on Lichun (Start of Spring).
    - **Month Pillar**: Based on 12 Major Solar Terms.
    - **Day Pillar**: Based on absolute day count from reference epoch.
    - **Hour Pillar**: Uses "Five Rats Chasing Hour" method with True Solar Time.
    - **Ten Gods**: Calculates relationships (Eating God, Seven Killings, etc.) deterministically.

### 4. LLM Integration
- **SSOT Prompting**: The View now calculates the chart *before* calling the LLM.
- **Strict Adherence**: The System Prompt forces the LLM to use the calculated chart, preventing it from generating its own (often wrong) charts.
- **Architecture**: `View -> Logic Engine -> Context -> System Prompt -> LLM`.

## 🧪 Verification
All unit and integration tests passed, verifying:
- Model integrity
- Astronomical calculation accuracy (Lichun dates, Time correction)
- Logic calculation correctness (Five Tigers, Five Rats, Ten Gods)
- View-Logic integration

The service is now ready to provide reliable, professional-grade Saju analysis.
