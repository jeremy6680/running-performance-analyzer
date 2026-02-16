# Recovery Score & Training Readiness - Quick Reference

## Recovery Score Formula (0-100)

### Component Breakdown

#### 1. Sleep Component (40 points max)
- **Formula:** `min(40, (total_sleep_hours / 8.0) * 40)`
- **Logic:** Linear scale up to 8 hours
  - 8+ hours = 40 points (100%)
  - 6 hours = 30 points (75%)
  - 4 hours = 20 points (50%)
  - 2 hours = 10 points (25%)

#### 2. Resting Heart Rate Component (20 points max)
- **Formula:** Comparison to 7-day average
- **Logic:**
  - At or below 7-day avg = 20 points (100%)
  - 1-5% above avg = 15 points (75%)
  - 6-10% above avg = 10 points (50%)
  - 10%+ above avg = 5 points (25%)

**Example:**
- 7-day avg RHR = 60 bpm
- Today's RHR = 57 bpm → 20 points (below average = good recovery)
- Today's RHR = 62 bpm → 15 points (3.3% above = slightly elevated)
- Today's RHR = 65 bpm → 10 points (8.3% above = moderate concern)
- Today's RHR = 68 bpm → 5 points (13.3% above = poor recovery)

#### 3. Stress Component (20 points max)
- **Formula:** Based on average daily stress level
- **Logic:**
  - Stress ≤25 = 20 points (100%) - Very low stress
  - Stress 26-40 = 15 points (75%) - Low stress
  - Stress 41-55 = 10 points (50%) - Moderate stress
  - Stress 56+ = 5 points (25%) - High stress

#### 4. Body Battery Component (20 points max)
- **Formula:** Based on net change (charged - drained)
- **Logic:**
  - Net change ≥20 = 20 points (100%) - Great recovery
  - Net change 10-19 = 15 points (75%) - Good recovery
  - Net change 0-9 = 10 points (50%) - Adequate recovery
  - Net change <0 = 5 points (25%) - Energy deficit

## Training Readiness Assessment

### Optimal
**Criteria (ALL must be met):**
- Total sleep ≥7 hours
- RHR ≤105% of 7-day average
- Average stress ≤40
- Body Battery net change ≥0

**Meaning:** Perfect conditions for hard training, intervals, or race efforts

### Good
**Criteria:**
- Total sleep ≥6 hours
- RHR ≤110% of 7-day average
- Average stress ≤55

**Meaning:** Suitable for moderate training, tempo runs, or steady efforts

### Moderate
**Criteria:**
- Total sleep ≥5 hours

**Meaning:** Light training recommended, easy runs, or active recovery

### Low
**Criteria:**
- Total sleep <5 hours OR
- Poor metrics across the board

**Meaning:** Rest day or very easy activity recommended

## Example Scenarios

### Scenario 1: Perfect Recovery
```
Sleep: 8.5 hours
Deep sleep: 2 hours
RHR: 55 bpm (7-day avg: 58 bpm)
Stress: 20
Body Battery: +25

Recovery Score Calculation:
- Sleep: min(40, (8.5/8)*40) = 40 points
- RHR: 20 points (below average)
- Stress: 20 points (very low)
- Body Battery: 20 points (net +25)
Total: 100 points

Training Readiness: OPTIMAL
Recommendation: Great day for intervals or tempo run
```

### Scenario 2: Adequate Recovery
```
Sleep: 7 hours
Deep sleep: 1.2 hours
RHR: 62 bpm (7-day avg: 60 bpm)
Stress: 35
Body Battery: +8

Recovery Score Calculation:
- Sleep: min(40, (7/8)*40) = 35 points
- RHR: 15 points (3.3% above avg)
- Stress: 15 points (low-moderate)
- Body Battery: 10 points (net +8)
Total: 75 points

Training Readiness: GOOD
Recommendation: Moderate training okay, avoid hard efforts
```

### Scenario 3: Poor Recovery
```
Sleep: 5.5 hours
Deep sleep: 0.8 hours
RHR: 68 bpm (7-day avg: 60 bpm)
Stress: 58
Body Battery: -5

Recovery Score Calculation:
- Sleep: min(40, (5.5/8)*40) = 27.5 points
- RHR: 5 points (13.3% above avg)
- Stress: 5 points (high)
- Body Battery: 5 points (net negative)
Total: 42.5 → 43 points

Training Readiness: LOW
Recommendation: Rest day or very easy recovery run
```

