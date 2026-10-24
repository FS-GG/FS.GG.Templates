#![forbid(unsafe_code)]
fn polyglot_greet(name: &str) -> String {
    format!("hello {name}")
}
fn main() {
    let mut args = std::env::args().skip(1);
    let command = args.next().unwrap_or_else(|| "hello".into());
    if command != "hello" {
        eprintln!("requested failure");
        std::process::exit(2);
    }
    let name = args.next().unwrap_or_else(|| "world".into());
    let message = polyglot_greet(&name);
    println!("{message}");
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn literal_domain() {
        let message = polyglot_greet("$(literal);& with spaces");
        assert_eq!(message, "hello $(literal);& with spaces");
    }
}
