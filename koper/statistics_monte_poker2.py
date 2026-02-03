import random
import time
import statistics

# --- Configuration ---
NUM_OUTER_ITERATIONS = 4000   # Number of different hand scenarios
NUM_MC_SIMULATIONS = 500    # MC runs per scenario (Simulating unknown opponent cards)
NUM_OPPONENTS = 1

# --- Constants & Lookup Tables ---
# Card: 0-51. Rank: Card >> 2 (0-12). Suit: Card & 3 (0-3).
RANK_LOOKUP = tuple(i >> 2 for i in range(52))
SUIT_LOOKUP = tuple(i & 3 for i in range(52))

def evaluate_hand_score_fast(cards):
    """
    Highly optimized Bitwise Evaluator.
    Returns an integer score. Higher integer = Better hand.
    """
    rank_counts = [0] * 13
    suit_counts = [0] * 4
    rank_bits = 0
    
    for c in cards:
        r = RANK_LOOKUP[c]
        s = SUIT_LOOKUP[c]
        rank_counts[r] += 1
        suit_counts[s] += 1
        rank_bits |= (1 << r)

    # Check Flush
    flush_suit = -1
    for s in range(4):
        if suit_counts[s] >= 5:
            flush_suit = s
            break
            
    # Check Straight
    straight_high = -1
    for r in range(8, -1, -1):
        if (rank_bits >> r) & 0x1F == 0x1F:
            straight_high = r + 4
            break
    if straight_high == -1 and (rank_bits & 0x100F) == 0x100F:
        straight_high = 3 # Wheel (A-2-3-4-5)

    # Straight Flush
    if flush_suit != -1:
        f_ranks = 0
        for c in cards:
            if SUIT_LOOKUP[c] == flush_suit:
                f_ranks |= (1 << RANK_LOOKUP[c])
        sf_high = -1
        for r in range(8, -1, -1):
            if (f_ranks >> r) & 0x1F == 0x1F:
                sf_high = r + 4
                break
        if sf_high == -1 and (f_ranks & 0x100F) == 0x100F:
            sf_high = 3
        if sf_high != -1:
            return (8 << 24) | sf_high

    quads, trips, pairs, singles = [], [], [], []
    for r in range(12, -1, -1):
        c = rank_counts[r]
        if c == 4: quads.append(r)
        elif c == 3: trips.append(r)
        elif c == 2: pairs.append(r)
        elif c == 1: singles.append(r)

    # 7. Quads
    if quads:
        kicker = -1
        for r in range(12, -1, -1):
            if r != quads[0] and rank_counts[r] > 0:
                kicker = r; break
        return (7 << 24) | (quads[0] << 16) | kicker

    # 6. Full House
    if trips and (len(trips) >= 2 or pairs):
        major = trips[0]
        minor = trips[1] if len(trips) >= 2 else pairs[0]
        return (6 << 24) | (major << 16) | minor

    # 5. Flush
    if flush_suit != -1:
        fl_ranks = [RANK_LOOKUP[c] for c in cards if SUIT_LOOKUP[c] == flush_suit]
        fl_ranks.sort(reverse=True)
        score = (5 << 24)
        for i, r in enumerate(fl_ranks[:5]): score |= (r << (20 - i*4))
        return score

    # 4. Straight
    if straight_high != -1:
        return (4 << 24) | straight_high

    # 3. Trips
    if trips:
        k = [r for r in range(12, -1, -1) if r != trips[0] and rank_counts[r] > 0]
        return (3 << 24) | (trips[0] << 16) | (k[0] << 12) | (k[1] << 8)

    # 2. Two Pair
    if len(pairs) >= 2:
        k = [r for r in range(12, -1, -1) if r != pairs[0] and r != pairs[1] and rank_counts[r] > 0]
        return (2 << 24) | (pairs[0] << 16) | (pairs[1] << 12) | k[0]

    # 1. Pair
    if pairs:
        k = []
        for r in range(12, -1, -1):
            if r != pairs[0] and rank_counts[r] > 0:
                k.append(r)
                if len(k) == 3: break
        return (1 << 24) | (pairs[0] << 16) | (k[0] << 12) | (k[1] << 8) | (k[2] << 4)

    # 0. High Card
    score = 0
    for i, r in enumerate(singles[:5]): score |= (r << (20 - i*4))
    return score

