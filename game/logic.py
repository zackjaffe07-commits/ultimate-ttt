WIN_LINES = [
    (0,1,2),(3,4,5),(6,7,8),
    (0,3,6),(1,4,7),(2,5,8),
    (0,4,8),(2,4,6)
]

class UltimateTicTacToe:
    def __init__(self):
        self.boards = [[None]*9 for _ in range(9)]
        self.board_winners = [None]*9
        self.current_player = "X"
        self.forced_board = None
        self.game_winner = None
        self.started = False

    def check_win(self, board):
        for a,b,c in WIN_LINES:
            if board[a] and board[a] == board[b] == board[c]:
                return board[a]
        if all(board):
            return "D"
        return None

    def make_move(self, b, c):
        if not self.started or self.game_winner:
            return False

        if self.board_winners[b]:
            return False
        if self.forced_board is not None and b != self.forced_board:
            return False
        if self.boards[b][c] is not None:
            return False

        self.boards[b][c] = self.current_player
        self.board_winners[b] = self.check_win(self.boards[b])
        self.game_winner = self.check_win(self.board_winners)

        self.forced_board = c if self.board_winners[c] is None else None
        self.current_player = "O" if self.current_player == "X" else "X"
        return True

    def resign(self, loser):
        self.game_winner = "O" if loser == "X" else "X"

    def state(self):
        return {
            "boards": self.boards,
            "winners": self.board_winners,
            "player": self.current_player,
            "forced": self.forced_board,
            "gameWinner": self.game_winner,
            "started": self.started
        }

