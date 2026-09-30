use std::fmt;
use std::io::{self, BufRead, Write};

pub const WINNING_LINES: [[usize; 3]; 8] = [
    [0, 1, 2],
    [3, 4, 5],
    [6, 7, 8],
    [0, 3, 6],
    [1, 4, 7],
    [2, 5, 8],
    [0, 4, 8],
    [2, 4, 6],
];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Player {
    X,
    O,
}

impl Player {
    fn other(self) -> Self {
        match self {
            Self::X => Self::O,
            Self::O => Self::X,
        }
    }
}

impl fmt::Display for Player {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::X => "X",
            Self::O => "O",
        })
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Phase {
    Playing,
    Won,
    Draw,
}

impl fmt::Display for Phase {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::Playing => "playing",
            Self::Won => "won",
            Self::Draw => "draw",
        })
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MoveError {
    OutOfRange,
    Occupied,
    Terminal,
}

impl fmt::Display for MoveError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::OutOfRange => "out-of-range",
            Self::Occupied => "occupied",
            Self::Terminal => "terminal",
        })
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Game {
    board: [Option<Player>; 9],
    phase: Phase,
    turn: Player,
    winner: Option<Player>,
}

impl Default for Game {
    fn default() -> Self {
        Self::new()
    }
}

impl Game {
    pub fn new() -> Self {
        Self {
            board: [None; 9],
            phase: Phase::Playing,
            turn: Player::X,
            winner: None,
        }
    }

    pub fn board(&self) -> &[Option<Player>; 9] {
        &self.board
    }

    pub fn phase(&self) -> Phase {
        self.phase
    }

    pub fn turn(&self) -> Player {
        self.turn
    }

    pub fn winner(&self) -> Option<Player> {
        self.winner
    }

    pub fn play(&mut self, index: isize) -> Result<Player, MoveError> {
        if self.phase != Phase::Playing {
            return Err(MoveError::Terminal);
        }

        let index = usize::try_from(index)
            .ok()
            .filter(|index| *index < self.board.len())
            .ok_or(MoveError::OutOfRange)?;

        if self.board[index].is_some() {
            return Err(MoveError::Occupied);
        }

        let player = self.turn;
        self.board[index] = Some(player);

        if has_won(&self.board, player) {
            self.phase = Phase::Won;
            self.winner = Some(player);
        } else if self.board.iter().all(Option::is_some) {
            self.phase = Phase::Draw;
        } else {
            self.turn = self.turn.other();
        }

        Ok(player)
    }

    pub fn restart(&mut self) {
        *self = Self::new();
    }

    pub fn state_line(&self) -> String {
        let board: String = self
            .board
            .iter()
            .map(|cell| match cell {
                Some(Player::X) => 'X',
                Some(Player::O) => 'O',
                None => '-',
            })
            .collect();
        let winner = self
            .winner
            .map_or_else(|| "-".to_owned(), |player| player.to_string());

        format!(
            "STATE phase={} turn={} winner={} board={}",
            self.phase, self.turn, winner, board
        )
    }
}

fn has_won(board: &[Option<Player>; 9], player: Player) -> bool {
    WINNING_LINES
        .iter()
        .any(|line| line.iter().all(|index| board[*index] == Some(player)))
}

