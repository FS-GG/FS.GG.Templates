#[test]
fn actual_cli() {
    let binary = env!("CARGO_BIN_EXE_product-cli");
    let ok = std::process::Command::new(binary)
        .args(["hello", "$(literal);& with spaces"])
        .output()
        .unwrap();
    assert!(ok.status.success());
    assert_eq!(
        String::from_utf8(ok.stdout).unwrap(),
        "hello $(literal);& with spaces\n"
    );
    let bad = std::process::Command::new(binary)
        .arg("--fail")
        .output()
        .unwrap();
    assert_eq!(bad.status.code(), Some(2));
    assert_eq!(
        String::from_utf8(bad.stderr).unwrap(),
        "requested failure\n"
    );
}
