import random
import itertools
import statistics
from collections import Counter

# --- Configuration ---
NUM_OUTER_ITERATIONS = 3000 
NUM_MC_SIMULATIONS = 500       
NUM_OPPONENTS = 1            

# --- Card & Evaluation Logic ---
RANK_MAP = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
SUITS = ['s', 'h', 'd', 'c']

class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
    
    def __repr__(self):
        r_rev = {v: k for k, v in RANK_MAP.items()}
        return f"{r_rev[self.rank]}{self.suit}"

def get_deck():
    deck = []
    for r_str, r_val in RANK_MAP.items():
        for s in SUITS:
            deck.append(Card(r_val, s))
    return deck

def evaluate_5_card_hand(cards):
    """Returns (score_category, tie_breakers). Higher is better."""
    ranks = sorted([c.rank for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    rank_counts = Counter(ranks)
    most_common = rank_counts.most_common()
    
    is_flush = len(set(suits)) == 1
    
    unique_ranks = sorted(list(set(ranks)), reverse=True)
    is_straight = False
    if len(unique_ranks) == 5:
        if unique_ranks[0] - unique_ranks[4] == 4:
            is_straight = True
        elif unique_ranks == [14, 5, 4, 3, 2]: 
            is_straight = True
            ranks = [5, 4, 3, 2, 1]

    if is_flush and is_straight: return (8, ranks)
    if most_common[0][1] == 4: return (7, most_common[0][0], most_common[1][0])
    if most_common[0][1] == 3 and most_common[1][1] == 2: return (6, most_common[0][0], most_common[1][0])
    if is_flush: return (5, ranks)
    if is_straight: return (4, ranks)
    if most_common[0][1] == 3:
        kickers = sorted([x for x in ranks if x != most_common[0][0]], reverse=True)
        return (3, most_common[0][0], kickers)
    if most_common[0][1] == 2 and most_common[1][1] == 2:
        pairs = sorted([most_common[0][0], most_common[1][0]], reverse=True)
        kicker = [x for x in ranks if x not in pairs][0]
        return (2, pairs[0], pairs[1], kicker)
    if most_common[0][1] == 2:
        pair_rank = most_common[0][0]
        kickers = sorted([x for x in ranks if x != pair_rank], reverse=True)
        return (1, pair_rank, kickers)
    return (0, ranks)

def get_best_hand_rank(hole_cards, board):
    all_7 = hole_cards + board
    best_score = (-1, [])
    for combo in itertools.combinations(all_7, 5):
        score = evaluate_5_card_hand(combo)
        if score > best_score:
            best_score = score
    return best_score

# --- Main Simulation Loop ---

def run_randomized_simulation():
    # Store dictionaries containing all stats for each scenario
    results_data = []

    print(f"Starting Randomized Simulation: {NUM_OUTER_ITERATIONS} scenarios.")
    print("-" * 60)

    for i in range(NUM_OUTER_ITERATIONS):
        full_deck = get_deck()
        random.shuffle(full_deck)
        
        hero_hand = [full_deck.pop(), full_deck.pop()]
        flop = [full_deck.pop(), full_deck.pop(), full_deck.pop()]
        
        scenario_deck_snapshot = list(full_deck)

        wins = 0
        draws = 0
        losses = 0

        for _ in range(NUM_MC_SIMULATIONS):
            deck = list(scenario_deck_snapshot)
            random.shuffle(deck)

            turn = deck.pop()
            river = deck.pop()
            board = flop + [turn, river]

            opponents_hands = []
            for _ in range(NUM_OPPONENTS):
                op_hand = [deck.pop(), deck.pop()]
                opponents_hands.append(op_hand)

            hero_score = get_best_hand_rank(hero_hand, board)
            
            op_best_score = (-1, [])
            for op_h in opponents_hands:
                s = get_best_hand_rank(op_h, board)
                if s > op_best_score:
                    op_best_score = s
            
            if hero_score > op_best_score:
                wins += 1
            elif hero_score == op_best_score:
                draws += 1
            else:
                losses += 1
        
        # Calculate Stats
        p_win = (wins / NUM_MC_SIMULATIONS) * 100
        p_draw = (draws / NUM_MC_SIMULATIONS) * 100
        p_loss = (losses / NUM_MC_SIMULATIONS) * 100
        p_equity = ((wins + (0.5 * draws)) / NUM_MC_SIMULATIONS) * 100
        
        if p_equity > 0:
            p_ratio = p_win / p_equity
        else:
            p_ratio = 0.0

        # Store single scenario result
        results_data.append({
            'win': p_win,
            'draw': p_draw,
            'loss': p_loss,
            'equity': p_equity,
            'ratio': p_ratio
        })

        if (i+1) % 100 == 0:
            print(f"Scenario {i+1} completed.")

    return results_data

def get_stats_pair(data_list):
    """Helper to return (mean, stdev) for a list of numbers."""
    if not data_list:
        return 0.0, 0.0
    
    mean_val = statistics.mean(data_list)
    if len(data_list) > 1:
        std_val = statistics.stdev(data_list)
    else:
        std_val = 0.0
    return mean_val, std_val

def analyze_by_regions(data):
    # Define 5 regions (min, max)
    regions = [
        (0, 20),
        (20, 40),
        (40, 60),
        (60, 80),
        (80, 100.1) # 100.1 to include 100 inclusive
    ]
    
    # Header Format
    # R: Region, N: Count
    # W: Win, D: Draw, L: Loss, Ratio: W/E Ratio
    # Format per column: "Mean ± SD"
    
    print("\n" + "="*115)
    print(f"{'EQUITY REGION':<18} | {'N':<6} | {'WIN % (Mean ± SD)':<18} | {'DRAW % (Mean ± SD)':<18} | {'LOSS % (Mean ± SD)':<18} | {'RATIO (Mean ± SD)':<18}")
    print("="*115)

    for min_eq, max_eq in regions:
        # Filter data for this region
        region_data = [d for d in data if min_eq <= d['equity'] < max_eq]
        count = len(region_data)
        
        # Calculate stats pairs (mean, stdev) for each metric
        w_m, w_s = get_stats_pair([d['win'] for d in region_data])
        d_m, d_s = get_stats_pair([d['draw'] for d in region_data])
        l_m, l_s = get_stats_pair([d['loss'] for d in region_data])
        r_m, r_s = get_stats_pair([d['ratio'] for d in region_data])

        region_label = f"{min_eq}% - {max_eq if max_eq <= 100 else 100}%"
        
        # Format strings
        s_win = f"{w_m:.1f} ± {w_s:.1f}"
        s_draw = f"{d_m:.1f} ± {d_s:.1f}"
        s_loss = f"{l_m:.1f} ± {l_s:.1f}"
        s_ratio = f"{r_m:.2f} ± {r_s:.2f}"
        
        print(f"{region_label:<18} | {count:<6} | {s_win:<18} | {s_draw:<18} | {s_loss:<18} | {s_ratio:<18}")

if __name__ == "__main__":
    results = run_randomized_simulation()
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