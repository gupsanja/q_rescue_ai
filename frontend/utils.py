def calculate_disaster_metrics(
    severity,
    affected_population,
    available_ambulances,
    available_rescue_teams,
    available_food_units
):
    """
    This function generates simulated disaster response metrics.
    Member 3 can use this dummy logic until backend integration is completed.
    """

    estimated_casualties = int((severity / 100) * affected_population)

    response_time = max(5, int(30 - (available_ambulances * 0.4) - (available_rescue_teams * 0.3)))

    resources_needed = int((affected_population / 1000) + (severity * 5))

    optimisation_score = min(100, int(60 + severity * 3 + available_rescue_teams * 0.8))

    recommended_ambulances = max(available_ambulances, int(severity * 2))
    recommended_rescue_teams = max(available_rescue_teams, int(severity * 1.5))
    recommended_food_units = max(available_food_units, int(affected_population / 300))

    critical_risk = min(50, severity * 5)
    high_risk = min(30, severity * 3)
    medium_risk = 20
    low_risk = max(0, 100 - critical_risk - high_risk - medium_risk)

    return {
        "estimated_casualties": estimated_casualties,
        "response_time": response_time,
        "resources_needed": resources_needed,
        "optimisation_score": optimisation_score,
        "recommended_ambulances": recommended_ambulances,
        "recommended_rescue_teams": recommended_rescue_teams,
        "recommended_food_units": recommended_food_units,
        "critical_risk": critical_risk,
        "high_risk": high_risk,
        "medium_risk": medium_risk,
        "low_risk": low_risk
    }
