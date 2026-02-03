import random
import time

# ==========================================
#        CONFIGURATION
# ==========================================

TOTAL_PLAYERS = 5
TOTAL_GAME_RUNS = 2000     # Increased since it handles multiple thresholds efficiently
EQUITY_SIMULATIONS = 500   # Monte Carlo samples per hand

# We will test every threshold from 0.00 to 1.00 in steps of 0.02
# You can customize this range
TEST_THRESHOLDS = [x / 100.0 for x in range(0, 101, 2)] 

# ==========================================
#          FAST POKER LOGIC (BITWISE)
# ==========================================

# Pre-computed lookups
RANK_LOOKUP = [i // 4 for i in range(52)]
SUIT_LOOKUP = [i % 4 for i in range(52)]

def get_deck():
    return list(range(52))

def evaluate_hand_score_fast(cards):
    """
    Optimized bitwise evaluator. 
    Returns integer: (HandType << 24) | TieBreakers
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

    # Flush Check
    flush_suit = -1
    for s in range(4):
        if suit_counts[s] >= 5:
            flush_suit = s
            break

    # Straight Check
    straight_high = -1
    for r in range(8, -1, -1):
        if (rank_bits >> r) & 0x1F == 0x1F:
            straight_high = r + 4
            break
    if straight_high == -1 and (rank_bits & 0x100F) == 0x100F:
        straight_high = 3

    # Straight Flush Check
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

    # Count Patterns (Quads, Full House, etc)
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
            if r != quads[0] and rank_counts[r] > 0:
                kicker = r
                break
        return (7 << 24) | (quads[0] << 16) | kicker

    if trips and (len(trips) >= 2 or pairs):
        major = trips[0]
        minor = trips[1] if len(trips) >= 2 else pairs[0]
        return (6 << 24) | (major << 16) | minor

    if flush_suit != -1:
        fl_ranks = [RANK_LOOKUP[c] for c in cards if SUIT_LOOKUP[c] == flush_suit]
        fl_ranks.sort(reverse=True)
        score = (5 << 24)
        for i, r in enumerate(fl_ranks[:5]):
            score |= (r << (20 - i*4))
        return score

    if straight_high != -1:
        return (4 << 24) | straight_high

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
                k.append(r)
                if len(k) == 3: break
        return (1 << 24) | (pairs[0] << 16) | (k[0] << 12) | (k[1] << 8) | (k[2] << 4)

    score = 0
    for i, r in enumerate(singles[:5]):
        score |= (r << (20 - i*4))
    return score

# ==========================================
#          SIMULATION ENGINE
# ==========================================

def calculate_equity(player_hand, flop, num_players, simulations=500):
    wins = 0
    draws = 0
    
    used_cards = set(player_hand + flop)
    available_deck = [x for x in range(52) if x not in used_cards]
    cards_needed = (num_players - 1) * 2 + 2 
    
    for _ in range(simulations):
        deal = random.sample(available_deck, cards_needed)
        turn = deal[0]
        river = deal[1]
        community = flop + [turn, river]
        
        my_score = evaluate_hand_score_fast(player_hand + community)
        
        best_opp = -1
        # Check opponents (chunks of 2)
        for i in range(2, len(deal), 2):
            op_score = evaluate_hand_score_fast([deal[i], deal[i+1]] + community)
            if op_score > best_opp:
                best_opp = op_score
                
        if my_score > best_opp:
            wins += 1
        elif my_score == best_opp:
            draws += 1
            
    return (wins + 0.5 * draws) / simulations

def run_multi_threshold_simulation():
    # Initialize stats for ALL thresholds
    # Format: {threshold: {'wins': 0, 'losses': 0, 'draws': 0, 'folds': 0, 'bets': 0}}
    stats_map = {t: {'wins':0, 'losses':0, 'draws':0, 'folds':0, 'bets':0} for t in TEST_THRESHOLDS}
    
    print(f"--- Running Multi-Threshold Optimization ---")
    print(f"Total Games: {TOTAL_GAME_RUNS}")
    print(f"Testing {len(TEST_THRESHOLDS)} thresholds simultaneously (0.0 to 1.0)")
    
    start_time = time.time()
    full_deck = list(range(52))
    
    for i in range(TOTAL_GAME_RUNS):
        # 1. Setup & Deal
        random.shuffle(full_deck)
        player_hand = full_deck[0:2]
        flop = full_deck[2:5]
        
        # 2. Calculate Equity ONCE
        equity = calculate_equity(player_hand, flop, TOTAL_PLAYERS, EQUITY_SIMULATIONS)
        
        # 3. Play the hand out to determine the "Potential Result"
        # We need to know if this hand WOULD have won if played, 
        # so we can credit the thresholds that decided to play it.
        turn = full_deck[5]
        river = full_deck[6]
        community = flop + [turn, river]
        
        opp_hands = []
        for j in range(TOTAL_PLAYERS - 1):
            idx = 7 + (j * 2)
            opp_hands.append(full_deck[idx : idx+2])
            
        my_score = evaluate_hand_score_fast(player_hand + community)
        best_opp_score = -1
        for oh in opp_hands:
            s = evaluate_hand_score_fast(oh + community)
            if s > best_opp_score:
                best_opp_score = s
        
        # 4. Update Stats for EVERY threshold based on the SAME game result
        for t in TEST_THRESHOLDS:
            if equity >= t:
                # This threshold says "BET"
                stats_map[t]['bets'] += 1
                if my_score > best_opp_score:
                    stats_map[t]['wins'] += 1
                elif my_score == best_opp_score:
                    stats_map[t]['draws'] += 1
                else:
                    stats_map[t]['losses'] += 1
            else:
                # This threshold says "FOLD"
                stats_map[t]['folds'] += 1

        if (i+1) % 100 == 0:
            print(f"Simulated {i+1} hands...")

    elapsed = time.time() - start_time
    print(f"\nSimulation Complete in {elapsed:.2f}s")
    return stats_map

# ==========================================
#               RESULTS ANALYSIS
# ==========================================

if __name__ == "__main__":
    results = run_multi_threshold_simulation()
    
    print("\n" + "="*50)
    print(f"  OPTIMIZATION REPORT ({TOTAL_PLAYERS} Players)")
    print("="*50)
    print(f"{'Threshold':<10} | {'Win Rate':<10} | {'Profit Score':<12} | {'Action Breakdown'}")
    print("-" * 50)
    
    best_threshold = -1
    max_profit = -float('inf')
    
    # We define Profit Score as: (Wins * (N-1)) - (Losses * 1)
    # This assumes a pot where everyone bets 1 unit. 
    # E.g. 5 players, you win 4 units (opponents' bets) or lose 1 unit (your bet).
    reward_mult = min(TOTAL_PLAYERS - 1,3)
    
    for t in TEST_THRESHOLDS:
        r = results[t]
        bets = r['bets']
        
        win_rate = 0
        if bets > 0:
            win_rate = (r['wins'] / bets) * 100
            
        # Metric: Profit Score
        profit = (r['wins'] * reward_mult) - r['losses'] - (r['folds']//2.875)
        
        if profit > max_profit:
            max_profit = profit
            best_threshold = t
            
        # Only print rows that are interesting (skip 0% or very sparse ones to save space)
        # Printing every 5th threshold or if it's the peak
        if int(t*100) % 10 == 0 or t == best_threshold:
            print(f"{t*100:5.0f}%     | {win_rate:6.1f}%    | {profit:6d}       | B:{bets} (W:{r['wins']} L:{r['losses']} F:{r['folds']})")

    print("="*50)
    print(f"RECOMMENDED THRESHOLD: {best_threshold*100:.1f}% Equity")
    print(f"Max Profit Score: {max_profit}")
    print("="*50)