def run_simulation_with_full_stats():
    results_data = []
    base_deck = list(range(52))
    
    print(f"Starting River Simulation (5 Board Cards): {NUM_OUTER_ITERATIONS} scenarios.")
    print("-" * 60)
    
    start_total = time.time()
    
    for i in range(NUM_OUTER_ITERATIONS):
        # 1. Generate Scenario (Hero + 5 Board Cards)
        # We now need 7 unique cards total (2 Hole + 5 Board)
        scenario_cards = random.sample(base_deck, 7)
        hero_hand = scenario_cards[0:2]
        board_cards = scenario_cards[2:7] # All 5 cards are now known
        
        # Identify remaining deck for MC (Opponents only)
        used = set(scenario_cards)
        deck_remainder = [x for x in base_deck if x not in used]
        
        # OPTIMIZATION:
        # Since the board is complete, Hero's hand strength is static for this scenario.
        # We calculate it once here, rather than 500 times in the loop.
        hero_score = evaluate_hand_score_fast(hero_hand + board_cards)

        wins = 0
        draws = 0
        losses = 0
        
        # Cards needed per run: Only the opponents' hole cards (2 per opponent)
        cards_needed = NUM_OPPONENTS * 2
        
        for _ in range(NUM_MC_SIMULATIONS):
            # Sample opponent cards from the remainder
            opp_draws = random.sample(deck_remainder, cards_needed)
            
            # Evaluate Opponents
            best_opp_score = -1
            
            # Loop through opponents (step by 2 cards)
            for k in range(0, len(opp_draws), 2):
                op_hand = [opp_draws[k], opp_draws[k+1]]
                s = evaluate_hand_score_fast(op_hand + board_cards)
                if s > best_opp_score:
                    best_opp_score = s
            
            if hero_score > best_opp_score:
                wins += 1
            elif hero_score == best_opp_score:
                draws += 1
            else:
                losses += 1

        # Calculate Stats
        total = NUM_MC_SIMULATIONS
        p_win = (wins / total) * 100
        p_draw = (draws / total) * 100
        p_loss = (losses / total) * 100
        p_equity = ((wins + (0.5 * draws)) / total) * 100
        
        if p_equity > 0:
            p_ratio = p_win / p_equity
        else:
            p_ratio = 0.0
            
        results_data.append({
            'win': p_win,
            'draw': p_draw,
            'loss': p_loss,
            'equity': p_equity,
            'ratio': p_ratio
        })

        if (i+1) % 100 == 0:
            print(f"Scenario {i+1} completed.")

    print(f"\nDone in {time.time() - start_total:.2f} seconds.")
    return results_data

# --- Reporting Functions ---

def get_stats_pair(data_list):
    if not data_list: return 0.0, 0.0
    mean_val = statistics.mean(data_list)
    if len(data_list) > 1:
        std_val = statistics.stdev(data_list)
    else:
        std_val = 0.0
    return mean_val, std_val

def analyze_by_regions(data):
    regions = [
        (0, 20), (20, 40), (40, 60), (60, 80), (80, 100.1)
    ]
    
    print("\n" + "="*115)
    print(f"{'EQUITY REGION':<18} | {'N':<6} | {'WIN % (Mean ± SD)':<18} | {'DRAW % (Mean ± SD)':<18} | {'LOSS % (Mean ± SD)':<18} | {'RATIO (Mean ± SD)':<18}")
    print("="*115)

    for min_eq, max_eq in regions:
        region_data = [d for d in data if min_eq <= d['equity'] < max_eq]
        count = len(region_data)
        
        if count == 0:
            continue
            
        w_m, w_s = get_stats_pair([d['win'] for d in region_data])
        d_m, d_s = get_stats_pair([d['draw'] for d in region_data])
        l_m, l_s = get_stats_pair([d['loss'] for d in region_data])
        r_m, r_s = get_stats_pair([d['ratio'] for d in region_data])

        region_label = f"{min_eq}% - {max_eq if max_eq <= 100 else 100}%"
        
        print(f"{region_label:<18} | {count:<6} | {w_m:<5.1f} ± {w_s:<5.1f} | {d_m:<5.1f} ± {d_s:<5.1f} | {l_m:<5.1f} ± {l_s:<5.1f} | {r_m:<5.2f} ± {r_s:<5.2f}")

if __name__ == "__main__":
    results = run_simulation_with_full_stats()
    
    analyze_by_regions(results)
    
    # --- Global Statistics ---
    print("\n" + "="*60)
    print("GLOBAL STATISTICS (All Scenarios)")
    print(f"{'METRIC':<15} | {'MEAN':<10} | {'STD DEV':<10}")
    print("="*60)
    
    metrics = ['win', 'draw', 'loss', 'equity', 'ratio']
    
    if results:
        for metric in metrics:
            values = [d[metric] for d in results]
            m, s = get_stats_pair(values)
            
            if metric == 'ratio':
                print(f"{metric.upper():<15} | {m:<10.3f} | {s:<10.3f}")
            else:
                print(f"{metric.upper():<15} | {m:<10.2f} | {s:<10.2f}")
    else:
        print("No simulation data available.")