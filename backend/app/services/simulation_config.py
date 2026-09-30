"""Every tunable number of the What-If simulator lives here, so it is easy to explain and change.

None of these are "results". They are model settings; results are calculated from the user's data.
"""

# ---------------------------------------------------------------- Monte Carlo
N_SIMULATIONS = 1000  # runs per plan
RANDOM_SEED = 42  # fixed seed -> same inputs always give the same numbers (reproducible demo)
MAX_HORIZON_DAYS = 14  # tasks due later than this are left out of the simulation window

# ---------------------------------------------------------------- day model
PERIOD_BLOCK_HOURS = 4.0  # first 4 h of the day in the first period, next 4 h in the second, rest in the third
PRODUCTIVITY_FACTOR_MIN, PRODUCTIVITY_FACTOR_MAX = 0.6, 1.4  # safety clamp for (period productivity / own average)

# Fatigue: after FATIGUE_THRESHOLD_HOURS of work in a day, every further hour is a bit slower.
#   fatigue_factor = max(FATIGUE_FLOOR, 1 - fatigue_rate * hours_over_threshold)
FATIGUE_THRESHOLD_HOURS = 4.0
FATIGUE_RATE = 0.05  # typical value (used for the single "typical" run)
FATIGUE_RATE_RANGE = (0.03, 0.07)  # Monte Carlo draws the rate uniformly from this range
FATIGUE_FLOOR = 0.70

# Task switching: each switch between tasks loses this share of the day's available hours
# (0.05 x 6 h = 18 minutes of refocusing).
SWITCH_COST = 0.05

# Procrastination: each simulated day, with probability = the Twin's delay score, this many hours are lost.
PROCRASTINATION_LOSS_HOURS = 1.0
# Day-to-day noise in how many hours are really available (Monte Carlo only).
AVAILABILITY_NOISE_SD = 0.25

# ---------------------------------------------------------------- labels
WORKLOAD_COMFORTABLE, WORKLOAD_MANAGEABLE, WORKLOAD_HIGH = 0.8, 1.0, 1.2
RISK_LOW, RISK_HIGH = 0.3, 0.6  # deadline risk: < 0.3 Low, < 0.6 Moderate, otherwise High
CONFIDENCE_LOW, CONFIDENCE_HIGH = 0.3, 0.7  # Twin confidence: < 0.3 Low, < 0.7 Moderate, otherwise High

PRIORITY_WEIGHT = {"high": 3.0, "medium": 2.0, "low": 1.0}

# ---------------------------------------------------------------- recommendation score
# score = W_PROGRESS * weighted progress + W_ON_TIME * weighted on-time chance
#         - W_RISK * worst deadline risk - W_OVERLOAD * max(0, workload - 1) + habit bonus
W_PROGRESS = 0.4
W_ON_TIME = 0.4
W_RISK = 0.3
W_OVERLOAD = 0.2
HABIT_BONUS = 0.03  # plan starts the way the Twin's observed task-ordering habit says
NO_CLEAR_PREFERENCE_MARGIN = 0.03  # top two scores closer than this -> no forced recommendation


def workload_label(ratio: float) -> str:
    if ratio < WORKLOAD_COMFORTABLE:
        return "Comfortable"
    if ratio <= WORKLOAD_MANAGEABLE:
        return "Manageable"
    if ratio <= WORKLOAD_HIGH:
        return "High"
    return "Over capacity"


def risk_label(risk: float) -> str:
    if risk < RISK_LOW:
        return "Low"
    if risk < RISK_HIGH:
        return "Moderate"
    return "High"


def confidence_label(confidence: float) -> str:
    if confidence < CONFIDENCE_LOW:
        return "Low"
    if confidence < CONFIDENCE_HIGH:
        return "Moderate"
    return "High"
