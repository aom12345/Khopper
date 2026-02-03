import random
import math

# Try importing matplotlib, handle gracefully if missing
try:
    import matplotlib.pyplot as plt
    PLOT_AVAILABLE = True
except ImportError:
    PLOT_AVAILABLE = False
    print("Warning: matplotlib not found. Graphing will be skipped.")

# ==========================================
#        CONFIGURATION
# ==========================================
TOTAL_PLAYERS = 2       
TOTAL_GAME_RUNS = 20000 
EQUITY_SIMULATIONS = 400  
ANTE = 100.0

# THRESHOLDS (From your previous data)
HERO_FOLD_THRESHOLDS = {
    5: 0.1450, 
    4: 0.2030, 
    3: 0.2555,
    2: 0.3565    
}

# REALIZATION DATA (River Decay)
RIVER_RATES = {
    2: [0.79, 0.90, 0.96, 0.98, 0.99],
    3: [0.69, 0.89, 0.95, 0.97, 0.98], 
    4: [0.63, 0.90, 0.95, 0.94, 0.97],
    5: [0.53, 0.88, 0.95, 0.91, 0.98]
}
TURN_RATES = {
    2: [0.76, 0.91, 0.96, 0.98, 0.99],
    3: [0.84, 0.94, 0.96, 0.98, 0.98],
    4: [0.85, 0.94, 0.96, 0.96, 0.98],
    5: [0.83, 0.94, 0.95, 0.96, 0.98]
}
FLOP_RATES = {
    2: [0.65, 0.90, 0.95, 0.98, 0.98],
    3: [0.88, 0.93, 0.96, 0.98, 0.98],
    4: [0.88, 0.94, 0.96, 0.98, 0.98],
    5: [0.87, 0.94, 0.96, 0.97, 0.98]
}

def get_realized_equity(raw_eq, players, stage):
    bucket = int(raw_eq * 5)
    if bucket >= 5: bucket = 4
    
    # EXACT SELECTION
    if stage == 1: 
        table = FLOP_RATES
    elif stage == 2: 
        table = TURN_RATES  # <--- Use the correct Turn decay
    else: 
        table = RIVER_RATES
    
    if players in table: 
        ratio = table[players][bucket]
    else: 
        ratio = 1.0 
        
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
    # Check normal straights
    for r in range(8, -1, -1):
        if (rank_bits >> r) & 0x1F == 0x1F: straight_high = r + 4; break
    # Check Wheel (A-2-3-4-5)
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
        # Safety check for kickers
        k1 = k[0] if len(k) > 0 else 0
        k2 = k[1] if len(k) > 1 else 0
        return (3 << 24) | (trips[0] << 16) | (k1 << 12) | (k2 << 8)
        
    if len(pairs) >= 2:
        k = [r for r in range(12, -1, -1) if r != pairs[0] and r != pairs[1] and rank_counts[r] > 0]
        k1 = k[0] if len(k) > 0 else 0
        return (2 << 24) | (pairs[0] << 16) | (pairs[1] << 12) | k1
        
    if pairs:
        k = []
        for r in range(12, -1, -1):
            if r != pairs[0] and rank_counts[r] > 0:
                k.append(r)
                if len(k) == 3: break
        # Pad if not enough kickers (rare but safe)
        while len(k) < 3: k.append(0)
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
        # Ensure we have enough cards to deal
        if len(available_deck) < cards_needed: break
        
        deal = random.sample(available_deck, cards_needed)
        turn, river = deal[0], deal[1]
        community = flop + [turn, river]
        
        my_score = evaluate_hand_score_fast(player_hand + community)
        best_opp = -1
        
        for i in range(2, len(deal), 2):
            op_score = evaluate_hand_score_fast([deal[i], deal[i+1]] + community)
            if op_score > best_opp: best_opp = op_score
            
        if my_score > best_opp: wins += 1
        elif my_score == best_opp: draws += 1
        
    return (wins + 0.5 * draws) / simulations

# ==========================================
#        HYBRID STRATEGY SIMULATOR
# ==========================================

