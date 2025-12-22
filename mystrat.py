"""
To understand deeply how  to use this functions and all the variables given please look at the dummy_strategies.py file.

You have to implement your strategy in this file. 

Change the class name (i.e YourStrategyName) with your team name. 
Also change same name in dummy_strategies.py file (where imports are being done)
"""


class YourStrategyName:
    def __init__(self):
        # Initialize any state variables here.
        # This is where your unique index for the CURRENT match will be stored.
        self.my_index = -1
        pass

    def initialize_game(self, match_history, current_game_num):
        # 1. Update Opponent Profiles (only if new data exists)

        pass

    # --- ROUND 1 (Pre-Flop) ---
    def round1(self, hole, comm, stacks, pot, win_prob):
        """
        ... (arguments are the same)

        CRUCIAL INFO:
        Your unique index for the current game is available via: self.my_index
        Use it to access your stack and your previous bets:
        - stacks[self.my_index]
        """
        return "fold", 0 #dummy return
        pass


    # --- ROUND 2 (Flop/Turn) ---
    def round2(self, hole, comm, r1_bets, stacks, pot, win_prob):
        """
        Args:
            r1_bets (dict): R1 bets {player_index: bet_amount}.

        Returns:
            float: Desired bet amount.
        """
        pass

    # --- ROUND 3 (River) ---
    def round3(self, hole, comm, r1_bets, r2_bets, stacks, pot, win_prob):
        """
        Args:
            r2_bets (dict): R2 bets {player_index: bet_amount}.

        Returns:
            float: Desired bet amount.
        """
        pass