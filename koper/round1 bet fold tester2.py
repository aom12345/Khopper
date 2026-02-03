import random
import time

# ==========================================
#        CONFIGURATION
# ==========================================

TOTAL_PLAYERS = 5       
TOTAL_GAME_RUNS = 2000     
EQUITY_SIMULATIONS = 400 

# Opponents fold if they have less than this equity
OPPONENT_THRESHOLD = 0.14 

# The fixed cost everyone pays every hand
ANTE = 0.347

# Testing thresholds for Hero (You)
TEST_THRESHOLDS = [x / 1000.0 for x in range(60, 180, 1)] 

# ==========================================
#          FAST POKER LOGIC
# ==========================================

RANK_LOOKUP = [i // 4 for i in range(52)]
SUIT_LOOKUP = [i % 4 for i in range(52)]

def evaluate_hand_score_fast(cards):
    """ Optimized bitwise evaluator. """
    rank_counts = [0] * 13
    suit_counts = [0] * 4
    rank_bits = 0 
    
    for c in cards:
        r = RANK_LOOKUP[c]
        s = SUIT_LOOKUP[c]
        rank_counts[r] += 1
        suit_counts[s] += 1
        rank_bits |= (1 << r)

    flush_suit = -1
    for s in range(4):
        if suit_counts[s] >= 5:
            flush_suit = s
            break

    straight_high = -1
    for r in range(8, -1, -1):
        if (rank_bits >> r) & 0x1F == 0x1F:
            straight_high = r + 4
            break
    if straight_high == -1 and (rank_bits & 0x100F) == 0x100F:
        straight_high = 3

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
            if r != quads[0] and rank_counts[r] > 0:
                kicker = r; break
        return (7 << 24) | (quads[0] << 16) | kicker

    if trips and (len(trips) >= 2 or pairs):
        major = trips[0]
        minor = trips[1] if len(trips) >= 2 else pairs[0]
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
                if len(k) == 3: 
                    break
        return (1 << 24) | (pairs[0] << 16) | (k[0] << 12) | (k[1] << 8) | (k[2] << 4)

    score = 0
    for i, r in enumerate(singles[:5]): score |= (r << (20 - i*4))
    return score

# ==========================================
#          SIMULATION ENGINE
# ==========================================

def calculate_equity(player_hand, flop, num_players, simulations=500):
    wins, draws = 0, 0
    used_cards = set(player_hand + flop)
    available_deck = [x for x in range(52) if x not in used_cards]
    cards_needed = (num_players - 1) * 2 + 2 
    
    for _ in range(simulations):
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

def run_multi_threshold_simulation():
    # Stats structure
    stats_map = {t: {'profit':0, 'bets':0, 'wins':0, 'folds':0} for t in TEST_THRESHOLDS}
    
    print(f"--- Poker Sim (Capped Pot + Antes) ---")
    print(f"Players: {TOTAL_PLAYERS}")
    print(f"Ante: {ANTE:.3f} units (Paid by everyone)")
    print(f"Cap Rule: Max 4.0 units per winner.")
    
    start_time = time.time()
    full_deck = list(range(52))
    
    # Pre-calculate Pot Base (Antes)
    POT_FROM_ANTES = TOTAL_PLAYERS * ANTE
    
    for i in range(TOTAL_GAME_RUNS):
        random.shuffle(full_deck)
        player_hand = full_deck[0:2]
        flop = full_deck[2:5]
        turn = full_deck[5]
        river = full_deck[6]
        community = flop + [turn, river]
        
        # 1. Calculate MY Equity
        my_equity = calculate_equity(player_hand, flop, TOTAL_PLAYERS, EQUITY_SIMULATIONS)
        
        # 2. Determine Active Opponents
        active_opp_hands = []
        for j in range(TOTAL_PLAYERS - 1):
            idx = 7 + (j * 2)
            o_hand = full_deck[idx : idx+2]
            opp_eq = calculate_equity(o_hand, flop, TOTAL_PLAYERS, 100)
            if opp_eq >= OPPONENT_THRESHOLD:
                active_opp_hands.append(o_hand)

        # 3. Calculate Outcome if I BET
        hypothetical_profit = 0.0
        is_win = False
        
        if len(active_opp_hands) == 0:
            # UNCONTESTED
            # I win the Blinds (1.5) + All Antes (POT_FROM_ANTES)
            # My cost was 1.0 (Bet) + ANTE
            # I get my Bet and my Ante back, plus everyone else's ante and blinds
            revenue = 1.0 + 1.5 + POT_FROM_ANTES 
            hypothetical_profit = revenue - 1.0 - ANTE
            is_win = True
        else:
            # SHOWDOWN
            my_score = evaluate_hand_score_fast(player_hand + community)
            
            all_scores = [my_score]
            for oh in active_opp_hands:
                all_scores.append(evaluate_hand_score_fast(oh + community))
            
            best_score = max(all_scores)
            num_winners = all_scores.count(best_score)
            i_am_winner = (my_score == best_score)
            if i_am_winner: is_win = True

            # --- POT CALCULATION ---
            total_active_players = len(active_opp_hands) + 1
            
            # The pot is composed of Bets + Antes
            pot_from_bets = float(total_active_players)
            total_pot = pot_from_bets + POT_FROM_ANTES
            
            # Cap Logic: Max 4.0 units per winner
            max_winnable = num_winners * 4.0
            
            # Payout
            payout_to_winners = min(total_pot, max_winnable)
            excess = total_pot - payout_to_winners
            
            # Excess is shared by active players
            refund_per_player = excess / total_active_players
            
            my_revenue = refund_per_player
            if i_am_winner:
                my_revenue += (payout_to_winners / num_winners)
            
            # Net Profit = Revenue - Bet - Ante
            hypothetical_profit = my_revenue - 1.0 - ANTE

        # 4. Apply result to thresholds
        for t in TEST_THRESHOLDS:
            if my_equity >= t:
                # PLAY
                stats_map[t]['bets'] += 1
                stats_map[t]['profit'] += hypothetical_profit
                if is_win:
                    stats_map[t]['wins'] += 1
            else:
                # FOLD (I still pay the Ante)
                stats_map[t]['folds'] += 1
                stats_map[t]['profit'] -= ANTE

        if (i+1) % 100 == 0:
            print(f"Simulated {i+1} hands...")

    elapsed = time.time() - start_time
    print(f"\nSimulation Complete in {elapsed:.2f}s")
    return stats_map

# ==========================================
#               RESULTS
# ==========================================

if __name__ == "__main__":
    results = run_multi_threshold_simulation()
    
    print("\n" + "="*60)
    print(f"  OPTIMIZATION REPORT (Players: {TOTAL_PLAYERS})")
    print("="*60)
    print(f"{'My Threshold':<14} | {'Net Profit':<12} | {'Win Rate':<10} | {'Action Breakdown'}")
    print("-" * 60)
    
    best_t = -1
    max_p = -float('inf')
    
    for t in TEST_THRESHOLDS:
        r = results[t]
        if r['profit'] > max_p:
            max_p = r['profit']
            best_t = t
            
        if int(t*100) % 5 == 0 or t == best_t:
             win_rate = (r['wins']/r['bets']*100) if r['bets'] > 0 else 0
             print(f"{t*100:5.0f}% Equity   | {r['profit']:8.1f}     | {win_rate:6.1f}%    | B:{r['bets']} F:{r['folds']}")

    print("="*60)
    print(f"BEST THRESHOLD: {best_t*100:.1f}%")
    print(f"Total Profit:   {max_p:.1f}")
    print("="*60)