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


def agents_for_sla(
    target_sla: float,
    calls_per_hour: float,
    aht_seconds: float,
    target_answer_time_seconds: float,
    max_agents: int = 1000,
) -> int:
    """
    Find the smallest number of agents that reaches at least target_sla
    for one interval.

    This is a simple search, similar in spirit to the VBA AgentsSLA function. [attached_file:1]

    Inputs:
      - target_sla: e.g. 0.8 for 80%
      - calls_per_hour: forecast calls in this interval (scaled to per hour)
      - aht_seconds: average handle time in seconds
      - target_answer_time_seconds: e.g. 20 seconds
      - max_agents: safety cap so we don't loop forever

    Output:
      - integer number of agents
    """

    # Protect against silly inputs
    if target_sla <= 0:
        # If target is 0 or less, 0 agents is already enough
        return 0
    if calls_per_hour <= 0 or aht_seconds <= 0:
        # No calls or no AHT: no agents needed
        return 0

    # Make sure target_sla is not > 1
    if target_sla > 1:
        target_sla = target_sla / 100.0  # allow 80 as 80%

    # Start with a basic guess:
    # intensity (erlangs) rounded up, plus 1, just like many Erlang examples. [web:26]
    intensity = traffic_intensity(calls_per_hour, aht_seconds)
    if intensity <= 0:
        return 0

    agents = max(1, math.ceil(intensity + 1))

    # Safety: don't start above max_agents
    agents = min(agents, max_agents)

    # Now keep adding agents until SLA is good enough or we hit max_agents
    while agents <= max_agents:
        sla = sla_for_interval(
            agents=agents,
            calls_per_hour=calls_per_hour,
            aht_seconds=aht_seconds,
            target_answer_time_seconds=target_answer_time_seconds,
        )

        # If SLA meets or beats the target, we stop and return this agent count
        if sla >= target_sla:
            return agents

        agents += 1

    # If we get here, something is off (too few agents allowed)
    # Return max_agents as a "best we could do".
    return max_agents


import pandas as pd

def required_agents_and_hours_sla(
volume_df: "pd.DataFrame",
aht_df: "pd.DataFrame",
target_sla: float,
target_answer_time_seconds: float,
interval_minutes: int,
) -> tuple["pd.DataFrame", "pd.DataFrame"]:
"""
For a whole week grid:
- volume_df: calls per interval (rows = intervals, cols = days)
- aht_df: AHT in seconds, same shape as volume_df
Calculate:
- required_agents_df: agents needed per cell
- required_hours_df: required_hours = agents * (interval_minutes / 60)
  This uses agents_for_sla() for each cell.[2][1]
  """

  # Copy shape and index/columns from volume_df
  required_agents = pd.DataFrame(
      0,
      index=volume_df.index,
      columns=volume_df.columns,
  )
  required_hours = pd.DataFrame(
      0.0,
      index=volume_df.index,
      columns=volume_df.columns,
  )

  interval_hours = interval_minutes / 60.0

  for i in volume_df.index:
      for day in volume_df.columns:
          calls = float(volume_df.at[i, day] or 0)
          aht = float(aht_df.at[i, day] or 0)

          if calls <= 0 or aht <= 0:
              # No calls or no AHT: no agents, no hours
              agents = 0
          else:
              agents = agents_for_sla(
                  target_sla=target_sla,
                  calls_per_hour=calls * (60.0 / interval_minutes),
                  aht_seconds=aht,
                  target_answer_time_seconds=target_answer_time_seconds,
              )

          required_agents.at[i, day] = agents
          required_hours.at[i, day] = agents * interval_hours

  return required_agents, required_hours
