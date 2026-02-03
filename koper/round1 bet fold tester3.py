import random
import time
import matplotlib.pyplot as plt

# ==========================================
#              CONFIGURATION
# ==========================================

TOTAL_PLAYERS = 2
TOTAL_GAME_RUNS = 15000
HERO_SIMS = 400
OPP_SIMS = 200

OPP_THRESH_MIN = 0.38
OPP_THRESH_MAX = 0.48
ANTE = 0.347
TEST_THRESHOLDS = [x / 10000.0 for x in range(1000, 5000, 5)]

RANK_LOOKUP = tuple(i // 4 for i in range(52))
SUIT_LOOKUP = tuple(i % 4 for i in range(52))

# ==========================================
#              POKER LOGIC
# ==========================================

def evaluate_hand_score_fast(cards):
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
                k.append(r)
                if len(k) == 3: break
        return (1 << 24) | (pairs[0] << 16) | (k[0] << 12) | (k[1] << 8) | (k[2] << 4)

    score = 0
    for i, r in enumerate(singles[:5]): score |= (r << (20 - i*4))
    return score

# ==========================================
#              SIMULATION
# ==========================================

def calculate_equity(hand, community, num_players, sims):
    wins = 0.0
    used = set(hand + community)
    deck_list = [x for x in range(52) if x not in used]
    cards_to_draw = 2 + (num_players - 1) * 2
    
    for _ in range(sims):
        drawn = random.sample(deck_list, cards_to_draw)
        final_community = community + drawn[0:2]
        
        my_score = evaluate_hand_score_fast(hand + final_community)
        best_opp_score = -1
        
        opp_idx = 2
        for _ in range(num_players - 1):
            s = evaluate_hand_score_fast([drawn[opp_idx], drawn[opp_idx+1]] + final_community)
            if s > best_opp_score: best_opp_score = s
            opp_idx += 2
        
        if my_score > best_opp_score: wins += 1.0
        elif my_score == best_opp_score: wins += 0.5
            
    return wins / sims

def run_simulation():
    stats = {t: {'profit':0.0, 'bets':0, 'wins':0, 'folds':0} for t in TEST_THRESHOLDS}
    
    print(f"Running simulation ({TOTAL_GAME_RUNS} hands)...")
    start_time = time.time()
    
    full_deck = list(range(52))
    pot_from_antes = TOTAL_PLAYERS * ANTE
    range_total_players_minus_1 = range(TOTAL_PLAYERS - 1)

    for i in range(TOTAL_GAME_RUNS):
        deal_indices = random.sample(full_deck, 15)
        player_hand = deal_indices[0:2]
        flop = deal_indices[2:5]
        turn = deal_indices[5]
        river = deal_indices[6]
        final_community = flop + [turn, river]
        
        current_opp_threshold = random.uniform(OPP_THRESH_MIN, OPP_THRESH_MAX)
        my_equity = calculate_equity(player_hand, flop, TOTAL_PLAYERS, HERO_SIMS)
        
        active_opp_hands = []
        opp_card_idx = 7
        for _ in range_total_players_minus_1:
            o_hand = deal_indices[opp_card_idx : opp_card_idx+2]
            opp_card_idx += 2
            opp_eq = calculate_equity(o_hand, flop, TOTAL_PLAYERS, OPP_SIMS)
            if opp_eq >= current_opp_threshold:
                active_opp_hands.append(o_hand)
        
        profit = 0.0
        is_win = False
        
        if not active_opp_hands:
            revenue = 1.0 + pot_from_antes
            profit = revenue - 1.0 - ANTE
            is_win = True
        else:
            my_score = evaluate_hand_score_fast(player_hand + final_community)
            best_score = my_score
            winners_count = 1
            im_winning = True
            
            for oh in active_opp_hands:
                s = evaluate_hand_score_fast(oh + final_community)
                if s > best_score:
                    best_score = s
                    im_winning = False
                    winners_count = 1
                elif s == best_score:
                    winners_count += 1
            
            is_win = im_winning and (best_score == my_score)

            total_active = len(active_opp_hands) + 1
            total_pot = float(total_active) + pot_from_antes
            
            # Cap Logic: 4 * (Bet + Ante)
            my_contribution = 1.0 + ANTE
            max_win_per_person = my_contribution * 4.0
            
            max_total_payout = winners_count * max_win_per_person
            payout_real = min(total_pot, max_total_payout)
            excess = total_pot - payout_real
            refund = excess / total_active
            
            revenue = refund
            if is_win: revenue += (payout_real / winners_count)
            profit = revenue - 1.0 - ANTE

        for t in TEST_THRESHOLDS:
            if my_equity >= t:
                stats[t]['bets'] += 1
                stats[t]['profit'] += profit
                if is_win: stats[t]['wins'] += 1
            else:
                stats[t]['folds'] += 1
                stats[t]['profit'] -= ANTE

        if (i+1) % 5000 == 0:
            print(f"Simulated {i+1} hands...")

    print(f"Done in {time.time() - start_time:.2f}s")
    
    x_vals, y_vals = [], []
    best_t, max_p = -1, -float('inf')
    
    for t in TEST_THRESHOLDS:
        p = stats[t]['profit']
        x_vals.append(t)
        y_vals.append(p)
        if p > max_p:
            max_p = p
            best_t = t
            
    print("\n" + "="*40)
    print(f"BEST THRESHOLD: {best_t*100:.2f}%")
    print(f"Total Profit:   {max_p:.1f}")
    print("="*40)
    
    plt.figure(figsize=(10, 6))
    plt.plot(x_vals, y_vals, color='blue')
    plt.axvline(x=best_t, color='red', linestyle='--')
    plt.title("Profit vs Equity Threshold")
    plt.xlabel("Equity Threshold")
    plt.ylabel("Profit")
    plt.grid(True, alpha=0.3)
    plt.show()

if __name__ == "__main__":
    run_simulation()