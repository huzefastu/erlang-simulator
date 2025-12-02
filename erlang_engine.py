# erlang_engine.py
#
# Erlang calculator "brain":
# - traffic_intensity (erlangs)
# - Erlang C formula
# - SLA for one interval
# - ASA for one interval
# - agents_for_sla / agents_for_asa (one interval)
# - required_agents_and_hours_sla / _asa (full week grids)

import math
import pandas as pd


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
    """
    if agents <= 0 or intensity <= 0:
        return 0.0

    # utilisation
    rho = intensity / agents
    if rho >= 1.0:
        rho = 0.999999

    # sum_{n=0..agents} A^n / n!
    sum_terms = 0.0
    term = 1.0  # A^0 / 0! = 1
    for n in range(0, agents + 1):
        if n > 0:
            term *= intensity / n
        sum_terms += term

    a_power_n_over_n_fact = term  # last term for n = agents

    numerator = a_power_n_over_n_fact * (agents / (agents - intensity))
    denominator = sum_terms
    c = numerator / denominator

    c = max(0.0, min(1.0, c))
    return c


def sla_for_interval(
    agents: int,
    calls_per_hour: float,
    aht_seconds: float,
    target_answer_time_seconds: float,
) -> float:
    """
    Service level for one interval:
    SLA = (1 - C) + C * exp(-(agents - A) * (T / AHT))
    where:
      C = Erlang C
      A = intensity (erlangs)
      T = target answer time (seconds)
    """
    if agents <= 0 or calls_per_hour <= 0 or aht_seconds <= 0:
        return 0.0

    A = traffic_intensity(calls_per_hour, aht_seconds)
    if A <= 0:
        return 0.0

    C = erlang_c(agents, A)

    rho = A / agents
    if rho >= 1.0:
        rho = 0.999999

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
    """
    if target_sla <= 0:
        return 0
    if calls_per_hour <= 0 or aht_seconds <= 0:
        return 0

    if target_sla > 1:
        target_sla = target_sla / 100.0  # allow 80 as 80%

    intensity = traffic_intensity(calls_per_hour, aht_seconds)
    if intensity <= 0:
        return 0

    agents = max(1, math.ceil(intensity + 1))
    agents = min(agents, max_agents)

    while agents <= max_agents:
        sla = sla_for_interval(
            agents=agents,
            calls_per_hour=calls_per_hour,
            aht_seconds=aht_seconds,
            target_answer_time_seconds=target_answer_time_seconds,
        )
        if sla >= target_sla:
            return agents
        agents += 1

    return max_agents


def asa_for_interval(
    agents: int,
    calls_per_hour: float,
    aht_seconds: float,
) -> float:
    """
    ASA for one interval using Erlang C:
      ASA = (Erlang_C * AHT) / (agents - A)
    If agents <= A, system overloaded -> return large ASA.
    """
    if agents <= 0 or calls_per_hour <= 0 or aht_seconds <= 0:
        return 0.0

    A = traffic_intensity(calls_per_hour, aht_seconds)
    if A <= 0:
        return 0.0

    if agents <= A:
        return 999999.0

    C = erlang_c(agents, A)
    asa = (C * aht_seconds) / (agents - A)
    return asa


def agents_for_asa(
    target_asa_seconds: float,
    calls_per_hour: float,
    aht_seconds: float,
    max_agents: int = 1000,
) -> int:
    """
    Find smallest number of agents to reach target ASA (seconds)
    for one interval, by simple upward search.
    """
    if target_asa_seconds <= 0:
        return 0
    if calls_per_hour <= 0 or aht_seconds <= 0:
        return 0

    A = traffic_intensity(calls_per_hour, aht_seconds)
    if A <= 0:
        return 0

    agents = max(1, math.ceil(A + 1))
    agents = min(agents, max_agents)

    while agents <= max_agents:
        asa = asa_for_interval(
            agents=agents,
            calls_per_hour=calls_per_hour,
            aht_seconds=aht_seconds,
        )
        if asa <= target_asa_seconds:
            return agents
        agents += 1

    return max_agents


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
    Returns:
      - required_agents_df
      - required_hours_df = agents * (interval_minutes / 60)
    """
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


def required_agents_and_hours_asa(
    volume_df: "pd.DataFrame",
    aht_df: "pd.DataFrame",
    target_asa_seconds: float,
    interval_minutes: int,
) -> tuple["pd.DataFrame", "pd.DataFrame"]:
    """
    For a whole week grid (ASA-based):
      - volume_df: calls per interval
      - aht_df: AHT in seconds
    Returns:
      - required_agents_df
      - required_hours_df = agents * (interval_minutes / 60)
    """
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
            calls_interval = float(volume_df.at[i, day] or 0)
            aht = float(aht_df.at[i, day] or 0)

            if calls_interval <= 0 or aht <= 0:
                agents = 0
            else:
                calls_per_hour = calls_interval * (60.0 / interval_minutes)
                agents = agents_for_asa(
                    target_asa_seconds=target_asa_seconds,
                    calls_per_hour=calls_per_hour,
                    aht_seconds=aht,
                )

            required_agents.at[i, day] = agents
            required_hours.at[i, day] = agents * interval_hours

    return required_agents, required_hours
