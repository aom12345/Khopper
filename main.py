"""
main.py

This file orchestrates the entire tournament.
It handles:
    1. Importing core components (constants, PlayerState, helper functions) from engine_core.py.
    2. Importing strategies (participant strategies or dummy fallbacks) from dummy_strategies.py.
    3. The main play_match() loop that runs the games, manages state, and calls strategy methods.
"""

# Import necessary components from the core engine file
# This gives us access to configuration, classes, and poker math functions.
from engine_core import (
    NUM_GAMES, STARTING_STACK, BUY_IN, PLAYER_NAMES, PlayerState,
    create_deck, calculate_multiplayer_equity, evaluate_hand,
)

# Import the pre-loaded strategy objects from the strategy file.
# These variables (strategyA, strategyB, etc.) are instances of the strategy classes.
from dummy_strategies import (
    strategyA, strategyB, strategyC, strategyD, strategyE
)

# Import standard library components needed for the game loop
import random
import copy
import sys
import itertools
import contextlib
import pandas as pd

# ============================================================
# 1. STRATEGY INSTANCES & GLOBAL CACHE
# ============================================================
# List of strategy objects that will play in each game.
PLAYERS = [strategyA, strategyB, strategyC, strategyD, strategyE]


# Global cache to store equity calculations across matches
EQUITY_CACHE = {}

def get_cached_equity(game_idx, seat_idx, hole_cards, community, num_players, round_key):
    """
    Checks if equity has been calculated for this specific game/seat/player-count.
    """
    cache_key = (game_idx, seat_idx, num_players, round_key)
    if cache_key not in EQUITY_CACHE:
        EQUITY_CACHE[cache_key] = calculate_multiplayer_equity(hole_cards, community, num_players)
    return EQUITY_CACHE[cache_key]


# ============================================================
# 2. MAIN GAME LOOP: play_match()
# ============================================================