pub fn run<R: BufRead, W: Write>(reader: R, mut writer: W) -> io::Result<()> {
    let mut game = Game::new();
    writeln!(writer, "{}", game.state_line())?;

    for line in reader.lines() {
        let line = line?;
        let fields: Vec<_> = line.split_whitespace().collect();

        match fields.as_slice() {
            ["move", index] => match index.parse::<isize>() {
                Ok(index) => match game.play(index) {
                    Ok(player) => writeln!(writer, "ACCEPT move index={index} player={player}")?,
                    Err(reason) => writeln!(writer, "REFUSE move index={index} reason={reason}")?,
                },
                Err(_) => writeln!(writer, "REFUSE input reason=move-index-integer-required")?,
            },
            ["restart"] => {
                game.restart();
                writeln!(writer, "ACCEPT restart")?;
            }
            ["quit"] => {
                writeln!(writer, "ACCEPT quit")?;
                return Ok(());
            }
            _ => writeln!(writer, "REFUSE input reason=expected-move-restart-or-quit")?,
        }

        writeln!(writer, "{}", game.state_line())?;
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn play(indices: &[isize]) -> Game {
        let mut game = Game::new();
        for index in indices {
            game.play(*index).expect("fixture move must be legal");
        }
        game
    }

    fn non_winning_complement(line: [usize; 3]) -> [usize; 3] {
        let outside: Vec<_> = (0..9).filter(|index| !line.contains(index)).collect();

        for first in 0..outside.len() {
            for second in first + 1..outside.len() {
                for third in second + 1..outside.len() {
                    let candidate = [outside[first], outside[second], outside[third]];
                    if !WINNING_LINES.contains(&candidate) {
                        return candidate;
                    }
                }
            }
        }

        panic!("every winning line must have a safe opponent complement")
    }

    #[test]
    fn legal_moves_alternate_players_and_report_state() {
        let mut game = Game::new();
        assert_eq!(game.play(0), Ok(Player::X));
        assert_eq!(game.play(4), Ok(Player::O));
        assert_eq!(game.turn(), Player::X);
        assert_eq!(game.board()[0], Some(Player::X));
        assert_eq!(game.board()[4], Some(Player::O));
        assert_eq!(
            game.state_line(),
            "STATE phase=playing turn=X winner=- board=X---O----"
        );
    }

    #[test]
    fn occupied_and_out_of_range_moves_are_refused_without_change() {
        let mut game = play(&[0]);
        let before = game.clone();

        assert_eq!(game.play(0), Err(MoveError::Occupied));
        assert_eq!(game, before);
        assert_eq!(game.play(-1), Err(MoveError::OutOfRange));
        assert_eq!(game, before);
        assert_eq!(game.play(9), Err(MoveError::OutOfRange));
        assert_eq!(game, before);
    }

    #[test]
    fn both_players_can_win_on_every_winning_line() {
        for line in WINNING_LINES {
            let outside: Vec<_> = (0..9).filter(|index| !line.contains(index)).collect();
            let x_game = play(&[
                line[0] as isize,
                outside[0] as isize,
                line[1] as isize,
                outside[1] as isize,
                line[2] as isize,
            ]);
            assert_eq!(x_game.phase(), Phase::Won, "X line {line:?}");
            assert_eq!(x_game.winner(), Some(Player::X), "X line {line:?}");

            let x_moves = non_winning_complement(line);
            let o_game = play(&[
                x_moves[0] as isize,
                line[0] as isize,
                x_moves[1] as isize,
                line[1] as isize,
                x_moves[2] as isize,
                line[2] as isize,
            ]);
            assert_eq!(o_game.phase(), Phase::Won, "O line {line:?}");
            assert_eq!(o_game.winner(), Some(Player::O), "O line {line:?}");
        }
    }

    #[test]
    fn draw_and_ninth_move_win_are_distinguished_in_win_first_order() {
        let draw = play(&[0, 1, 2, 4, 3, 5, 7, 6, 8]);
        assert_eq!(draw.phase(), Phase::Draw);
        assert_eq!(draw.winner(), None);

        let ninth_move_win = play(&[0, 1, 2, 3, 4, 5, 7, 6, 8]);
        assert_eq!(ninth_move_win.phase(), Phase::Won);
        assert_eq!(ninth_move_win.winner(), Some(Player::X));
    }

    #[test]
    fn terminal_games_refuse_moves_and_restart_from_every_phase() {
        let won = play(&[0, 3, 1, 4, 2]);
        let draw = play(&[0, 1, 2, 4, 3, 5, 7, 6, 8]);

        for terminal in [won, draw] {
            let mut game = terminal.clone();
            assert_eq!(game.play(6), Err(MoveError::Terminal));
            assert_eq!(game, terminal);
            game.restart();
            assert_eq!(game, Game::new());
        }

        let mut playing = play(&[0, 1]);
        playing.restart();
        assert_eq!(playing, Game::new());
    }

    #[test]
    fn native_protocol_reports_refusals_and_preserves_state() {
        let input = b"move 0\nmove 0\nmove -1\nmove nine\nunknown\nquit\n";
        let mut output = Vec::new();
        run(&input[..], &mut output).expect("in-memory protocol must complete");
        let output = String::from_utf8(output).expect("protocol output must be UTF-8");

        assert!(output.contains("ACCEPT move index=0 player=X"));
        assert!(output.contains("REFUSE move index=0 reason=occupied"));
        assert!(output.contains("REFUSE move index=-1 reason=out-of-range"));
        assert!(output.contains("REFUSE input reason=move-index-integer-required"));
        assert!(output.contains("REFUSE input reason=expected-move-restart-or-quit"));
        assert_eq!(output.matches("board=X--------").count(), 5);
    }
}