def run_hybrid_sim():
    # Comparing Fixed vs Hybrid
    strategies = ["Fixed_Aggressive", "Hybrid_Safe"]
    
    stats = {i: {k:0 for k in strategies} for i in range(0, 100, 5)}
    counts = {i: 0 for i in range(0, 100, 5)}
    hero_floor = HERO_FOLD_THRESHOLDS.get(TOTAL_PLAYERS, 0.20) # Default if key missing
    
    print(f"--- Hybrid Strategy Analysis ({TOTAL_PLAYERS} Players) ---")
    print("Testing 'Safe R2' + 'Equity-Driven R3'")
    
    full_deck = list(range(52))
    
    for i in range(TOTAL_GAME_RUNS):
        random.shuffle(full_deck)
        player_hand = full_deck[0:2]
        flop = full_deck[2:5]
        turn = full_deck[5]
        river = full_deck[6]
        community = flop + [turn, river]
        
        # Initial Equity
        eq_flop = calculate_equity(player_hand, flop, TOTAL_PLAYERS, EQUITY_SIMULATIONS)
        realized_flop = get_realized_equity(eq_flop, TOTAL_PLAYERS, 1)
        
        eq_bucket = int(realized_flop * 20) * 5 
        if eq_bucket >= 100: eq_bucket = 95
        
        if realized_flop < hero_floor: continue
        counts[eq_bucket] += 1

        # Simulate Opponents (Randomized Betting Profiles)
        opp_bets = [] 
        active_opponents = []
        for idx in range(TOTAL_PLAYERS - 1):
            opp_hand = full_deck[7+(idx*2) : 7+(idx*2)+2]
            op_raw = calculate_equity(opp_hand, flop, TOTAL_PLAYERS, 20)
            op_real = get_realized_equity(op_raw, TOTAL_PLAYERS, 1)
            
            # Simple Profiles
            if op_real < 0.20: 
                active_opponents.append(False); opp_bets.append([0,0,0])
            elif op_real > 0.60: 
                active_opponents.append(True); opp_bets.append([300, 450, 562.5])
            elif op_real > 0.40: 
                active_opponents.append(True); opp_bets.append([200, 200, 200])
            else: 
                active_opponents.append(True); opp_bets.append([100, 50, 37.5])
        
        # --- FIXED STRATEGY (Baseline) ---
        hero_bets_agg = [300, 450, 562.5]
        hero_inv_agg = sum(hero_bets_agg) + ANTE
        pot_agg = (TOTAL_PLAYERS * ANTE) + hero_inv_agg + sum([sum(b) for b in opp_bets])
        cap_agg = 4.0 * hero_inv_agg
        
        # --- HYBRID STRATEGY ---
        
        # R1: Probe 110
        h_r1 = 110.0
        
        # R2: The "Safe Side" Bet
        h_r2 = 50.0 + (realized_flop * 200.0) 
        min_r2 = h_r1 * 0.5
        max_r2 = h_r1 * 1.5
        h_r2 = max(min_r2, min(max_r2, h_r2))
        
        # R3: Cap Optimization (Precision)
        current_inv = ANTE + h_r1 + h_r2
        opp_contrib = sum([sum(b) for b in opp_bets])
        pot_pre_r3 = (TOTAL_PLAYERS * ANTE) + current_inv + opp_contrib
        
        target_r3 = (pot_pre_r3 - (4.0 * current_inv)) / 3.0
        
        final_r3 = target_r3 * realized_flop
        
        min_r3 = h_r2 * 0.75
        max_r3 = h_r2 * 1.25
        h_r3 = max(min_r3, min(max_r3, final_r3))
        
        hero_bets_hyb = [h_r1, h_r2, h_r3]
        hero_inv_hyb = sum(hero_bets_hyb) + ANTE
        pot_hyb = (TOTAL_PLAYERS * ANTE) + hero_inv_hyb + opp_contrib
        cap_hyb = 4.0 * hero_inv_hyb
        
        # --- SHOWDOWN ---
        any_active = any(active_opponents)
        
        if not any_active:
            profit_agg = (TOTAL_PLAYERS * ANTE) - ANTE
            profit_hyb = (TOTAL_PLAYERS * ANTE) - ANTE
        else:
            my_score = evaluate_hand_score_fast(player_hand + community)
            best_opp_score = -1
            for idx, is_active in enumerate(active_opponents):
                if is_active:
                    oh = full_deck[7+(idx*2) : 7+(idx*2)+2]
                    s = evaluate_hand_score_fast(oh + community)
                    if s > best_opp_score: best_opp_score = s
            
            if my_score > best_opp_score:
                profit_agg = min(pot_agg, cap_agg) - hero_inv_agg
                profit_hyb = min(pot_hyb, cap_hyb) - hero_inv_hyb
            else:
                profit_agg = -hero_inv_agg
                profit_hyb = -hero_inv_hyb

        stats[eq_bucket]["Fixed_Aggressive"] += profit_agg
        stats[eq_bucket]["Hybrid_Safe"] += profit_hyb

        if (i+1) % 500 == 0: print(f"Simulated {i+1} hands...")

    return stats, counts

if __name__ == "__main__":
    # --- FIX APPLIED HERE: Unpack tuple correctly ---
    stats, counts = run_hybrid_sim()
    
    print("\n" + "="*80)
    print(f"  HYBRID STRATEGY REPORT (Safe R2 / Precise R3)")
    print("="*80)
    print(f"{'Equity':<8} | {'Fixed Aggro':<12} | {'Hybrid Safe':<12} | {'Choice'}")
    print("-" * 80)
    
    x_eq = []
    y_agg = []
    y_hyb = []
    
    for eq in sorted(stats.keys()):
        if counts[eq] < 10: continue # Lowered threshold slightly for visibility
        
        avg_agg = stats[eq]["Fixed_Aggressive"] / counts[eq]
        avg_hyb = stats[eq]["Hybrid_Safe"] / counts[eq]
        
        x_eq.append(eq)
        y_agg.append(avg_agg)
        y_hyb.append(avg_hyb)
        
        best = "HYBRID" if avg_hyb > avg_agg else "FIXED"
        
        print(f"{eq}-{eq+5}%    | {avg_agg:8.1f}     | {avg_hyb:8.1f}     | {best}")

    if PLOT_AVAILABLE:
        plt.figure(figsize=(10, 6))
        plt.plot(x_eq, y_agg, marker='o', label="Fixed Aggressive", color='red')
        plt.plot(x_eq, y_hyb, marker='x', label="Hybrid (Safe R2)", color='green')
        plt.title(f"Hybrid vs Fixed Strategy ({TOTAL_PLAYERS} Players)")
        plt.xlabel("Realized Flop Equity (%)")
        plt.ylabel("Avg Profit")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.show()