def play_match(match_num, match_strategies, tournament_cards):
    """
    Runs a single match (50 games) with a specific seating arrangement.
    """
    # Create PlayerState objects using the rotated strategies.
    # Note: PLAYER_NAMES stays static, but the strategies assigned to them change.
    players = [PlayerState(PLAYER_NAMES[i], match_strategies[i], i) for i in range(len(PLAYER_NAMES))]
    
    # CRITICAL SETUP: Assign each strategy its index (0-4) for internal reference.
    for p in players:
        p.strategy.my_index = p.index
        
    match_history = []
    no_of_wins = [0] * len(players)

    # --- Start Game Loop ---
    for game_num in range(1, NUM_GAMES + 1):
        print(f"\n--- Match {match_num} | Game {game_num} ---")

        for p in players:
            p.strategy.initialize_game(match_history, game_num)
        






        # ------------------------------------------------------------
        # ROUND 0: Setup and Buy-in
        # ------------------------------------------------------------
        print("\nRound 0 starting: Buy-ins and Dealing")
        pot = 0
        
        # USE PRE-GENERATED CARDS FOR THIS GAME
        game_data = tournament_cards[game_num - 1]
        pre_dealt_hands = game_data['hands']
        community_cards = game_data['community']
        
        active_players_indices = []

        for p in players:
            p.reset_round()
            if p.is_lost_match:
                continue

            if p.stack < BUY_IN:
                print(f"{p.name} eliminated! Stack ({p.stack:.2f}) < {BUY_IN}.")
                pot += p.stack 
                p.stack = 0
                p.is_lost_match = True
            else:
                p.stack -= BUY_IN
                pot += BUY_IN
                # Assign the pre-generated hand for this seat
                p.hole_cards = pre_dealt_hands[p.index]
                print(f"{p.hole_cards} dealt to {p.strategy.__class__.__name__}")
                active_players_indices.append(p.index)

        print(f"The community cards are: {community_cards}")

        if len(active_players_indices) < 2:
            print("Not enough players to continue match.")
            break







        # ------------------------------------------------------------
        # ROUND 1: FLOP BETTING (3 community cards shown)
        # ------------------------------------------------------------
        visible_community = community_cards[:3]
        print("\nRound 1 starting: Flop Betting")
        print(f"Visible Community Cards for Round 1 (Flop): {visible_community}")
        
        round1_active_indices = []
        current_stacks = [p.stack for p in players] 

        for idx in active_players_indices:
            p = players[idx]
            if p.stack < 100:
                 print(f"{p.strategy.__class__.__name__} eliminated! Stack ({p.stack:.2f}) < 100.")
                 pot += p.stack
                 p.stack = 0
                 p.is_lost_match = True
            else:
                 round1_active_indices.append(idx)

        r1_bets = {idx: 0 for idx in range(len(players))}

        pot_before_round1 = pot

        for idx in round1_active_indices:
            p = players[idx]

            # CACHED EQUITY CALL
            win_prob = get_cached_equity(game_num, p.index, p.hole_cards, visible_community, len(round1_active_indices), "flop")

            print(f"Equity: {win_prob*100:.2f}%, {p.strategy.__class__.__name__}", end=' ')
            action, val = p.strategy.round1(p.hole_cards, visible_community, current_stacks, pot_before_round1, win_prob)

            if action == "fold":
                p.has_folded = True
                print("chose to fold.")
            else:
                price = max(100.0, min(300.0, float(val)))
                price = min(price, p.stack)
                p.current_bet_r1 = price
                r1_bets[idx] = price
                p.stack -= price
                pot += price
                print(f"chose to bet ${price:.2f}.")
            p.round_equities.append(win_prob)

        round1_post_fold_indices = [i for i in round1_active_indices if not players[i].has_folded]
        

        # Handling edge case: all players folded
        if not round1_post_fold_indices:
            print("All players folded! Pot redistributes.")
            for p in round1_active_indices:
                players[p].stack += pot / len(round1_active_indices)
                number_of_wins = 1 / len(round1_active_indices)
                no_of_wins[players[p].index] += number_of_wins
                print(f"{players[p].strategy.__class__.__name__} receives ${pot / len(round1_active_indices):.2f}")
            print()

            game_history = {}
            for p in players:
                game_history[p.index] = {
                    "hole_cards": p.hole_cards,
                    "final_score": 7463, 
                    "folded": p.has_folded,
                    "r1_bets": 0,
                    "r2_bets": 0,
                    "final_bet": 0, 
                    "equities": p.round_equities,
                    "stack": p.stack
                }
            game_history["community_cards"] = community_cards[:3]
            game_history["pot_final"] = pot
            match_history.append(game_history)
            continue


        # Handling edge case: only one player remains after folds
        if len(round1_post_fold_indices) == 1:
            winner_idx = round1_post_fold_indices[0]
            winner = players[winner_idx]
            winner.stack += pot
            no_of_wins[winner.index] += 1
            
            print("\n*** EARLY WINNER (Fold Equity) ***")
            print(f"{winner.strategy.__class__.__name__} wins by fold! Pot: ${pot:.2f}. Payout: ${pot:.2f}\n")

            game_history = {}
            for p in players:
                game_history[p.index] = {
                    "hole_cards": p.hole_cards,
                    "final_score": 7463, 
                    "folded": p.has_folded,
                    "r1_bets": r1_bets[p.index],
                    "r2_bets": 0,
                    "final_bet": 0,
                    "equities": p.round_equities,
                    "stack": p.stack
                }
            game_history["community_cards"] = community_cards[:3]
            game_history["pot_final"] = pot
            
            match_history.append(game_history)
            continue







        # ------------------------------------------------------------
        # ROUND 2: TURN BETTING (4 community cards visible)
        # ------------------------------------------------------------
        visible_community = community_cards[:4]
        print("\nRound 2 starting: Turn Betting")
        
        round2_active_indices = round1_post_fold_indices
        r2_bets = {idx: 0 for idx in range(len(players))}
        num_r2_players = len(round2_active_indices)
        
        pot_before_round2 = pot
        current_stacks = [p.stack for p in players]

        if num_r2_players > 0:
            for idx in round2_active_indices:
                p = players[idx]
                win_prob = get_cached_equity(game_num, p.index, p.hole_cards, visible_community, num_r2_players, "turn")
                val = p.strategy.round2(p.hole_cards, visible_community, r1_bets, current_stacks, pot_before_round2, win_prob)

                min_p = p.current_bet_r1 * 0.5
                max_p = p.current_bet_r1 * 1.5
                price = max(min_p, min(max_p, float(val)))
                price = min(price, p.stack)

                print(f"Equity: {win_prob*100:.2f}%, {p.strategy.__class__.__name__} bet {price:.2f} in round 2")
                p.current_bet_r2 = price
                r2_bets[idx] = price
                p.stack -= price
                pot += price
                p.round_equities.append(win_prob)







        # ------------------------------------------------------------
        # ROUND 3: RIVER BETTING (all 5 community cards visible)
        # ------------------------------------------------------------
        visible_community = community_cards
        print("\nRound 3 starting: River Betting")
        
        num_r3_players = len(round2_active_indices)
        pot_before_round3 = pot
        current_stacks = [p.stack for p in players]

        if num_r3_players > 0:
            for idx in round2_active_indices:
                p = players[idx]
                win_prob = get_cached_equity(game_num, p.index, p.hole_cards, visible_community, num_r3_players, "river")
                val = p.strategy.round3(p.hole_cards, visible_community, r1_bets, r2_bets, current_stacks, pot_before_round3, win_prob)

                min_p = p.current_bet_r2 * 0.75
                max_p = p.current_bet_r2 * 1.25
                price = max(min_p, min(max_p, float(val)))
                price = min(price, p.stack)

                print(f"Equity: {win_prob*100:.2f}%, {p.strategy.__class__.__name__} bet {price:.2f} in round 3")
                p.final_round_bet = price
                p.stack -= price
                pot += price
                p.round_equities.append(win_prob)







        # ------------------------------------------------------------
        # 3. SHOWDOWN & POT ALLOCATION
        # ------------------------------------------------------------
        best_score = 7463 
        winners = []
        game_history = {} 

        for idx in active_players_indices:
            p = players[idx]
            score = 0
            if not p.has_folded:
                score = evaluate_hand(p.hole_cards, community_cards)
                p.hand_score = score
                if score < best_score:
                    best_score = score
                    winners = [p]
                elif score == best_score:
                    winners.append(p)
            
            game_history[p.index] = {
                "hole_cards": p.hole_cards,
                "final_score": score,
                "folded": p.has_folded,
                "r1_bets": r1_bets[p.index],
                "r2_bets": r2_bets[p.index],
                "final_bet": p.final_round_bet,
                "equities": p.round_equities,
                "stack": p.stack
            }
            
        if winners:
            num_winners = len(winners)
            winning_pot_share_max = pot / num_winners
            total_win = 0
            print("\n*** SHOWDOWN RESULTS ***")
            if num_winners > 1:
                print(f"Total number of winners: {num_winners}")
            for winner in winners:
                no_of_wins[winner.index] += 1 / num_winners
                winning_cap = 4 * (BUY_IN + winner.current_bet_r1 + winner.current_bet_r2 + winner.final_round_bet)
                actual_win_for_winner = min(winning_cap, winning_pot_share_max)
                winner.stack += actual_win_for_winner
                total_win += actual_win_for_winner
                print(f"{winner.strategy.__class__.__name__} won ${actual_win_for_winner:.2f}. Winning Cap was ${winning_cap:.2f}. Pot was ${pot:.2f}")
            for p in players:
                print(f"{p.strategy.__class__.__name__} final stack: ${p.stack:.2f}")
            print()

            remaining_pot = pot - total_win
            game_history["community_cards"] = community_cards
            game_history["pot_final"] = pot
            match_history.append(game_history)
            
            if remaining_pot > 0:
                print(f"Distributing remaining pot ${remaining_pot:.2f} among {len(round2_active_indices)} active players.")
                recipients = [players[i] for i in round2_active_indices]
                if recipients:
                    share = remaining_pot / len(recipients)
                    for p in recipients: p.stack += share



    # FIXED: Return summary dict with stacks and wins for leaderboard
    results_summary = {}
    for p in players:
        results_summary[p.strategy] = {
            "stack": p.stack,
            "wins": no_of_wins[p.index]
        }
    return results_summary


