import random
import math
import matplotlib.pyplot as plt

# ==========================================
#        CONFIGURATION
# ==========================================

TOTAL_PLAYERS = 2       
TOTAL_GAME_RUNS = 20000 
EQUITY_SIMULATIONS = 200  

ANTE = 100.0

# PATHS: [Round 1, Round 2, Round 3]
STRATEGY_PATHS = {
    "Conservative": [100, 50, 37.5],    # Total Invest: 187.5
    "Moderate":     [200, 200, 200],    # Total Invest: 600.0
    "Aggressive":   [300, 450, 562.5]   # Total Invest: 1312.5
}

# ==========================================
#      REALIZATION CALIBRATION (DATA)
# ==========================================

FLOP_RATES = {
    3: [0.88, 0.93, 0.96, 0.98, 0.98],
    4: [0.88, 0.94, 0.96, 0.98, 0.98],
    5: [0.87, 0.94, 0.96, 0.97, 0.98]
}

TURN_RATES = {
    3: [0.84, 0.94, 0.96, 0.98, 0.98],
    4: [0.85, 0.94, 0.96, 0.96, 0.98],
    5: [0.83, 0.94, 0.95, 0.96, 0.98]
}

# Updated with your River Data
RIVER_RATES = {
    3: [0.69, 0.89, 0.95, 0.97, 0.98], 
    4: [0.63, 0.90, 0.95, 0.94, 0.97],
    5: [0.53, 0.88, 0.95, 0.91, 0.98]
}

def get_realized_equity(raw_eq, players, stage_cards):
    bucket = int(raw_eq * 5)
    if bucket >= 5: bucket = 4
    
    if stage_cards == 3: table = FLOP_RATES
    elif stage_cards == 4: table = TURN_RATES
    else: table = RIVER_RATES
    
    if players in table: ratio = table[players][bucket]
    else: ratio = 1.0 
    return raw_eq * ratio

