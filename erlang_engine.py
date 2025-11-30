# erlang_engine.py
#
# Small Erlang calculator "brain" that we will grow later.
# For now, we just handle:
# - basic traffic intensity (erlangs)
# - Erlang C formula
# - a simple SLA calculation

import math


def traffic_intensity(calls_per_hour: float, aht_seconds: float) -> float:
    """
    Calculate traffic intensity (erlangs).
    erlangs = (calls per hour * AHT seconds) / 3600
    """
    if calls_per_hour <= 0 or aht_seconds <= 0:
        return 0.0
    return (calls_per_hour * aht_seconds) / 3600.0


def erlang_c(agents: int, intensity: float) -> float:
    """
    Erlang C formula: probability a call waits (is queued).
    This follows the same logic as the ErlangC function in the VBA file.
    """
    if agents <= 0 or intensity <= 0:
        return 0.0

    # If offered load is equal or higher than agents, system is overloaded.
    # Clamp utilisation just below 1 to avoid divide-by-zero explosions.
    rho = intensity / agents
    if rho >= 1.0:
        rho = 0.999999

    # Compute the sum of (A^n / n!) for n = 0..agents
    sum_terms = 0.0
    term = 1.0  # A^0 / 0! = 1
    for n in range(0, agents + 1):
        if n > 0:
            term *= intensity / n
        sum_terms += term

    # Last term for n = agents
    a_power_n_over_n_fact = term  # already last value from loop

    # Erlang C formula
    numerator = a_power_n_over_n_fact * (agents / (agents - intensity))
    denominator = sum_terms
    c = numerator / denominator

    # Keep in [0,1]
    c = max(0.0, min(1.0, c))
    return c


def sla_for_interval(
    agents: int,
    calls_per_hour: float,
    aht_seconds: float,
    target_answer_time_seconds: float,
) -> float:
    """
    Approximate service level for one interval:
    = % of calls answered within target_answer_time_seconds.

    Formula (same structure as VBA SLA function):
    SLA = (1 - C) + C * exp(-(agents - A) * (T / AHT))
    where:
      C = Erlang C (probability of waiting)
      A = intensity (erlangs)
      T = target answer time (seconds)
    """

    if agents <= 0 or calls_per_hour <= 0 or aht_seconds <= 0:
        return 0.0

    A = traffic_intensity(calls_per_hour, aht_seconds)
    if A <= 0:
        return 0.0

    C = erlang_c(agents, A)

    # utilisation rho = A / agents
    rho = A / agents
    if rho >= 1.0:
        rho = 0.999999

    # This matches the "1 - C * exp(-...)" style used in the VBA SLA function. [attached_file:1]
    exponent = -(agents - A) * (target_answer_time_seconds / aht_seconds)
    part_queued_and_answered_in_time = C * math.exp(exponent)

    sla = (1.0 - C) + part_queued_and_answered_in_time

    sla = max(0.0, min(1.0, sla))
    return sla