# ========================================================
# 4. TOURNAMENT ORCHESTRATION
# ========================================================

if __name__ == "__main__":
        
    # 1. Pre-generate decks for all 50 games (removes luck variance)
    TOURNAMENT_CARDS = []
    for _ in range(NUM_GAMES):
        deck = create_deck()
        random.shuffle(deck)
        TOURNAMENT_CARDS.append({
            'hands': [[deck.pop(), deck.pop()] for _ in range(5)],
            'community': [deck.pop() for _ in range(5)]
        })
    
    # Track cumulative data across all 5 rotations
    cumulative_data = {strat: {"profit": 0.0, "wins": 0.0} for strat in PLAYERS}

    print("\n" + "="*65)
    print("TOURNAMENT START: 5 MATCHES FORMAT")
    print("="*65)

    # Initialize the log file
    with open("all_games.txt", "w") as f:
        f.write("TOURNAMENT LOG\n" + "="*20 + "\n")

    for m_idx in range(5):
        # Rotate strategies: ensures every player plays every 'seat' (0-4)
        rotated_strategies = PLAYERS[m_idx:] + PLAYERS[:m_idx]
        match_num = m_idx + 1
        
        print(f"\n[!] Running Match {match_num}/5 (Rotating Seats)...", end=" ", flush=True)
        
        # 2. Redirect game details to text file
        with open("all_games.txt", "a") as f:
            with contextlib.redirect_stdout(f):
                match_results = play_match(match_num, rotated_strategies, TOURNAMENT_CARDS)
        
        print("COMPLETE.")

        # 3. Process Match Results for DataFrame
        match_table_data = []
        for strat, data in match_results.items():
            profit = data["stack"] - STARTING_STACK
            cumulative_data[strat]["profit"] += profit
            cumulative_data[strat]["wins"] += data["wins"]
            
            match_table_data.append({
                "Strategy": strat.__class__.__name__,
                "Wins": data["wins"],
                "Final Stack": round(data["stack"], 2),
                "Net Profit": round(profit, 2)
            })

        # Display Match Table
        df_match = pd.DataFrame(match_table_data)
        df_match = df_match.sort_values(by="Net Profit", ascending=False).reset_index(drop=True)
        
        print(f"\n--- MATCH {match_num} SUMMARY ---\n")
        print(df_match.to_string(index=False))
        print("-" * 65)

    # ------------------------------------------------------------
    # 4. FINAL GLOBAL STANDINGS
    # ------------------------------------------------------------
    print("\n" + "🏆 "*15)
    print("FINAL STANDINGS (All 5 Matches Combined)")
    print("🏆 "*15 + "\n")
    
    final_list = []
    for strat, totals in cumulative_data.items():
        final_list.append({
            "Strategy": strat.__class__.__name__,
            "Total Wins": totals["wins"],
            "Total Profit": round(totals["profit"], 2)
        })
    
    df_final = pd.DataFrame(final_list)
    df_final = df_final.sort_values(by="Total Profit", ascending=False).reset_index(drop=True)
    
    # Add a rank column for clarity
    df_final.index = df_final.index + 1
    df_final.index.name = "Rank"
    
    print(df_final)
    print(f"\nDetailed play-by-play saved to: all_games.txt\n")
    print("Note: Please go through main.py and dummy_strategies.py to understand the tournament structure and strategy implementations.")