# ==========================================
#          POKER LOGIC
# ==========================================
RANK_LOOKUP = [i // 4 for i in range(52)]
SUIT_LOOKUP = [i % 4 for i in range(52)]

def evaluate_hand_score_fast(cards):
    rank_counts = [0] * 13; suit_counts = [0] * 4; rank_bits = 0 
    for c in cards:
        r = RANK_LOOKUP[c]; s = SUIT_LOOKUP[c]
        rank_counts[r] += 1; suit_counts[s] += 1; rank_bits |= (1 << r)
    flush_suit = -1
    for s in range(4):
        if suit_counts[s] >= 5: flush_suit = s; break
    straight_high = -1
    for r in range(8, -1, -1):
        if (rank_bits >> r) & 0x1F == 0x1F: straight_high = r + 4; break
    if straight_high == -1 and (rank_bits & 0x100F) == 0x100F: straight_high = 3
    if flush_suit != -1:
        f_ranks = 0
        for c in cards:
            if SUIT_LOOKUP[c] == flush_suit: f_ranks |= (1 << RANK_LOOKUP[c])
        sf_high = -1
        for r in range(8, -1, -1):
            if (f_ranks >> r) & 0x1F == 0x1F: sf_high = r + 4; break
        if sf_high == -1 and (f_ranks & 0x100F) == 0x100F: sf_high = 3
        if sf_high != -1: return (8 << 24) | sf_high
    quads, trips, pairs, singles = [], [], [], []
    for r in range(12, -1, -1):
        count = rank_counts[r]
        if count == 4: quads.append(r)
        elif count == 3: trips.append(r)
        elif count == 2: pairs.append(r)
        elif count == 1: singles.append(r)
    if quads:
        kicker = -1
        for r in range(12, -1, -1):
            if r != quads[0] and rank_counts[r] > 0: kicker = r; break
        return (7 << 24) | (quads[0] << 16) | kicker
    if trips and (len(trips) >= 2 or pairs):
        major = trips[0]; minor = trips[1] if len(trips) >= 2 else pairs[0]
        return (6 << 24) | (major << 16) | minor
    if flush_suit != -1:
        fl_ranks = [RANK_LOOKUP[c] for c in cards if SUIT_LOOKUP[c] == flush_suit]
        fl_ranks.sort(reverse=True)
        score = (5 << 24)
        for i, r in enumerate(fl_ranks[:5]): score |= (r << (20 - i*4))
        return score
    if straight_high != -1: return (4 << 24) | straight_high
    if trips:
        k = [r for r in range(12, -1, -1) if r != trips[0] and rank_counts[r] > 0]
        return (3 << 24) | (trips[0] << 16) | (k[0] << 12) | (k[1] << 8)
    if len(pairs) >= 2:
        k = [r for r in range(12, -1, -1) if r != pairs[0] and r != pairs[1] and rank_counts[r] > 0]
        return (2 << 24) | (pairs[0] << 16) | (pairs[1] << 12) | k[0]
    if pairs:
        k = []
        for r in range(12, -1, -1):
            if r != pairs[0] and rank_counts[r] > 0:
                k.append(r); 
                if len(k) == 3: break
        return (1 << 24) | (pairs[0] << 16) | (k[0] << 12) | (k[1] << 8) | (k[2] << 4)
    score = 0
    for i, r in enumerate(singles[:5]): score |= (r << (20 - i*4))
    return score

def calculate_equity(player_hand, flop, num_players, simulations=50):
    wins = 0
    draws = 0 
    used_cards = set(player_hand + flop)
    available_deck = [x for x in range(52) if x not in used_cards]
    cards_needed = (num_players - 1) * 2 + 2 
    for _ in range(simulations):
        deal = random.sample(available_deck, cards_needed)
        turn, river = deal[0], deal[1]; community = flop + [turn, river]
        my_score = evaluate_hand_score_fast(player_hand + community)
        best_opp = -1
        for i in range(2, len(deal), 2):
            op_score = evaluate_hand_score_fast([deal[i], deal[i+1]] + community)
            if op_score > best_opp: best_opp = op_score
        if my_score > best_opp: wins += 1
        elif my_score == best_opp: draws += 1
    return (wins + 0.5 * draws) / simulations

# ==========================================
#          DETAILED SIMULATOR
# ==========================================

def run_detailed_sim():
    # Structure: detailed_stats[bucket][strategy] = {list of profits, fold_count, win_count}
    detailed_stats = {
        i: {
            k: {'profits': [], 'folds': 0, 'wins': 0} 
            for k in STRATEGY_PATHS.keys()
        } 
        for i in range(0, 100, 5)
    }
    
    print(f"--- Running Deep Analysis ({TOTAL_GAME_RUNS} Hands) ---")
    
    full_deck = list(range(52))
    
    for i in range(TOTAL_GAME_RUNS):
        random.shuffle(full_deck)
        player_hand = full_deck[0:2]
        flop = full_deck[2:5]
        turn = full_deck[5]
        river = full_deck[6]
        community = flop + [turn, river]
        
        my_raw_equity = calculate_equity(player_hand, flop, TOTAL_PLAYERS, EQUITY_SIMULATIONS)
        my_realized_eq = get_realized_equity(my_raw_equity, TOTAL_PLAYERS, 3)
        
        eq_bucket = int(my_realized_eq * 20) * 5 
        if eq_bucket >= 100: eq_bucket = 95
        
        for strat_name, bets in STRATEGY_PATHS.items():
            hero_total_cost = sum(bets)
            pot_base = TOTAL_PLAYERS * ANTE
            
            # Opponent Decision
            active_opponents = [True] * (TOTAL_PLAYERS - 1)
            call_cost = hero_total_cost
            total_pot_after_call = pot_base + hero_total_cost + hero_total_cost
            required_equity = call_cost / total_pot_after_call
            
            opps_folded_count = 0
            
            for idx in range(len(active_opponents)):
                opp_hand = full_deck[7+(idx*2) : 7+(idx*2)+2]
                opp_raw = calculate_equity(opp_hand, flop, TOTAL_PLAYERS, 20)
                # Opponent uses RIVER ratio (5 cards) to decide
                opp_realized = get_realized_equity(opp_raw, TOTAL_PLAYERS, 5)
                
                thresh = required_equity * random.uniform(0.95, 1.05)
                
                if opp_realized < thresh:
                    active_opponents[idx] = False
                    opps_folded_count += 1
            
            all_folded = (opps_folded_count == (TOTAL_PLAYERS - 1))
            
            profit = 0
            is_win = False
            
            if all_folded:
                profit = (TOTAL_PLAYERS * ANTE) - ANTE
                detailed_stats[eq_bucket][strat_name]['folds'] += 1
                detailed_stats[eq_bucket][strat_name]['wins'] += 1
                is_win = True
            else:
                num_active = sum(active_opponents)
                final_pot = (TOTAL_PLAYERS * ANTE) + hero_total_cost + (num_active * hero_total_cost)
                my_cap_limit = 4.0 * (hero_total_cost + ANTE)
                
                my_score = evaluate_hand_score_fast(player_hand + community)
                best_opp_score = -1
                for idx, is_active in enumerate(active_opponents):
                    if is_active:
                        oh = full_deck[7+(idx*2) : 7+(idx*2)+2]
                        s = evaluate_hand_score_fast(oh + community)
                        if s > best_opp_score: best_opp_score = s
                
                total_investment = hero_total_cost + ANTE
                
                if my_score > best_opp_score:
                    payout = min(final_pot, my_cap_limit)
                    profit = payout - total_investment
                    detailed_stats[eq_bucket][strat_name]['wins'] += 1
                    is_win = True
                else:
                    profit = -total_investment
            
            detailed_stats[eq_bucket][strat_name]['profits'].append(profit)

        if (i+1) % 5000 == 0: print(f"Simulated {i+1} hands...")

    return detailed_stats

if __name__ == "__main__":
    stats = run_detailed_sim()
    
    print("\n" + "="*100)
    print(f"  DETAILED STRATEGY ANALYSIS (3 Players, Calibrated)")
    print("="*100)
    
    # Headers
    print(f"{'Strat':<13} | {'Avg Profit':<10} | {'Win %':<7} | {'Fold %':<7} | {'Risk(SD)':<9} | {'Min':<6} | {'Max':<6}")
    
    x_eq = []
    y_cons, y_mod, y_agg = [], [], []

    for eq in sorted(stats.keys()):
        # Check if bucket has data
        sample_strat = list(STRATEGY_PATHS.keys())[0]
        n = len(stats[eq][sample_strat]['profits'])
        if n < 20: continue # Skip low sample buckets
        
        print("-" * 100)
        print(f"EQUITY RANGE: {eq}% - {eq+5}%  (Samples: {n})")
        
        best_profit = -float('inf')
        best_strat_name = ""
        
        # Collect stats for graph
        x_eq.append(eq)
        
        for strat in ["Conservative", "Moderate", "Aggressive"]:
            data = stats[eq][strat]
            profits = data['profits']
            
            avg_prof = sum(profits) / n
            win_rate = (data['wins'] / n) * 100
            fold_rate = (data['folds'] / n) * 100
            
            # Standard Deviation Calculation
            variance = sum([(x - avg_prof)**2 for x in profits]) / n
            std_dev = math.sqrt(variance)
            
            min_p = min(profits)
            max_p = max(profits)
            
            if strat == "Conservative": y_cons.append(avg_prof)
            if strat == "Moderate": y_mod.append(avg_prof)
            if strat == "Aggressive": y_agg.append(avg_prof)
            
            if avg_prof > best_profit:
                best_profit = avg_prof
                best_strat_name = strat
                
            # Print Row
            # Highlight the row if it's the current best
            prefix = ">> " if avg_prof == best_profit else "   " 
            print(f"{prefix}{strat:<10} | {avg_prof:9.1f}  | {win_rate:5.1f}%  | {fold_rate:5.1f}%  | {std_dev:8.1f}  | {min_p:6.0f} | {max_p:6.0f}")
        
        print(f"   BEST CHOICE: {best_strat_name.upper()}")

    # Plot
    plt.figure(figsize=(10, 6))
    plt.plot(x_eq, y_cons, label='Conservative', marker='o')
    plt.plot(x_eq, y_mod, label='Moderate', marker='x')
    plt.plot(x_eq, y_agg, label='Aggressive', marker='s')
    plt.axhline(0, color='black', linewidth=1)
    plt.title("Profit Profiles by Realized Equity")
    plt.xlabel("Realized Flop Equity (%)")
    plt.ylabel("Avg Profit")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()