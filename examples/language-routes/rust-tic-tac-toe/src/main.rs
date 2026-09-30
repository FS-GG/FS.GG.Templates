use std::io;

fn main() -> io::Result<()> {
    let stdin = io::stdin();
    let stdout = io::stdout();
    fsgg_rust_tic_tac_toe::run(stdin.lock(), stdout.lock())
}
