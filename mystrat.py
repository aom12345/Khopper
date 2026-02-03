"""
Final Optimized Strategy for Team 268 (No Bluff Version)
1. HYBRID (Dynamic): Scales 110 -> 180 based on equity.
2. CONFIDENT (Fixed): 204 (The Silencer).
3. AGGRESSIVE (Fixed): 235 (Safe Max).
NO IMPORTS USED.
"""

class team268:
    def __init__(self):
        self.my_index = -1
        self.mode = "HYBRID" 
        
        # --- CONFIGURATION ---
        
        # 1. HARD FOLD THRESHOLDS
        self.FOLD_THRESHOLDS = {
            5: 0.1450, 
            4: 0.2030, 
            3: 0.2555,
            2: 0.3565
        }
        
        # 2. HYBRID BET LIMITS (The Ramp)
        # We scale from Probe (110) up to just below Confident (180).
        self.HYBRID_BET_RANGE = (110, 180)

    def initialize_game(self, match_history, current_game_num):
        self.mode = "HYBRID"

    def _get_active_player_count(self, stacks):
        return sum(1 for s in stacks if s > 1.0)

    def _calculate_ramp_bet(self, equity, min_eq, max_eq):
        """
        Scales bet between 110 and 180 based on equity position.
        Uses inverted 1/sqrt(x) curve for smooth acceleration.
        Implemented without math import using ** 0.5.
        """
        min_bet, max_bet = self.HYBRID_BET_RANGE
        
        # Clamp equity to the hybrid band
        if equity < min_eq: equity = min_eq
        if equity > max_eq: equity = max_eq
        
        # Inverted 1/sqrt(x) Logic
        # 1/sqrt(x) decreases as x increases.
        # We map High Value (Low Eq) -> Min Bet
        # We map Low Value (High Eq) -> Max Bet
        
        # Using ** 0.5 instead of math.sqrt
        val_at_equity = 1 / (equity ** 0.5)
        val_min = 1 / (min_eq ** 0.5) 
        val_max = 1 / (max_eq ** 0.5) 
        
        func_range = val_min - val_max
        if func_range == 0: return min_bet
        
        # Normalize (0.0 at Min Eq, 1.0 at Max Eq)
        normalized_pos = (val_min - val_at_equity) / func_range
        
        # Map to money
        return min_bet + (normalized_pos * (max_bet - min_bet))

    # --- ROUND 1 (Pre-Flop / Flop) ---
    def round1(self, hole, comm, stacks, pot, win_prob):
        # 1. Determine Context
        active_players = self._get_active_player_count(stacks)
        # Clamp between 2 and 5 players logic
        if active_players < 2: active_players = 2
        if active_players > 5: active_players = 5
        
        # 2. Hard Fold Check
        # Manual get with default 0.20
        fold_floor = self.FOLD_THRESHOLDS.get(active_players)
        if fold_floor is None: fold_floor = 0.20
            
        if win_prob < fold_floor:
            return "fold", 0

        # 3. Strategy Selection
        
        # --- 5 PLAYERS ---
        if active_players == 5:
            if win_prob > 0.55:
                self.mode = "AGGRESSIVE"
                return "play", 235
            # REMOVED BLUFF CONDITION HERE
            elif win_prob >= 0.40:
                self.mode = "CONFIDENT"
                return "play", 204
            else:
                self.mode = "HYBRID"
                # Hybrid Band: 30% to 40% (Anything 14.5-30% gets Min Bet 110)
                return "play", self._calculate_ramp_bet(win_prob, 0.30, 0.40)

        # --- 4 PLAYERS ---
        elif active_players == 4:
            if win_prob > 0.65:
                self.mode = "AGGRESSIVE"
                return "play", 235
            elif win_prob > 0.55:
                self.mode = "CONFIDENT"
                return "play", 204
            else:
                self.mode = "HYBRID"
                # Hybrid Band: 20.3% to 55%
                return "play", self._calculate_ramp_bet(win_prob, 0.203, 0.55)

        # --- 3 PLAYERS ---
        elif active_players == 3:
            if win_prob > 0.65:
                self.mode = "AGGRESSIVE"
                return "play", 235
            elif win_prob > 0.60:
                self.mode = "CONFIDENT"
                return "play", 204
            else:
                self.mode = "HYBRID"
                # Hybrid Band: 25.6% to 60%
                return "play", self._calculate_ramp_bet(win_prob, 0.256, 0.60)

        # --- 2 PLAYERS ---
        else:
            if win_prob > 0.70:
                self.mode = "AGGRESSIVE"
                return "play", 235
            elif win_prob > 0.65:
                self.mode = "CONFIDENT"
                return "play", 204
            else:
                self.mode = "HYBRID"
                # Hybrid Band: 35.7% to 65%
                return "play", self._calculate_ramp_bet(win_prob, 0.357, 0.65)

    # --- ROUND 2 (Turn) ---
    def round2(self, hole, comm, r1_bets, stacks, pot, win_prob):
        # Safely get my r1 bet
        my_r1_bet = 0
        if self.my_index in r1_bets:
            my_r1_bet = r1_bets[self.my_index]

        min_limit = my_r1_bet * 0.5
        max_limit = my_r1_bet * 1.5

        if self.mode == "AGGRESSIVE":
            return max_limit

        if self.mode == "CONFIDENT":
            if win_prob < 0.40: return min_limit
            target = my_r1_bet * 1.25
            
            # Manual clamping logic to avoid dependencies
            final = target
            if final < min_limit: final = min_limit
            if final > max_limit: final = max_limit
            return final

        # HYBRID MODE: Safe Ramp
        # Maintain curve logic: Base 50 + (Eq * 200)
        target_bet = 50.0 + (win_prob * 200.0)
        
        # Clamp
        final = target_bet
        if final < min_limit: final = min_limit
        if final > max_limit: final = max_limit
        return final

    # --- ROUND 3 (River) ---
    def round3(self, hole, comm, r1_bets, r2_bets, stacks, pot, win_prob):
        # Safely get my r2 bet
        my_r2 = 0
        if self.my_index in r2_bets:
            my_r2 = r2_bets[self.my_index]

        min_limit = my_r2 * 0.75
        max_limit = my_r2 * 1.25

        if self.mode == "AGGRESSIVE":
            return max_limit

        if self.mode == "CONFIDENT":
            if win_prob > 0.70: return max_limit
            else: return my_r2 * 1.0

        # HYBRID MODE: Cap Optimizer
        ANTE = 100.0
        
        my_r1 = 0
        if self.my_index in r1_bets:
            my_r1 = r1_bets[self.my_index]
            
        invested_so_far = ANTE + my_r1 + my_r2
        
        numerator = pot - (4.0 * invested_so_far)
        ideal_cap_bet = numerator / 3.0
        
        weighted_bet = ideal_cap_bet * win_prob
        
        # Clamp
        final = weighted_bet
        if final < min_limit: final = min_limit
        if final > max_limit: final = max_limit
        return final