### Scenario 4: Mixed Signals
```
Sleep: 8 hours (good)
Deep sleep: 1.5 hours
RHR: 64 bpm (7-day avg: 60 bpm) ← elevated
Stress: 28
Body Battery: +15

Recovery Score Calculation:
- Sleep: 40 points
- RHR: 10 points (6.7% above avg)
- Stress: 15 points
- Body Battery: 15 points
Total: 80 points

Training Readiness: GOOD
Recommendation: Sleep was great but RHR is elevated. 
Consider easy run to monitor how body responds.
```

## Sleep Debt Impact

### Sleep Debt Calculation
- Target: 8 hours per night
- Daily debt = 8 - actual_hours
- 7-day cumulative debt tracked

### Impact on Recovery

**Low Sleep Debt (0-3 hours over 7 days)**
- Minimal impact
- Training can proceed normally
- Monitor trends

**Moderate Sleep Debt (4-7 hours over 7 days)**
- Noticeable impact on recovery
- Consider easier training week
- Prioritize sleep
- Recovery score likely 60-75

**High Sleep Debt (8+ hours over 7 days)**
- Significant recovery impairment
- Risk of illness or injury increases
- Reduce training intensity
- Focus on sleep catch-up
- Recovery score likely <60

## Stress Time Distribution

### Healthy Pattern
- Low stress: 60-70% of day
- Medium stress: 20-30% of day
- High stress: <10% of day

### Warning Signs
- High stress: >20% of day
- Medium stress: >40% of day
- Low stress: <40% of day

## RHR Trend Interpretation

### Positive Trends (Good)
- RHR decreasing over 28 days
- RHR consistently at or below 7-day average
- Low variability day-to-day

### Warning Signs (Bad)
- RHR increasing over 28 days
- RHR consistently above 7-day average by >5%
- High variability (swings of 10+ bpm)
- Elevated RHR persisting for 3+ days

**Possible Causes of Elevated RHR:**
- Insufficient recovery
- Onset of illness
- Overtraining
- Poor sleep
- High stress
- Dehydration
- Heat/environmental factors

## Using Recovery Score for Training Decisions

### Score 90-100: Optimal
- Hard intervals okay
- Race efforts okay
- Long tempo runs okay
- Push the limits

### Score 75-89: Good
- Moderate workouts okay
- Easy tempo okay
- Avoid maximal efforts
- Listen to body during workout

### Score 60-74: Moderate
- Easy runs only
- Light cross-training
- Active recovery
- Skip hard workouts

### Score <60: Low
- Rest day or
- Very easy 20-30 min jog
- Gentle stretching/yoga
- Focus on recovery

## Weekly Pattern Analysis

### Ideal Weekly Recovery Pattern
```
Monday: 70-80 (recovering from weekend)
Tuesday: 75-85 (improving)
Wednesday: 80-90 (good recovery)
Thursday: 80-90 (maintaining)
Friday: 85-95 (peaked)
Saturday: 75-85 (after hard workout)
Sunday: 70-80 (after long run)
```

### Warning Patterns
1. **Declining trend:** Score dropping each day = overtraining risk
2. **Consistently low:** Score <70 for 5+ days = need rest week
3. **High variability:** Swings of 20+ points = unstable recovery
4. **Weekend crash:** Major drop Sat/Sun = too hard on weekends

## Integration with Training Load

When recovery score is combined with training load from `mart_training_analysis`:

### High Load + High Recovery = Good (sustainable training)
### High Load + Low Recovery = RED FLAG (overtraining risk)
### Low Load + High Recovery = Opportunity (ready for harder work)
### Low Load + Low Recovery = Investigate (why low recovery with light training?)

## Advanced Insights

### Sleep Efficiency
- **>90%:** Excellent sleep quality
- **85-90%:** Good sleep quality
- **80-85%:** Fair sleep quality
- **<80%:** Poor sleep quality (fragmented sleep)

### HRV Interpretation (when available)
- Rising HRV trend = improving recovery
- Falling HRV trend = accumulating fatigue
- Use HRV alongside RHR for best assessment

### Body Battery Net Change
- Consistent positive days = good recovery habits
- Consistent negative days = not recovering fully
- Target: average net change >0 over 7 days

## Tips for Improving Recovery Score

### To Improve Sleep Component (+40 points max)
- Target 8+ hours per night
- Consistent bed/wake times
- Cool, dark room
- Limit caffeine after 2pm
- Avoid screens 1 hour before bed

### To Improve RHR Component (+20 points max)
- Quality sleep
- Proper training load management
- Stay hydrated
- Manage stress
- Adequate nutrition

### To Improve Stress Component (+20 points max)
- Meditation/mindfulness
- Time management
- Work-life balance
- Limit caffeine
- Regular easy activity

### To Improve Body Battery Component (+20 points max)
- Full sleep duration
- Rest days when needed
- Manage training intensity
- Reduce daily stressors
- Proper nutrition and hydration
