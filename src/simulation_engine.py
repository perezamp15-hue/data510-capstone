# src/simulation_engine.py
import numpy as np
import psycopg2
from config import DATABASE_URL

def calculate_environmental_modifier(weather, stadium):
    """Computes a scalar shift modifying air trajectory resistance calculations."""
    hr_modifier = 1.0
    hr_modifier += (weather.get('temperature', 70) - 70) * 0.005  # Density altitude carry
    hr_modifier += (stadium.get('altitude', 0) / 1000) * 0.05       # Thin air bonus
    
    if not stadium.get('wind_shielded', False):
        if weather.get('wind_direction') == 'Out':
            hr_modifier += (weather.get('wind_speed', 0) * 0.015)
        elif weather.get('wind_direction') == 'In':
            hr_modifier -= (weather.get('wind_speed', 0) * 0.015)
            
    return max(0.5, hr_modifier)

def calculate_matchup_odds(hitter, pitcher, ump_mod, env_mod):
    """Applies Log-Odds interaction models tracking current health and tiredness values."""
    league_avg_xwoba = 0.320
    
    hitter_xwoba = hitter.get('rolling_30_xwoba', 0.320)
    pitcher_allowed = pitcher.get('xwoba_allowed', 0.320)
    
    # Apply health and exhaustion degradation layers
    if hitter.get('injury_status') == 'Day-to-Day': hitter_xwoba *= 0.92
    if hitter.get('rolling_15_ops', 0.750) > 0.950: hitter_xwoba *= 1.05  
    if pitcher.get('pitches_last_7_days', 0) > 100: pitcher_allowed *= 1.06
    if pitcher.get('travel_distance', 0) > 1200: hitter_xwoba *= 0.98
        
    combined_xwoba = hitter_xwoba * (pitcher_allowed / league_avg_xwoba)
    
    probabilities = {
        'strikeout_or_out': max(0.1, (1.0 - (combined_xwoba * 2.0)) * ump_mod.get('k_bias', 1.0)),
        'walk': 0.09 * ump_mod.get('bb_bias', 1.0),
        'single': combined_xwoba * 1.1,
        'double_triple': combined_xwoba * 0.3,
        'home_run': (combined_xwoba * 0.2) * env_mod
    }
    
    total = sum(probabilities.values())
    return {k: v / total for k, v in probabilities.items()}

def simulate_half_inning(lineup, pitcher, ump_mod, env_mod, state):
    """Iterates a standard Markov framework base-runner loop state machine."""
    outs, runs = 0, 0
    bases = [0, 0, 0] 
    
    while outs < 3:
        hitter = lineup[state['batter_index']]
        probs = calculate_matchup_odds(hitter, pitcher, ump_mod, env_mod)
        
        result = np.random.choice(list(probs.keys()), p=list(probs.values()))
        
        if result == 'strikeout_or_out':
            outs += 1
        elif result == 'walk':
            if bases[0] == 1 and bases[1] == 1 and bases[2] == 1: runs += 1
            elif bases[0] == 1 and bases[1] == 1: bases[2] = 1
            elif bases[0] == 1: bases[1] = 1
            bases[0] = 1
        elif result == 'single':
            runs += bases[2]
            bases[2], bases[1], bases[0] = bases[1], bases[0], 1
        elif result == 'double_triple':
            runs += (bases[2] + bases[1])
            bases[2], bases[1], bases[0] = bases[0], 1, 0
        elif result == 'home_run':
            runs += (sum(bases) + 1)
            bases = [0, 0, 0]
            
        state['batter_index'] = (state['batter_index'] + 1) % 9
    return runs

def run_monte_carlo_simulation(game_id, num_simulations=10000):
    home_wins = 0
    
    # Mock fallback dictionaries for structural isolation verification testing
    dummy_hitter = {'rolling_30_xwoba': 0.335, 'injury_status': 'Healthy'}
    dummy_pitcher = {'xwoba_allowed': 0.315, 'pitches_last_7_days': 35}
    home_lineup = [dummy_hitter] * 9
    away_lineup = [dummy_hitter] * 9
    
    ump_mod = {'k_bias': 1.0, 'bb_bias': 1.0}
    env_mod = 1.00 
    
    for _ in range(num_simulations):
        home_score, away_score = 0, 0
        state_home = {'batter_index': 0}
        state_away = {'batter_index': 0}
        
        for inning in range(1, 10):
            away_score += simulate_half_inning(away_lineup, dummy_pitcher, ump_mod, env_mod, state_away)
            home_score += simulate_half_inning(home_lineup, dummy_pitcher, ump_mod, env_mod, state_home)
            
        if home_score > away_score:
            home_wins += 1
            
    print(f"Execution complete. Win expectation: {(home_wins / num_simulations) * 100:.2%}")
    return home_wins / num_simulations

if __name__ == "__main__":
    run_monte_carlo_simulation(game_id=0)
