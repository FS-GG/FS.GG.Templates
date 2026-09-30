use std::io::Write;
use std::process::{Command, Stdio};

#[test]
fn built_entrypoint_starts_fresh_completes_a_game_refuses_terminal_move_and_restarts() {
    let mut child = Command::new(env!("CARGO_BIN_EXE_rust-tic-tac-toe"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("built entrypoint must start");

    child
        .stdin
        .take()
        .expect("entrypoint stdin must be piped")
        .write_all(b"move 0\nmove 3\nmove 1\nmove 4\nmove 2\nmove 5\nrestart\nquit\n")
        .expect("player input must be written");

    let output = child
        .wait_with_output()
        .expect("built entrypoint must terminate");

    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let stdout = String::from_utf8(output.stdout).expect("entrypoint output must be UTF-8");
    let lines: Vec<_> = stdout.lines().collect();

    assert_eq!(
        lines.first().copied(),
        Some("STATE phase=playing turn=X winner=- board=---------")
    );
    assert!(lines.contains(&"STATE phase=won turn=X winner=X board=XXXOO----"));
    assert!(lines.contains(&"REFUSE move index=5 reason=terminal"));
    assert!(lines.contains(&"ACCEPT restart"));
    assert_eq!(
        lines
            .iter()
            .rev()
            .find(|line| line.starts_with("STATE"))
            .copied(),
        Some("STATE phase=playing turn=X winner=- board=---------")
    );
    assert_eq!(lines.last().copied(), Some("ACCEPT quit"));
}
